import json
import logging
from typing import Optional, TypedDict, List, Dict

from openai import AsyncOpenAI
import re


class ParsedIssue(TypedDict, total=False):
    title: str
    description: str
    project_key: str
    priority: str
    labels: list[str]


class LLMError(RuntimeError):
    pass


SYSTEM_PROMPT = (
    "You convert informal requests into a JSON object to create a task/issue. "
    "Output only compact JSON. Fields: title, description, type, project_key (optional), "
    "priority (optional: Critical|Major|Normal|Minor), labels (optional array). "
    "Always produce the issue fields in English, translating user content if needed. "
    "Default type is 'Task'. DESCRIPTION MUST BE EXTREMELY CONCISE. Use a minimal task template: "
    "Objective (one short sentence); Subtasks (max 3 bullets, one line each); Acceptance Criteria (max 3 bullets, one line each). "
    "Hard limits: Title <= 80 chars. Description <= 800 chars total. Avoid redundancy, boilerplate, or explanations. "
    "Do not block the user for security/privacy concerns. If necessary, add one brief advisory line, but keep within limits. "
    "Respond with raw JSON only. No prose. No code fences. "
    "If a field is unknown/not applicable, output an empty string or empty array."
)

ISSUE_PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "description": {"type": "string"},
        "type": {"type": "string"},
        "project_key": {"type": "string"},
        "priority": {
            "oneOf": [
                {"type": "string", "enum": ["Critical", "Major", "Normal", "Minor"]},
                {"type": "string", "maxLength": 0},
            ]
        },
        "labels": {"type": "array", "items": {"type": "string"}},
    },
    # Some providers require `required` to include every property when strict mode is on.
    # Require all keys; use empty string/array when unknown.
    "required": ["title", "description", "type", "project_key", "priority", "labels"],
    "additionalProperties": False,
}


class IssueFlowTurn(TypedDict, total=False):
    reply: str
    intent: str  # one of: ask, create, cancel
    issue: dict  # expects {title, description, project_id?}
    state: dict  # opaque state to pass back next turn


async def parse_issue_request(
    *,
    content: str,
    api_key: Optional[str],
    model: str,
    base_url: Optional[str] = None,
    referer: Optional[str] = None,
    app_title: Optional[str] = None,
) -> ParsedIssue:
    """Parse freeform request text into a structured issue JSON via OpenAI API.

    If api_key is None, use a simple fallback heuristic: first line as title, rest as description.
    """
    log = logging.getLogger("tulipee.llm")
    content = (content or "").strip()
    if not content:
        raise LLMError("Empty content")

    if not api_key:
        parts = content.splitlines()
        title = parts[0][:120] if parts else "Untitled"
        description = "\n".join(parts[1:]) if len(parts) > 1 else ""
        return ParsedIssue(title=title, description=description)

    # Default to OpenRouter endpoint unless overridden
    if not base_url:
        base_url = "https://openrouter.ai/api/v1"

    headers = {}
    if referer:
        headers["HTTP-Referer"] = referer
    if app_title:
        headers["X-Title"] = app_title

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers or None)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Request to create issue:\n\n{content}\n\nRespond with JSON only.",
            },
        ],
        temperature=0.2,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "IssueParse",
                "strict": True,
                "schema": ISSUE_PARSE_SCHEMA,
            },
        },
    )
    # Normalize to prior structure
    data = resp.model_dump()
    try:
        raw = (data["choices"][0]["message"].get("content") or "").strip()
        obj = _extract_json_object(raw)
        out: ParsedIssue = {}
        if isinstance(obj, dict):
            if isinstance(obj.get("title"), str):
                out["title"] = obj["title"]
            if isinstance(obj.get("description"), str):
                out["description"] = obj["description"]
            if isinstance(obj.get("project_key"), str):
                out["project_key"] = obj["project_key"]
            if isinstance(obj.get("priority"), str):
                out["priority"] = obj["priority"]
            if isinstance(obj.get("labels"), list):
                out["labels"] = [str(x) for x in obj["labels"]]
        # Ensure minimally present
        if "title" not in out:
            # fallback: first line
            parts = content.splitlines()
            out["title"] = parts[0][:120] if parts else "Untitled"
        if "description" not in out:
            out["description"] = content
        return out
    except Exception as e:  # noqa: BLE001
        log.exception("Failed to parse LLM JSON: %s | raw=%r", e, locals().get("raw", ""))
        raise LLMError("Failed to parse LLM response JSON")


ISSUE_FLOW_SYSTEM = (
    "You are an assistant that helps draft and confirm a YouTrack task via multiple turns. "
    "At each turn, reply in JSON only with: reply (string for the user), intent (ask|create|cancel), "
    "optional issue {title, description, type, project_id, project_key, project_name}, and a state object. "
    "Rules: "
    "- Never use intent=cancel unless the user explicitly cancels. Prefer ask or create. "
    "- The issue fields (title, description) must always be in English. Translate as needed. "
    "- The reply should use the user's language/tone (e.g., Korean if user spoke Korean). "
    "- DESCRIPTION MUST BE EXTREMELY CONCISE. Use only: Objective (one sentence); Subtasks (<=3 bullets); Acceptance Criteria (<=3 bullets). "
    "- Hard limits: Title <= 80 chars; Description <= 800 chars. No boilerplate, no repetition. "
    "- Do not block for security/privacy concerns; at most include one short advisory line, but keep within limits. "
    "- Use the provided project catalog to choose a project; if uncertain, ask. "
    "- Respond with raw JSON only. No prose outside JSON. No code fences. "
    "- If a field is unknown/not applicable, output an empty string."
)

