from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections import defaultdict
from contextlib import suppress
from typing import Any, Awaitable, Callable

from fastapi import WebSocket

from database.config.config import settings


UserEventTransformer = Callable[[str, dict], dict]
UserEventHook = Callable[[str, dict], Awaitable[None] | None]


class ConnectionManager:
    """WebSocket channel registry with durable database fallbacks.

    Redis is used only for cross-worker event fan-out. Notifications, messages,
    files and reports remain persisted in PostgreSQL/media storage.
    """

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)
        self.user_connection_counts: dict[str, int] = defaultdict(int)
        self.client_connections: dict[tuple[str, str], WebSocket] = {}
        self.instance_id = uuid.uuid4().hex
        self.redis: Any | None = None
        self.pubsub: Any | None = None
        self.listener_task: asyncio.Task | None = None
        self.user_event_transformer: UserEventTransformer | None = None
        self.user_event_hook: UserEventHook | None = None

    def set_user_event_transformer(
        self,
        transformer: UserEventTransformer | None,
    ) -> None:
        self.user_event_transformer = transformer

    def set_user_event_hook(self, hook: UserEventHook | None) -> None:
        """Install one optional side-channel for user events (for example push).

        The hook runs only on the worker that originates an event. Redis replicas
        deliver the same event locally without re-running the side-channel, so a
        multi-worker deployment does not duplicate push notifications.
        """

        self.user_event_hook = hook

    async def start(self) -> None:
        if not settings.REDIS_URL or self.redis is not None:
            return
        try:
            from redis.asyncio import Redis

            self.redis = Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe(settings.REDIS_REALTIME_CHANNEL)
            self.listener_task = asyncio.create_task(self._listen_for_events())
        except Exception:
            self.redis = None
            self.pubsub = None

    async def shutdown(self) -> None:
        if self.listener_task:
            self.listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.listener_task
            self.listener_task = None
        if self.pubsub:
            with suppress(Exception):
                await self.pubsub.unsubscribe(settings.REDIS_REALTIME_CHANNEL)
                await self.pubsub.close()
            self.pubsub = None
        if self.redis:
            with suppress(Exception):
                await self.redis.aclose()
            self.redis = None

    async def _listen_for_events(self) -> None:
        if not self.pubsub:
            return
        async for message in self.pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                envelope = json.loads(message["data"])
                if envelope.get("origin") == self.instance_id:
                    continue
                channel = str(envelope["channel"])
                payload = envelope["payload"]
                if isinstance(payload, dict):
                    await self._send_local(channel, payload)
            except Exception:
                continue

    async def register_client(
        self,
        user_id: str,
        client_id: str,
        websocket: WebSocket,
    ) -> None:
        key = (user_id, client_id)
        previous = self.client_connections.get(key)
        self.client_connections[key] = websocket

        if previous and previous is not websocket:
            with suppress(Exception):
                await previous.close(
                    code=4000,
                    reason="Replaced by a newer connection",
                )

    def unregister_client(
        self,
        user_id: str,
        client_id: str,
        websocket: WebSocket,
    ) -> None:
        key = (user_id, client_id)
        if self.client_connections.get(key) is websocket:
            self.client_connections.pop(key, None)

    def subscribe(self, channel: str, websocket: WebSocket) -> None:
        connections = self.active_connections[channel]
        if websocket not in connections:
            connections.append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        connections = self.active_connections.get(channel)
        if not connections:
            return
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(channel, None)

    def disconnect_all(self, websocket: WebSocket) -> None:
        for channel in list(self.active_connections):
            self.disconnect(channel, websocket)

    def user_connected(self, user_id: str) -> bool:
        previous = self.user_connection_counts[user_id]
        self.user_connection_counts[user_id] = previous + 1
        return previous == 0

    def user_disconnected(self, user_id: str) -> bool:
        current = self.user_connection_counts.get(user_id, 0)
        if current <= 1:
            self.user_connection_counts.pop(user_id, None)
            return current > 0
        self.user_connection_counts[user_id] = current - 1
        return False

    def is_user_online(self, user_id: str) -> bool:
        return self.user_connection_counts.get(user_id, 0) > 0

    async def _send_local(self, channel: str, data: dict) -> None:
        connections = list(self.active_connections.get(channel, []))
        if not connections:
            return
        message = json.dumps(data, default=str)
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(channel, connection)

    @staticmethod
    def _typed_event(data: dict) -> dict:
        event = dict(data)
        event.setdefault("event_id", str(uuid.uuid4()))
        if not event.get("domain"):
            event_type = str(event.get("type") or "")
            if event_type.startswith("CHAT_"):
                event["domain"] = "chat"
            elif event_type.startswith("MONEY_") or event_type.startswith("PAYMENT_"):
                event["domain"] = "money"
            elif "CALL" in event_type:
                event["domain"] = "call"
            elif event_type.startswith("PRESENCE_"):
                event["domain"] = "presence"
            else:
                event["domain"] = "system"
        return event

    async def _publish_channel(self, channel: str, event: dict) -> None:
        await self._send_local(channel, event)
        if not self.redis:
            return
        try:
            await self.redis.publish(
                settings.REDIS_REALTIME_CHANNEL,
                json.dumps(
                    {
                        "origin": self.instance_id,
                        "channel": channel,
                        "payload": event,
                    },
                    default=str,
                ),
            )
        except Exception:
            pass

    async def send_to_channel(self, channel: str, data: dict) -> None:
        await self._publish_channel(channel, self._typed_event(data))

    async def send_to_user(self, user_id: str, data: dict) -> None:
        event = self._typed_event(data)
        if self.user_event_transformer:
            event = self.user_event_transformer(user_id, event)
        await self._publish_channel(f"user-{user_id}", event)
        if self.user_event_hook:
            result = self.user_event_hook(user_id, event)
            if inspect.isawaitable(result):
                await result

    async def broadcast(self, data: dict) -> None:
        event = self._typed_event(data)
        for channel in list(self.active_connections):
            await self._publish_channel(channel, event)


manager = ConnectionManager()
