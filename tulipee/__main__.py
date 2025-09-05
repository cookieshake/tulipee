import asyncio
import logging

from tulipee.app import start_app
from tulipee.settings import Settings


if __name__ == "__main__":
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(start_app())
