from tulipee.router import route, Context
from .utils import send_stream_reply


@route(stream="support", topic="triage")
async def support_triage(ctx: Context) -> None:
    content = (ctx.message.content or "").strip()
    if "urgent" in content.lower():
        await send_stream_reply(ctx, "Acknowledged: marking as urgent triage.")
    else:
        await send_stream_reply(ctx, "Triage noted. Our team will follow up.")

