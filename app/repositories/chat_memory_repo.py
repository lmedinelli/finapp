from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import ChatMemory


class ChatMemoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_entry(self, session_id: str, role: str, content: str) -> ChatMemory:
        entry = ChatMemory(session_id=session_id, role=role, content=content)
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def list_recent(self, session_id: str, limit: int = 12) -> list[ChatMemory]:
        stmt = (
            select(ChatMemory)
            .where(ChatMemory.session_id == session_id)
            .order_by(ChatMemory.created_at.desc(), ChatMemory.id.desc())
            .limit(limit)
        )
        rows = list(self.session.scalars(stmt).all())
        return list(reversed(rows))
