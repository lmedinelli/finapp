from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import PortfolioPosition
from app.schemas.portfolio import PositionCreate


class PortfolioRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_position(self, payload: PositionCreate) -> PortfolioPosition:
        position = PortfolioPosition(**payload.model_dump())
        self.session.add(position)
        self.session.commit()
        self.session.refresh(position)
        return position

    def list_positions(self, user_id: int) -> list[PortfolioPosition]:
        stmt = select(PortfolioPosition).where(PortfolioPosition.user_id == user_id)
        return list(self.session.scalars(stmt).all())
