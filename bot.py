# task_worker.py
import os
import re
import sys
import json 
from loguru import logger
import random
import asyncio
import traceback
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from db.base import get_supabase
from db.tasks import TasksRepo
from processors.wisley_login import WisleyLogin

with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)
for k, v in cfg.items():
    os.environ[k] = str(v)
    logger.debug(f"Loaded env var: {k}")

CONFIG = {
    "POLL_INTERVAL": {"min": 1000, "max": 15000},  # ms
    "NO_TASKS_WAIT": 10000,                        # ms
    "MAX_ITERATIONS": 999_999_999,
    "MAX_TASKS_FETCH": 500,
}

# ───────────────────────── helpers ─────────────────────────
def random_int(a: int, b: int) -> int:
    return random.randint(a, b)

async def delay(ms: int) -> None:
    await asyncio.sleep(ms / 1000)

def extract_id_from_env(k: str) -> Optional[str]:
    v = os.getenv(k, "")
    m = re.search(r"\d+", v)
    return m.group(0) if m else None

def _normalize_type(t: Optional[str]) -> str:
    return (t or "").strip().lower()

def _is_balance_type(t: Optional[str]) -> bool:
    t = _normalize_type(t)
    return t in {"balance_check", "balance", "balance_check".lower()}

def _is_register_type(t: Optional[str]) -> bool:
    return _normalize_type(t) == "register"

def _eligible(task_type: str, rdp_id: str, thread_id: str) -> bool:
    # balance is always eligible
    if _is_balance_type(task_type):
        return True
    # register / c2c (if you add later) restricted to rdp=1, thread=1
    if _is_register_type(task_type):
        return rdp_id == "1" and thread_id == "1"
    return False

def _priority(task_type: str) -> int:
    # If you add C2C later, give it higher priority.
    if _is_balance_type(task_type):
        return 2
    if _is_register_type(task_type):
        return 3
    return 999

# ───────────────────────── fetching ─────────────────────────
async def _fetch_queued(tasks_repo: TasksRepo, *, task_type: str) -> List[Dict[str, Any]]:
    """
    Your bot queues tasks with status='queued'. We also tolerate legacy 'PENDING'.
    """
    rows: List[Dict[str, Any]] = []

    # primary: queued
    r1 = await tasks_repo.list(
        filters={"status": "queued", "task_type": task_type},
        order=("created_at", "asc"),
        limit=CONFIG["MAX_TASKS_FETCH"],
    )
    if r1:
        rows.extend(r1)

    # fallback: PENDING (if any legacy)
    r2 = await tasks_repo.list(
        filters={"status": "PENDING", "task_type": task_type},
        order=("created_at", "asc"),
        limit=CONFIG["MAX_TASKS_FETCH"],
    )
    if r2:
        rows.extend(r2)

    return rows

async def _fetch_by_priority(tasks_repo: TasksRepo, rdp_id: str, thread_id: str) -> List[Dict[str, Any]]:
    """
    Priority: (C2C later if you add) > BALANCE > REGISTER
    We only fetch for types your bot actually uses right now.
    """
    # BALANCE first (since this is the only active type you run via WisleyLogin)
    balance_rows: List[Dict[str, Any]] = []
    # accept either "balance_check" or legacy/case variants
    for t in ("balance_check", "BALANCE", "BALANCE_CHECK"):
        balance_rows.extend(await _fetch_queued(tasks_repo, task_type=t))
    if balance_rows:
        print(f"Found {len(balance_rows)} balance_check tasks")
        return balance_rows

    # REGISTER (only if worker should handle it and eligible)
    if rdp_id == "1" and thread_id == "1":
        register_rows = await _fetch_queued(tasks_repo, task_type="REGISTER")
        if register_rows:
            print(f"Found {len(register_rows)} REGISTER tasks")
            return register_rows

    print("No eligible tasks found")
    return []

