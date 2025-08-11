# db/emails.py
from typing import Optional, Dict, Any
from db.base import BaseRepo, Client

class EmailsRepo(BaseRepo):
    def __init__(self, sb: Client):
        super().__init__(sb, "emails")

    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self.get_one(email=email)

    async def find_free_email(self) -> Optional[Dict[str, Any]]:
        """
        Pick one email where used is false or null, and banned is not true (false or null).
        Oldest first to be predictable.
        """
        res = await (
            self.sb.table(self.table)
            .select("*")
            .eq("used", False)
            .eq("banned", False)
            .order("created_at", desc=False)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return res.data

    async def upsert_email(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # NOTE: async client can't chain .select().single() after upsert
        resp = await (
            self.sb.table(self.table)
            .upsert(data, on_conflict="email")
            .execute()
        )
        rows = resp.data or []
        return rows[0] if isinstance(rows, list) and rows else rows or None

    async def set_used(self, email: str, used: bool = True) -> Optional[Dict[str, Any]]:
        # NOTE: async client can't chain .select() after update
        resp = await (
            self.sb.table(self.table)
            .update({"used": used})
            .eq("email", email)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if isinstance(rows, list) and rows else rows or None

    async def set_banned(self, email: str, banned: bool = True) -> Optional[Dict[str, Any]]:
        # NOTE: async client can't chain .select() after update
        resp = await (
            self.sb.table(self.table)
            .update({"banned": banned})
            .eq("email", email)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if isinstance(rows, list) and rows else rows or None
