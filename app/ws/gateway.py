
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class Broker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, run_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(run_id, ()))
        for q in queues:
            if q.qsize() < 1000:
                q.put_nowait(message)

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers[run_id].add(q)
        return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers[run_id].discard(q)
            if not self._subscribers[run_id]:
                self._subscribers.pop(run_id, None)


broker = Broker()


@router.websocket("/ws/runs/{run_id}")
async def run_stream(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    queue = await broker.subscribe(run_id)
    try:
        await websocket.send_json({"type": "connected", "run_id": run_id})
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await broker.unsubscribe(run_id, queue)
