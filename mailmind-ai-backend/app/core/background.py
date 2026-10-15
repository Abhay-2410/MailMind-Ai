"""Fire-and-forget work that survives serverless request lifecycles.

Locally a spawned task simply runs on the long-lived event loop. On Vercel an instance
may be suspended once its request finishes, so DrainBackgroundTasksMiddleware keeps the
ASGI call open (after the response has been sent) until that request's spawned tasks
finish or the drain budget runs out.
"""

import asyncio
import logging
import time
from collections.abc import Coroutine
from contextvars import ContextVar
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Stay under the 300s function limit, counted from the start of the request.
DRAIN_BUDGET_SECONDS = 270.0

_request_tasks: ContextVar[list[asyncio.Task[Any]] | None] = ContextVar("_request_tasks", default=None)
_detached: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro)
    _detached.add(task)
    task.add_done_callback(_detached.discard)
    tracked = _request_tasks.get()
    if tracked is not None:
        tracked.append(task)
    return task


class DrainBackgroundTasksMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        tasks: list[asyncio.Task[Any]] = []
        token = _request_tasks.set(tasks)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_tasks.reset(token)

        while True:
            pending = [task for task in tasks if not task.done()]
            remaining = DRAIN_BUDGET_SECONDS - (time.monotonic() - started)
            if not pending:
                return
            if remaining <= 0:
                logger.warning("%s background task(s) still running at the drain budget", len(pending))
                return
            await asyncio.wait(pending, timeout=remaining)
