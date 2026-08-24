"""A2A AgentExecutor that runs GrokAgent for each task."""

from __future__ import annotations

import asyncio

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from grok_a2a.agent import GrokAgent

_TERMINAL_STATES = {
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_REJECTED,
}


class GrokAgentExecutor(AgentExecutor):
    """Execute inbound A2A tasks via Grok."""

    def __init__(self, agent: GrokAgent | None = None) -> None:
        self.agent = agent or GrokAgent()
        self._inflight: dict[str, asyncio.Event] = {}
        self._end_lock = asyncio.Lock()
        self._ended: set[str] = set()

    async def _claim_end(self, task_id: str) -> bool:
        async with self._end_lock:
            if task_id in self._ended:
                return False
            self._ended.add(task_id)
            return True

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        abort = asyncio.Event()
        self._inflight[task.id] = abort
        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        try:
            await updater.update_status(
                state=TaskState.TASK_STATE_WORKING,
                message=new_text_message("Calling Grok…"),
            )

            query = get_message_text(context.message)
            try:
                result = await self.agent.invoke(
                    user_request=query or "", abort=abort
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — surface to A2A client
                if abort.is_set() or not await self._claim_end(task.id):
                    return
                await updater.update_status(
                    state=TaskState.TASK_STATE_FAILED,
                    message=new_text_message(f"Grok A2A failed: {exc}"),
                )
                return

            if abort.is_set():
                return
            if not await self._claim_end(task.id):
                return
            if abort.is_set():
                await updater.update_status(
                    state=TaskState.TASK_STATE_CANCELED,
                    message=new_text_message("Canceled."),
                )
                return

            await updater.add_artifact(
                parts=[new_text_part(text=result, media_type="text/plain")]
            )
            await updater.update_status(
                state=TaskState.TASK_STATE_COMPLETED,
                message=new_text_message("Done."),
            )
        finally:
            self._inflight.pop(task.id, None)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        if task_id:
            abort = self._inflight.get(task_id)
            if abort is not None:
                abort.set()

        task = context.current_task
        if task is not None and task.status.state in _TERMINAL_STATES:
            return

        cancel_task_id = (task.id if task else None) or task_id
        context_id = (task.context_id if task else None) or context.context_id
        if not cancel_task_id or not context_id:
            return

        if not await self._claim_end(cancel_task_id):
            return

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=cancel_task_id,
            context_id=context_id,
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_CANCELED,
            message=new_text_message("Canceled."),
        )
