from __future__ import annotations

import logging
from tulipee.router import route, Context
from tulipee.utils.llm import issue_flow_turn, LLMError
from tulipee.utils.youtrack import YouTrackClient, YouTrackError
from tulipee.utils.zulip import send_stream_reply
from tulipee.utils.conversation import flow_store, chat_history
from tulipee.handlers.youtrack_projects import get_project_catalog, resolve_project_id


@route(stream="youtrack", topic="create issue")
async def youtrack_create_issue(ctx: Context) -> None:
    log = logging.getLogger("tulipee.handlers.youtrack_create")

    content = (ctx.message.content or "").strip()
    if not content:
        return

    st = ctx.settings
    # Validate configuration early
    if not st.youtrack_url or not st.youtrack_token:
        await send_stream_reply(
            ctx,
            "YouTrack is not configured. Set `YOUTRACK_URL` and `YOUTRACK_TOKEN` in .env.",
        )
        return

    assert ctx.message.stream_id is not None  # ensured by route(stream=..., topic=...)

    # Retrieve any prior LLM-managed state and chat history
    prior = flow_store.get(
        stream_id=ctx.message.stream_id,
        subject=ctx.message.subject,
        sender_id=ctx.message.sender_id,
    )
    history = chat_history.get(
        stream_id=ctx.message.stream_id,
        subject=ctx.message.subject,
        sender_id=ctx.message.sender_id,
    )
    # Append current user message to history before calling LLM
    chat_history.append(
        stream_id=ctx.message.stream_id,
        subject=ctx.message.subject,
        sender_id=ctx.message.sender_id,
        role="user",
        content=content,
    )

    # Let the LLM decide the next step and message
    try:
        catalog = [
            {"id": p.id, "key": p.key, "name": p.name, "description": p.description}
            for p in get_project_catalog()
        ]
        turn = await issue_flow_turn(
            content=content,
            prior_state=prior,
            projects=catalog,
            history=history,
            api_key=st.openai_api_key,
            model=st.openai_model,
            base_url=st.openai_base_url,
            referer=st.openai_http_referer,
            app_title=st.openai_app_title,
        )
    except LLMError as e:
        await send_stream_reply(ctx, f"대화를 처리하지 못했어요: {e}.")
        return

    intent = (turn.get("intent") or "ask").lower()
    issue = (turn.get("issue") or {})
    state = (turn.get("state") or {})

    # Compose assistant reply and, when applicable, append a deterministic preview
    reply_text = turn.get("reply") or ""
    def _format_preview(data: dict) -> str:
        title = (data.get("title") or "").strip()
        desc = (data.get("description") or "").strip()
        itype = (data.get("type") or "Task").strip() or "Task"
        proj_id = (data.get("project_id") or "").strip()
        proj_key = (data.get("project_key") or data.get("project") or "").strip()
        proj_name = (data.get("project_name") or "").strip()
        proj_label = ""
        if proj_id:
            match = next((p for p in catalog if p.get("id") == proj_id), None)
            if match:
                proj_label = f"{match.get('key') or ''} ({match.get('name') or ''})"
            else:
                proj_label = proj_id
        elif proj_key:
            proj_label = proj_key
        elif proj_name:
            proj_label = proj_name
        else:
            proj_label = "(unset)"
        parts = [
            "Draft preview:",
            f"- Title: {title or '(unset)'}",
            f"- Type: {itype}",
            f"- Project: {proj_label}",
            "- Description:\n```\n" + (desc or "(empty)") + "\n```",
        ]
        return "\n".join(parts)

    if intent != "create" and (issue.get("title") or issue.get("description") or issue.get("type") or issue.get("project_id") or issue.get("project_key") or issue.get("project_name")):
        preview = _format_preview(issue)
        reply_text = (reply_text + "\n\n" + preview).strip()

    if reply_text:
        await send_stream_reply(ctx, reply_text)
        # Record assistant reply into history
        chat_history.append(
            stream_id=ctx.message.stream_id,
            subject=ctx.message.subject,
            sender_id=ctx.message.sender_id,
            role="assistant",
            content=reply_text,
        )

    if intent == "cancel":
        flow_store.clear(
            stream_id=ctx.message.stream_id,
            subject=ctx.message.subject,
            sender_id=ctx.message.sender_id,
        )
        chat_history.clear(
            stream_id=ctx.message.stream_id,
            subject=ctx.message.subject,
            sender_id=ctx.message.sender_id,
        )
        return

    if intent == "create":
        # Validate configuration
        if not st.youtrack_url or not st.youtrack_token:
            await send_stream_reply(ctx, "YouTrack 설정이 없습니다. `YOUTRACK_URL`/`YOUTRACK_TOKEN`을 설정해 주세요.")
            return
        title = (issue.get("title") or "Untitled").strip()
        description = (issue.get("description") or "").strip()
        issue_type = (issue.get("type") or "Task").strip() or "Task"
        project_id = resolve_project_id(
            project_id=issue.get("project_id"),
            project_key=issue.get("project_key") or issue.get("project"),
            project_name=issue.get("project_name"),
        )
        if not project_id:
            await send_stream_reply(ctx, "프로젝트를 아직 결정하지 못했어요. 어떤 프로젝트에 만들까요? (프로젝트 키/이름으로 알려주세요)")
            # Keep state so user can continue
            flow_store.set(
                stream_id=ctx.message.stream_id,
                subject=ctx.message.subject,
                sender_id=ctx.message.sender_id,
                state=state,
            )
            return
        yt = YouTrackClient(st.youtrack_url, st.youtrack_token)
        try:
            result = await yt.create_issue(
                summary=title,
                description=description,
                project_id=project_id,
                type_name=issue_type,
            )
        except YouTrackError as e:
            log.exception("YouTrack create failed")
            await send_stream_reply(ctx, f"YouTrack error: {e}")
            # Keep state to allow retry/edit
            flow_store.set(
                stream_id=ctx.message.stream_id,
                subject=ctx.message.subject,
                sender_id=ctx.message.sender_id,
                state=state,
            )
            return
        key = result.get("idReadable") or result.get("id") or "(unknown)"
        url = f"{st.youtrack_url}/issue/{key}" if st.youtrack_url and key else st.youtrack_url or ""
        await send_stream_reply(ctx, f"생성 완료: {key} {url}")
        # Add assistant confirmation to history
        chat_history.append(
            stream_id=ctx.message.stream_id,
            subject=ctx.message.subject,
            sender_id=ctx.message.sender_id,
            role="assistant",
            content=f"생성 완료: {key} {url}",
        )
        flow_store.clear(
            stream_id=ctx.message.stream_id,
            subject=ctx.message.subject,
            sender_id=ctx.message.sender_id,
        )
        chat_history.clear(
            stream_id=ctx.message.stream_id,
            subject=ctx.message.subject,
            sender_id=ctx.message.sender_id,
        )
        return

    # Default: ask → persist updated state
    flow_store.set(
        stream_id=ctx.message.stream_id,
        subject=ctx.message.subject,
        sender_id=ctx.message.sender_id,
        state=state,
    )
