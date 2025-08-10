# base.py
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple
from supabase._async.client import AsyncClient as Client, create_client  # async API


async def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_*_KEY in environment.")
    return await create_client(url, key)


class BaseRepo:
    def __init__(self, sb: Client, table: str):
        self.sb = sb
        self.table = table

    # ---------- Generic CRUD (async) ----------
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        res = await self.sb.table(self.table).insert(data).select("*").single().execute()
        return res.data

    async def bulk_create(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        res = await self.sb.table(self.table).insert(list(rows)).select("*").execute()
        return res.data or []

    async def get_by_id(self, id_: int) -> Optional[Dict[str, Any]]:
        res = await self.sb.table(self.table).select("*").eq("id", id_).single().execute()
        return res.data

    async def get_one(self, **filters) -> Optional[Dict[str, Any]]:
        q = self.sb.table(self.table).select("*")
        for k, v in filters.items():
            q = q.eq(k, v)
        res = await q.limit(1).maybe_single().execute()
        return res.data

    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[Tuple[str, str]] = ("created_at", "desc"),
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
    ) -> List[Dict[str, Any]]:
        q = self.sb.table(self.table).select("*")
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        if order:
            col, direction = order
            q = q.order(col, desc=(direction.lower() == "desc"))
        if offset:
            q = q.range(offset, offset + (limit or 100) - 1)
        elif limit:
            q = q.limit(limit)
        res = await q.execute()
        return res.data or []

    async def update(self, id_: int, data: Dict[str, Any]) -> Dict[str, Any]:
        data = {k: v for k, v in data.items() if k != "id"}
        res = await self.sb.table(self.table).update(data).eq("id", id_).select("*").single().execute()
        return res.data

    async def delete(self, id_: int) -> None:
        await self.sb.table(self.table).delete().eq("id", id_).execute()
