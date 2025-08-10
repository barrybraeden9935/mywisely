# users.py
from typing import Optional, Dict, Any
from db.base import BaseRepo, Client

class UsersRepo(BaseRepo):
    def __init__(self, sb: Client):
        super().__init__(sb, "users")

    async def get_by_email(self, email: str) -> Optional[Dict]:
        return await self.get_one(email=email)

    async def get_by_username(self, username: str) -> Optional[Dict]:
        return await self.get_one(username=username)

    async def ban(self, id_: int, banned: bool = True) -> Dict:
        return await self.update(id_, {"banned": banned})

    async def set_profile_id(self, id_: int, profile_id: str) -> Dict:
        return await self.update(id_, {"profile_id": profile_id})

    async def _get_user_row_by_email(sb: Client, email: str) -> Optional[Dict[str, Any]]:
        res = (
            await sb.table("users")
            .select("*")
            .eq("email", email)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return res.data