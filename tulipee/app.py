
import logging

from tulipee.client import ZulipClient
from tulipee.settings import Settings
from tulipee.router import Router, mount_registered_routes
from tulipee.discovery import import_all_handlers


async def start_app():
    settings = Settings()
    logger = logging.getLogger("tulipee.app")
    logger.info("Starting Tulipee app")
    logger.debug("Config: zulip_url=%s email=%s", settings.zulip_url, settings.email)
    client = ZulipClient(
        zulip_url=settings.zulip_url,
        api_key=settings.api_key,
        email=settings.email,
    )

    router = Router()
    # Import handlers dynamically so their decorators register routes
    import_all_handlers("tulipee.handlers")
    # Mount all decorator-registered routes
    mount_registered_routes(router)

    async for message in client.stream_messages():
        logger.debug(
            "Recv msg id=%s type=%s stream_id=%s subject=%s sender=%s",
            getattr(message, "id", None),
            getattr(message, "type", None),
            getattr(message, "stream_id", None),
            getattr(message, "subject", None),
            getattr(message, "sender_email", None),
        )
        if message.sender_email == settings.email:
            logger.debug("Skipping own message id=%s", getattr(message, "id", None))
            continue
        handled = await router.dispatch(message, settings, client)
        if not handled:
            logger.debug("Message id=%s not handled by any route", getattr(message, "id", None))
            continue
