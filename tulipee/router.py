from typing import Awaitable, Callable, List, Optional, Union, Literal

from dataclasses import dataclass

from tulipee.client import Message
from tulipee.settings import Settings
from tulipee.client import ZulipClient


class Context:
    def __init__(self, message: Message, settings: Settings, client: ZulipClient):
        self.message = message
        self.settings = settings
        self.client = client


Predicate = Callable[[Message, Settings], bool]
Handler = Callable[[Context], Awaitable[None]]


class Router:
    def __init__(self):
        self._routes: List[tuple[List[Predicate], Handler]] = []

    def add_route(self, predicates: List[Predicate], handler: Handler) -> None:
        self._routes.append((predicates, handler))

    async def dispatch(self, message: Message, settings: Settings, client: "ZulipClient") -> bool:
        ctx = Context(message, settings, client)
        for predicates, handler in self._routes:
            if all(pred(message, settings) for pred in predicates):
                await handler(ctx)
                return True
        return False


# Common predicates
def is_stream_message(msg: Message, _: Settings) -> bool:
    return msg.type == "stream" and msg.stream_id is not None


def topic_in(topics: List[str]) -> Predicate:
    lowered = {t.lower() for t in topics}

    def _pred(msg: Message, _: Settings) -> bool:
        return msg.subject.lower() in lowered

    return _pred


def stream_in(stream_ids: Optional[List[int]]) -> Predicate:
    def _pred(msg: Message, _: Settings) -> bool:
        if stream_ids is None:
            return True
        return msg.stream_id in stream_ids

    return _pred


def content_startswith_any(
    prefixes: Union[List[str], Callable[[Settings], List[str]]]
) -> Predicate:
    def _pred(msg: Message, settings: Settings) -> bool:
        content = (msg.content or "").lstrip()
        pref_list = prefixes(settings) if callable(prefixes) else prefixes
        return any(content.startswith(p) for p in pref_list)

    return _pred


def stream_name_in(names: List[str]) -> Predicate:
    lowered = {n.lower() for n in names}

    def _pred(msg: Message, _: Settings) -> bool:
        # For stream messages, Zulip sets display_recipient to the stream name (str)
        name: Union[str, List] = msg.display_recipient  # type: ignore[assignment]
        return isinstance(name, str) and name.lower() in lowered

    return _pred
def is_private_message(msg: Message, _: Settings) -> bool:
    return msg.type == "private"



# Declarative routing (FastAPI-like)
@dataclass
class RouteSpec:
    predicates: List[Predicate]
    handler: Handler


_route_registry: List[RouteSpec] = []


def route(
    *,
    stream: Optional[Union[str, List[str]]] = None,
    topic: Optional[Union[str, List[str]]] = None,
    stream_id: Optional[Union[int, List[int]]] = None,
    msg_type: Optional[Literal["stream", "private"]] = None,
    when: Optional[Predicate] = None,
) -> Callable[[Handler], Handler]:
    """Decorator to register a handler with simple conditions.

    Example:
        @route(stream="general", topic="global chat")
        async def handler(ctx: Context): ...
    """

    streams_list: Optional[List[str]]
    topics_list: Optional[List[str]]
    ids_list: Optional[List[int]]

    if isinstance(stream, str):
        streams_list = [stream]
    else:
        streams_list = stream

    if isinstance(topic, str):
        topics_list = [topic]
    else:
        topics_list = topic

    if isinstance(stream_id, int):
        ids_list = [stream_id]
    else:
        ids_list = stream_id

    def _decorator(handler: Handler) -> Handler:
        preds: List[Predicate] = []
        if msg_type == "stream" or streams_list is not None or ids_list is not None:
            preds.append(is_stream_message)
        if msg_type == "private":
            preds.append(is_private_message)
        if streams_list:
            preds.append(stream_name_in(streams_list))
        if topics_list:
            preds.append(topic_in(topics_list))
        if ids_list is not None:
            preds.append(stream_in(ids_list))
        if when is not None:
            preds.append(when)
        _route_registry.append(RouteSpec(predicates=preds, handler=handler))
        return handler

    return _decorator


def mount_registered_routes(router: Router) -> None:
    for spec in _route_registry:
        router.add_route(spec.predicates, spec.handler)
