from tulipee.router import route, Context
from .utils import send_stream_reply


@route(stream="general", topic="general chat")
async def general_chat(ctx: Context) -> None:
    content = (ctx.message.content or "").strip()
    if not content:
        return
    await send_stream_reply(ctx, content)

