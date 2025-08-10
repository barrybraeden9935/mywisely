# tasks.py
from typing import Optional, Dict, List, Union, Any
from base import BaseRepo, Client

Json = Union[dict, list, str, int, float, bool, None]

class TasksRepo(BaseRepo):
    def __init__(self, sb: Client):
        super().__init__(sb, "tasks")

    async def create_task(
        self,
        task_type: str,
        additional_data: Optional[Json] = None,
        status: Optional[str] = None,
        message_id: Optional[str] = None,
        email: Optional[str] = None,
        output: Optional[Json] = None,
    ) -> Dict:
        data: Dict = {
            "task_type": task_type,
            "additional_data": additional_data,
            "status": status,
            "message_id": message_id,
            "email": email,
            "output": output,
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self.create(data)

    async def set_status(self, id_: int, status: str, output: Optional[Json] = None) -> Dict:
        payload: Dict = {"status": status}
        if output is not None:
            payload["output"] = output
        return await self.update(id_, payload)

    async def for_email(self, email: str, limit: int = 100) -> List[Dict]:
        return await self.list(filters={"email": email}, limit=limit)

    async def list_completed(self, limit: int = 50) -> List[Dict[str, Any]]:
        q = (
            self.sb.table(self.table)
            .select("*")
            .eq("status", "COMPLETED")
            .order("created_at", desc=False)
            .limit(limit)
        )
        res = await q.execute()
        return res.data or []

    async def delete_by_id(self, id_: int) -> None:
        await self.sb.table(self.table).delete().eq("id", id_).execute()