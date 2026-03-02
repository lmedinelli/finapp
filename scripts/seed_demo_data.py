from sqlalchemy.orm import Session

from app.db.admin import Base, SessionLocal, engine
from app.models.admin import PortfolioPosition, UserProfile


Base.metadata.create_all(bind=engine)


def seed(session: Session) -> None:
    if session.query(UserProfile).count() == 0:
        user = UserProfile(name="Demo User", risk_profile="balanced", base_currency="USD")
        session.add(user)
        session.commit()
        session.refresh(user)

        positions = [
            PortfolioPosition(user_id=user.id, symbol="AAPL", asset_type="stock", quantity=10, avg_price=180),
            PortfolioPosition(user_id=user.id, symbol="BTC-USD", asset_type="crypto", quantity=0.1, avg_price=60000),
        ]
        session.add_all(positions)
        session.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
    print("Demo admin data seeded.")