# ───────────────────────── processors ─────────────────────────
async def _process_balance_task(tasks_repo: TasksRepo, task: Dict[str, Any], rdp_id: str, thread_id: str) -> None:
    # set RUNNING
    await tasks_repo.update(task["id"], {"status": "RUNNING"})
    ad = task.get("additional_data") or {}

    email_record = ad.get("email_record") 
    user_record = ad.get("user_record")

    wl = WisleyLogin(rdp_id, thread_id, email_record, user_record)
    output = wl.login()

    # mark COMPLETED with raw output (cron will parse + post)
    await tasks_repo.update(task["id"], {"status": "COMPLETED", "output": output})

# If/when you wire REGISTER in this worker, make it follow the same shapes as bot.py:
# - task_type: "REGISTER"
# - status: queued -> RUNNING -> COMPLETED/FAILED
# - additional_data.form / .email_record / .user_record / .username / .password
# async def _process_register_task(tasks_repo: TasksRepo, task: Dict[str, Any]) -> None:
#     await tasks_repo.update(task["id"], {"status": "RUNNING"})
#     ad = task.get("additional_data") or {}
#     proxy_provider = ad.get("form", {}).get("proxy_provider") or ad.get("proxy_provider")
#     email_record = ad.get("email_record")
#     user_record = ad.get("user_record")
#     proxy = await _generate_proxy(proxy_provider) if proxy_provider else None
#     client = RapidFSRegister(proxy, email_record, user_record, ad)
#     output = await client.register()
#     await tasks_repo.update(task["id"], {"status": "COMPLETED", "output": output})

async def _process_task(tasks_repo: TasksRepo, task: Dict[str, Any], rdp_id: str, thread_id: str) -> bool:
    ttype = _normalize_type(task.get("task_type"))
    if not _eligible(ttype, rdp_id, thread_id):
        print(f"Skipping task {task.get('id')} of type {ttype} (not eligible for RDP {rdp_id}, Thread {thread_id})")
        return False

    try:
        if _is_balance_type(ttype):
            await _process_balance_task(tasks_repo, task, rdp_id, thread_id)
        elif _is_register_type(ttype):
            # await _process_register_task(tasks_repo, task)
            # Not enabled yet
            return False
        else:
            print(f"Unknown task type: {ttype}")
            return False
        return True
    except Exception:
        err = traceback.format_exc()
        print(f"Error processing task {task.get('id')}: {err}")
        await tasks_repo.update(task["id"], {"status": "FAILED", "output": err})
        return False

# ───────────────────────── main loop ─────────────────────────
def _validate_environment() -> Tuple[str, str]:
    thread_id = extract_id_from_env("THREAD_ID")
    rdp_id = extract_id_from_env("RDP_ID")
    if not thread_id:
        raise RuntimeError("THREAD_ID is not set or invalid")
    if not rdp_id:
        raise RuntimeError("RDP_ID is not set or invalid")
    return thread_id, rdp_id

async def main():
    thread_id, rdp_id = _validate_environment()
    print(f"Starting task worker for RDP {rdp_id}, Thread {thread_id}")
    print("Priority: BALANCE(2) > REGISTER(3)")
    print("Eligibility: REGISTER requires RDP=1 & Thread=1; BALANCE always eligible")

    sb = await get_supabase()
    tasks_repo = TasksRepo(sb)

    for _ in range(CONFIG["MAX_ITERATIONS"]):
        pending = await _fetch_by_priority(tasks_repo, rdp_id, thread_id)

        if not pending:
            secs = CONFIG["NO_TASKS_WAIT"] // 1000
            print(f"No eligible tasks. Sleeping {secs}s…")
            await delay(CONFIG["NO_TASKS_WAIT"])
            continue

        task = random.choice(pending)
        prio = _priority(task.get("task_type", ""))
        print(f"Processing task {task.get('id')} of type {task.get('task_type')} (Priority: {prio})")

        ok = await _process_task(tasks_repo, task, rdp_id, thread_id)
        print(f"{'✅' if ok else '❌'} Task {task.get('id')} {'completed' if ok else 'failed'}")

        await delay(random_int(CONFIG["POLL_INTERVAL"]["min"], CONFIG["POLL_INTERVAL"]["max"]))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
