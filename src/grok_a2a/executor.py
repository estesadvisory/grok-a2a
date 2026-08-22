"""A2A AgentExecutor that runs GrokAgent for each task."""

from __future__ import annotations

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


class GrokAgentExecutor(AgentExecutor):
    """Execute inbound A2A tasks via Grok."""

    def __init__(self, agent: GrokAgent | None = None) -> None:
        self.agent = agent or GrokAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue, task_id=task.id, context_id=task.context_id
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Calling Grok…"),
        )

        query = get_message_text(context.message)
        try:
            result = await self.agent.invoke(user_request=query or "")
        except Exception as exc:  # noqa: BLE001 — surface to A2A client
            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(f"Grok A2A failed: {exc}"),
            )
            return

        await updater.add_artifact(
            parts=[new_text_part(text=result, media_type="text/plain")]
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Done."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel is not supported in grok-a2a v0.1.")
