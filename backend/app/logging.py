import logging
import sys
from backend.app.config import settings


def setup_logging():
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Silence noisy third-party loggers if needed
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


logger = logging.getLogger("crypto_tracer")
