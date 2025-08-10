# emails.py
from typing import Optional, Dict, Any
from db.base import BaseRepo, Client

class EmailsRepo(BaseRepo):
    def __init__(self, sb: Client):
        super().__init__(sb, "emails")

    async def get_by_email(self, email: str) -> Optional[Dict]:
        return await self.get_one(email=email)

    async def _get_email_row(sb: Client, email: str) -> Optional[Dict[str, Any]]:
        res = await sb.table("emails").select("*").eq("email", email).maybe_single().execute()
        return res.data

    async def upsert_email(self, data: Dict) -> Dict:
        res = await (
            self.sb.table(self.table)
            .upsert(data, on_conflict="email")
            .select("*")
            .single()
            .execute()
        )
        return res.data

    async def set_used(self, email: str, used: bool = True) -> Dict:
        res = await (
            self.sb.table(self.table)
            .update({"used": used})
            .eq("email", email)
            .select("*")
            .single()
            .execute()
        )
        return res.data

    async def set_banned(self, email: str, banned: bool = True) -> Dict:
        res = await (
            self.sb.table(self.table)
            .update({"banned": banned})
            .eq("email", email)
            .select("*")
            .single()
            .execute()
        )
        return res.data

    async def find_free_email(sb: Client) -> Optional[Dict[str, Any]]:
        res = (
            await sb.table("emails")
            .select("*")
            .or_("used.is.false,used.is.null")
            .or_("banned.is.false,banned.is.null")
            .order("created_at", desc=False)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return res.data


    async def _mark_email_used(sb: Client, email: str, used: bool) -> Optional[Dict[str, Any]]:
        res = (
            await sb.table("emails")
            .update({"used": used})
            .eq("email", email)
            .select("*")
            .maybe_single()
            .execute()
        )
        return res.data
