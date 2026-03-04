from fastapi import FastAPI

from app.api.router import alert_daemon_service
from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level, settings.log_file_path)

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(api_router)


@app.on_event("startup")
def start_background_alert_daemon() -> None:
    if settings.alert_daemon_autostart:
        alert_daemon_service.start_background_loop()


@app.on_event("shutdown")
def stop_background_alert_daemon() -> None:
    alert_daemon_service.stop_background_loop()
