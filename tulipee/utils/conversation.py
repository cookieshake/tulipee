from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List


@dataclass
class IssueDraft:
    title: str
    description: str
    project_id: Optional[str] = None
    created_ts: float = field(default_factory=lambda: time.time())

    def render_preview(self) -> str:
        lines = [
            f"제목: {self.title}",
            f"프로젝트 ID: {self.project_id or '(미설정)'}",
            "설명:",
        ]
        desc = self.description.strip() or "(비어있음)"
        lines.append(desc)
        return "\n".join(lines)


class ConversationStore:
    def __init__(self, ttl_seconds: int = 1800):
        self._store: Dict[Tuple[str, int, str, int], IssueDraft] = {}
        self._ttl = ttl_seconds

    @staticmethod
    def _key(kind: str, stream_id: int, subject: str, sender_id: int) -> Tuple[str, int, str, int]:
        return (kind, stream_id, subject.lower(), sender_id)

    def _gc(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.created_ts > self._ttl]
        for k in expired:
            self._store.pop(k, None)

    def get(self, *, stream_id: int, subject: str, sender_id: int) -> Optional[IssueDraft]:
        self._gc()
        return self._store.get(self._key("stream", stream_id, subject, sender_id))

    def set(self, *, stream_id: int, subject: str, sender_id: int, draft: IssueDraft) -> None:
        self._gc()
        self._store[self._key("stream", stream_id, subject, sender_id)] = draft

    def clear(self, *, stream_id: int, subject: str, sender_id: int) -> None:
        self._store.pop(self._key("stream", stream_id, subject, sender_id), None)


# Module-level singleton
store = ConversationStore()


class FlowStore:
    """Generic JSON-like state store for multi-turn LLM flows."""

    def __init__(self, ttl_seconds: int = 1800):
        self._store: Dict[Tuple[str, int, str, int], dict] = {}
        self._ttl = ttl_seconds

    @staticmethod
    def _key(kind: str, stream_id: int, subject: str, sender_id: int) -> Tuple[str, int, str, int]:
        return (kind, stream_id, subject.lower(), sender_id)

    def _gc(self) -> None:
        now = time.time()
        # Best-effort GC using a parallel timestamp map is overkill; use draft-like heuristic
        # We piggyback on a simple embedded timestamp if present; else keep state.
        # For simplicity, skip GC here; store remains small in typical usage.
        return

    def get(self, *, stream_id: int, subject: str, sender_id: int) -> Optional[dict]:
        self._gc()
        return self._store.get(self._key("flow", stream_id, subject, sender_id))

    def set(self, *, stream_id: int, subject: str, sender_id: int, state: dict) -> None:
        self._gc()
        self._store[self._key("flow", stream_id, subject, sender_id)] = state

    def clear(self, *, stream_id: int, subject: str, sender_id: int) -> None:
        self._store.pop(self._key("flow", stream_id, subject, sender_id), None)


flow_store = FlowStore()


class ChatHistoryStore:
    """In-memory chat history per (stream, subject, sender).

    Stores a rolling window of role/content messages for the LLM.
    """

    def __init__(self, max_messages: int = 16):
        self._store: Dict[Tuple[str, int, str, int], List[dict]] = {}
        self._max = max_messages

    @staticmethod
    def _key(stream_id: int, subject: str, sender_id: int) -> Tuple[str, int, str, int]:
        return ("chat", stream_id, subject.lower(), sender_id)

    def get(self, *, stream_id: int, subject: str, sender_id: int) -> List[dict]:
        return list(self._store.get(self._key(stream_id, subject, sender_id), []))

    def append(self, *, stream_id: int, subject: str, sender_id: int, role: str, content: str) -> None:
        k = self._key(stream_id, subject, sender_id)
        hist = self._store.get(k)
        if hist is None:
            hist = []
            self._store[k] = hist
        hist.append({"role": role, "content": content})
        if len(hist) > self._max:
            del hist[: len(hist) - self._max]

    def clear(self, *, stream_id: int, subject: str, sender_id: int) -> None:
        self._store.pop(self._key(stream_id, subject, sender_id), None)


chat_history = ChatHistoryStore()