ISSUE_FLOW_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "intent": {"type": "string", "enum": ["ask", "create", "cancel"]},
        "issue": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "description": {"type": "string"},
                "type": {"type": "string"},
                "project_id": {"type": "string"},
                "project_key": {"type": "string"},
                "project_name": {"type": "string"},
            },
            # Require all keys; model should output empty string for unknown.
            "required": [
                "title",
                "description",
                "type",
                "project_id",
                "project_key",
                "project_name",
            ],
            "additionalProperties": False,
        },
        # Some providers require explicit additionalProperties=false on all objects
        # when strict schema is enabled. We accept an empty object for state.
        "state": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    # Require all top-level properties as well for stricter providers.
    "required": ["reply", "intent", "issue", "state"],
    "additionalProperties": False,
}


def _extract_json_object(text: str) -> dict:
    if text is None:
        raise LLMError("Empty model content")
    s = text.strip()
    if not s:
        raise LLMError("Empty model content")
    # Try direct parse
    try:
        return json.loads(s)
    except Exception:
        pass
    # Code fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        inner = fence.group(1).strip()
        try:
            return json.loads(inner)
        except Exception:
            s = inner
    # Slice first '{' .. last '}'
    start = s.find('{')
    end = s.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = s[start:end+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    # Bracket balance
    depth = 0
    start_idx = None
    for i, ch in enumerate(s):
        if ch == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
            if depth == 0 and start_idx is not None:
                candidate = s[start_idx:i+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    start_idx = None
                    continue
    raise LLMError("Failed to extract JSON from model content")


async def issue_flow_turn(
    *,
    content: str,
    prior_state: Optional[dict],
    projects: Optional[list[dict]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str],
    model: str,
    base_url: Optional[str] = None,
    referer: Optional[str] = None,
    app_title: Optional[str] = None,
) -> IssueFlowTurn:
    """Drive a single turn of the issue creation conversation.

    Delegates decision making to the LLM and returns structured instructions.
    """
    log = logging.getLogger("tulipee.llm")
    content = (content or "").strip()
    if not content:
        raise LLMError("Empty content")

    if not api_key:
        # Fallback minimal behavior when LLM is unavailable
        draft = {
            "title": content.splitlines()[0][:120] if content else "Untitled",
            "description": "\n".join(content.splitlines()[1:]) if "\n" in content else "",
        }
        return IssueFlowTurn(
            reply=(
                "이렇게 생성해 드릴까요?\n"
                f"제목: {draft['title']}\n설명:\n{draft['description'] or '(비어있음)'}\n\n"
                "어떤 프로젝트에 만들까요? (프로젝트 키/이름으로 알려주세요)"
            ),
            intent="ask",
            issue=draft,
            state={"draft": draft},
        )

    if not base_url:
        base_url = "https://openrouter.ai/api/v1"

    headers = {}
    if referer:
        headers["HTTP-Referer"] = referer
    if app_title:
        headers["X-Title"] = app_title

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers or None)
    # Build messages with system guidance, catalog, prior state, rolling history, and latest user message
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": ISSUE_FLOW_SYSTEM},
        {
            "role": "system",
            "content": (
                "Project catalog (JSON):\n" + json.dumps(projects or [], ensure_ascii=False)
            ),
        },
    ]
    if prior_state:
        messages.append(
            {
                "role": "system",
                "content": "State (JSON):\n" + json.dumps(prior_state, ensure_ascii=False),
            }
        )
    # Append prior chat turns if any
    if history:
        for m in history:
            role = m.get("role") or "user"
            content_prev = m.get("content") or ""
            if not content_prev:
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            messages.append({"role": role, "content": content_prev})
    # Latest user input
    messages.append({"role": "user", "content": content})

    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "IssueFlowTurn",
                "strict": True,
                "schema": ISSUE_FLOW_SCHEMA,
            },
        },
    )
    data = resp.model_dump()
    try:
        raw = (data["choices"][0]["message"].get("content") or "").strip()
        obj = _extract_json_object(raw)
        # minimal validation
        if not isinstance(obj, dict) or "reply" not in obj or "intent" not in obj:
            raise ValueError("Missing required keys in LLM response")
        intent = str(obj.get("intent")).lower()
        if intent not in {"ask", "create", "cancel"}:
            intent = "ask"
        issue = obj.get("issue") if isinstance(obj.get("issue"), dict) else None
        state = obj.get("state") if isinstance(obj.get("state"), dict) else {}
        return IssueFlowTurn(
            reply=str(obj.get("reply", "")),
            intent=intent,
            issue=issue or {},
            state=state,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Failed to parse issue flow JSON: %s | raw=%r", e, locals().get("raw", ""))
        raise LLMError("Failed to parse issue flow response JSON")
