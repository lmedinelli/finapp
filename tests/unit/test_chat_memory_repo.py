from uuid import uuid4

from app.db.admin import Base, SessionLocal, engine
from app.repositories.chat_memory_repo import ChatMemoryRepository


def test_chat_memory_repo_roundtrip() -> None:
    Base.metadata.create_all(bind=engine)
    session_id = f"test-{uuid4().hex}"
    with SessionLocal() as session:
        repo = ChatMemoryRepository(session)
        repo.add_entry(session_id=session_id, role="user", content="Should I buy AAPL?")
        repo.add_entry(session_id=session_id, role="assistant", content="Here is the analysis.")
        rows = repo.list_recent(session_id=session_id, limit=10)

    assert len(rows) == 2
    assert rows[0].role == "user"
    assert rows[1].role == "assistant"
