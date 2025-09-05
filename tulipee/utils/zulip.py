from tulipee.router import Context


async def send_stream_reply(ctx: Context, content: str) -> None:
    assert ctx.message.stream_id is not None
    await ctx.client.send_message_to_stream(
        stream=ctx.message.stream_id,
        topic=ctx.message.subject,
        content=content,
    )

