from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable


class EventBus:
    """Publica eventos síncronos sem acoplar produtores e ouvintes."""

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, listener: Callable):
        if listener not in self._listeners[event_name]:
            self._listeners[event_name].append(listener)

    def unsubscribe(self, event_name: str, listener: Callable):
        if listener in self._listeners[event_name]:
            self._listeners[event_name].remove(listener)

    def emit(self, event_name: str, payload: dict) -> list[Exception]:
        errors = []
        for listener in tuple(self._listeners[event_name]):
            try:
                listener(payload)
            except Exception as error:
                errors.append(error)
        return errors

    def listeners(self, event_name: str) -> tuple[Callable, ...]:
        return tuple(self._listeners[event_name])
