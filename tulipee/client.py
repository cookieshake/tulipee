import logging
import httpx
from pydantic import BaseModel, Field

from typing import AsyncGenerator, Optional, List, Union, Literal


class UserRecipient(BaseModel):
    id: int
    email: str
    full_name: str
    is_mirror_dummy: bool


class TopicLink(BaseModel):
    text: str
    url: str


class Reaction(BaseModel):
    emoji_code: str
    emoji_name: str
    reaction_type: str
    user_id: int


class Submessage(BaseModel):
    id: int
    msg_type: str
    content: str
    message_id: int
    sender_id: int


class EditHistoryEntry(BaseModel):
    # Always includes timestamp and user_id (can be null for very old edits)
    timestamp: int
    user_id: Optional[int] = None
    # Optional fields depending on what changed in the edit
    prev_content: Optional[str] = None
    prev_rendered_content: Optional[str] = None
    prev_stream: Optional[int] = None
    prev_topic: Optional[str] = None
    stream: Optional[int] = None
    topic: Optional[str] = None


class Message(BaseModel):
    id: int
    type: Literal["stream", "private"]
    client: str
    content: str
    content_type: str
    display_recipient: Union[str, List[UserRecipient]]
    avatar_url: Optional[str] = None
    edit_history: Optional[List[EditHistoryEntry]] = None
    is_me_message: bool = False
    last_edit_timestamp: Optional[int] = None
    last_moved_timestamp: Optional[int] = None
    reactions: List[Reaction] = Field(default_factory=list)
    recipient_id: int
    sender_email: str
    sender_full_name: str
    sender_id: int
    sender_realm_str: str
    stream_id: Optional[int] = None
    subject: str
    submessages: List[Submessage] = Field(default_factory=list)
    timestamp: int
    topic_links: List[TopicLink] = Field(default_factory=list)


class MessageEvent(BaseModel):
    id: int
    type: Literal["message"]
    message: Message
    flags: List[str] = Field(default_factory=list)


class QueueStatus(BaseModel):
    queue_id: str
    event_queue_longpoll_timeout_seconds: int
    last_event_id: int


class ZulipClient:
    def __init__(self, zulip_url: str, api_key: str, email: str):
        self.zulip_url = zulip_url
        self.api_key = api_key
        self.email = email
        self._log = logging.getLogger("tulipee.client")
        self.client = httpx.AsyncClient(
            base_url=self.zulip_url + "/api/v1", auth=(self.email, self.api_key)
        )
        self._queue_status: Optional[QueueStatus] = None

    async def _register_queue(self) -> QueueStatus:
        self._log.debug("Registering event queue at %s/register", self.zulip_url)
        response = await self.client.post(
            "/register",
            data={
                "event_types": '["message"]',
                "all_public_streams": True
            }
        )
        if response.status_code != 200:
            self._log.error("Queue registration failed: %s %s", response.status_code, response.text)
            raise ValueError(f"Failed to register queue: {response.text}")
        data = response.json()
        self._log.info("Registered queue_id=%s last_event_id=%s", data.get("queue_id"), data.get("last_event_id"))
        return QueueStatus(
            queue_id=data["queue_id"],
            event_queue_longpoll_timeout_seconds=90,
            last_event_id=data["last_event_id"]
        )

    async def _get_queue_status(self) -> QueueStatus:
        if self._queue_status is None:
            self._queue_status = await self._register_queue()
        return self._queue_status

    async def send_message_to_stream(
        self,
        stream: Union[int, str],
        topic: str,
        content: str,
    ) -> None:
        self._log.debug(
            "Sending message to stream=%s topic=%s content_len=%s",
            stream,
            topic,
            len(content or ""),
        )
        response = await self.client.post(
            "/messages",
            data={
                "type": "stream",
                "to": stream,
                "topic": topic,
                "content": content
            }
        )
        if response.status_code != 200:
            self._log.error(
                "Send failed status=%s body=%s", response.status_code, response.text
            )
            raise ValueError(f"[{response.status_code}] Failed to send message: {response.text}")
        self._log.debug("Send OK status=%s", response.status_code)

    async def stream_messages(self) -> AsyncGenerator[Message]:
        queue_status = await self._get_queue_status()
        while True:
            self._log.debug(
                "Long-poll /events queue_id=%s last_event_id=%s timeout=%s",
                queue_status.queue_id,
                queue_status.last_event_id,
                queue_status.event_queue_longpoll_timeout_seconds,
            )
            response = await self.client.get(
                "/events",
                timeout=queue_status.event_queue_longpoll_timeout_seconds,
                params={
                    "queue_id": queue_status.queue_id,
                    "last_event_id": queue_status.last_event_id
                }
            )
            if response.status_code != 200:
                self._log.error(
                    "Events poll failed status=%s body=%s", response.status_code, response.text
                )
                raise ValueError(f"[{response.status_code}] Failed to retrieve events: {response.text}")
            data = response.json()
            max_event_id = queue_status.last_event_id
            for event in data["events"]:
                if event["type"] == "message":
                    max_event_id = max(max_event_id, event["id"])
                    msg = Message.model_validate(event["message"])
                    self._log.debug(
                        "Yield message id=%s stream_id=%s subject=%s sender=%s",
                        msg.id,
                        msg.stream_id,
                        msg.subject,
                        msg.sender_email,
                    )
                    yield msg
            self._queue_status.last_event_id = max_event_id
