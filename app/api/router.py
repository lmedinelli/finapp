from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.admin import Base, engine, get_db_session
from app.repositories.portfolio_repo import PortfolioRepository
from app.schemas.analysis import AnalysisResponse
from app.schemas.common import HealthResponse
from app.schemas.portfolio import PositionCreate, PositionRead
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.analytics import AnalyticsService
from app.services.market_data import MarketDataService
from app.services.recommendation import RecommendationService

Base.metadata.create_all(bind=engine)

router = APIRouter()
settings = get_settings()
market_data_service = MarketDataService()
analytics_service = AnalyticsService()
recommendation_service = RecommendationService()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, timestamp=datetime.utcnow())


@router.post("/market/ingest/{symbol}")
def ingest_symbol(symbol: str, asset_type: str = "stock") -> dict[str, str | int]:
    return market_data_service.ingest(symbol=symbol, asset_type=asset_type)


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
def analyze_symbol(symbol: str) -> AnalysisResponse:
    try:
        result = analytics_service.compute(symbol)
        return AnalysisResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(payload: RecommendationRequest) -> RecommendationResponse:
    try:
        result = recommendation_service.recommend(
            symbol=payload.symbol,
            risk_profile=payload.risk_profile,
            asset_type=payload.asset_type,
        )
        return RecommendationResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio/positions", response_model=PositionRead)
def create_position(payload: PositionCreate, db: Session = Depends(get_db_session)) -> PositionRead:
    repo = PortfolioRepository(db)
    saved = repo.create_position(payload)
    return PositionRead(
        id=saved.id,
        user_id=saved.user_id,
        symbol=saved.symbol,
        asset_type=saved.asset_type,
        quantity=saved.quantity,
        avg_price=saved.avg_price,
    )


@router.get("/portfolio/{user_id}/positions", response_model=list[PositionRead])
def list_positions(user_id: int, db: Session = Depends(get_db_session)) -> list[PositionRead]:
    repo = PortfolioRepository(db)
    rows = repo.list_positions(user_id)
    return [
        PositionRead(
            id=r.id,
            user_id=r.user_id,
            symbol=r.symbol,
            asset_type=r.asset_type,
            quantity=r.quantity,
            avg_price=r.avg_price,
        )
        for r in rows
    ]
