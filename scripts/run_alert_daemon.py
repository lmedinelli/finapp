from __future__ import annotations

import sys
import time
from pathlib import Path


def _bootstrap_project_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def main() -> None:
    _bootstrap_project_path()
    from app.core.config import get_settings
    from app.services.alert_daemon import AlertDaemonService

    settings = get_settings()
    service = AlertDaemonService()
    status = service.start_background_loop()
    print(f"Alert daemon started: {status}")
    frequency = max(60, int(settings.alert_daemon_frequency_seconds))
    try:
        while True:
            time.sleep(frequency)
    except KeyboardInterrupt:
        pass
    finally:
        final_status = service.stop_background_loop()
        print(f"Alert daemon stopped: {final_status}")


if __name__ == "__main__":
    main()
