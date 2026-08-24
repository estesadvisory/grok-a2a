"""Cancel in-flight tasks (no live xAI calls)."""

from __future__ import annotations

import asyncio
import unittest
import warnings

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette.testclient` is deprecated",
)

from a2a.helpers import new_text_message
from a2a.server.agent_execution import RequestContext
from a2a.server.context import ServerCallContext
from a2a.types import (
    Role,
    SendMessageRequest,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from httpx import ASGITransport, AsyncClient

from grok_a2a.agent import GrokAgent
from grok_a2a.executor import GrokAgentExecutor
from grok_a2a.server import create_app


class FakeQueue:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def enqueue_event(self, event: object) -> None:
        self.events.append(event)


class HangingAgent:
    """Stays in invoke until abort is set or the coroutine is cancelled."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.finished = False
        self.stopped = False

    async def invoke(
        self,
        user_request: str,
        *,
        abort: asyncio.Event | None = None,
    ) -> str:
        self.started.set()
        try:
            if abort is not None:
                await abort.wait()
                raise asyncio.CancelledError
            await asyncio.sleep(30)
            self.finished = True
            return f"late:{user_request}"
        except asyncio.CancelledError:
            self.stopped = True
            raise


def _context(task_id: str = "task-1", context_id: str = "ctx-1") -> RequestContext:
    message = new_text_message("hello", role=Role.ROLE_USER)
    message.task_id = task_id
    message.context_id = context_id
    task = Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
    )
    return RequestContext(
        call_context=ServerCallContext(),
        request=SendMessageRequest(message=message),
        task_id=task_id,
        context_id=context_id,
        task=task,
    )


def _canceled_states(queue: FakeQueue) -> list[TaskState]:
    states: list[TaskState] = []
    for event in queue.events:
        if isinstance(event, TaskStatusUpdateEvent):
            states.append(event.status.state)
    return states


class ExecutorCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_marks_canceled_and_stops_invoke(self) -> None:
        agent = HangingAgent()
        executor = GrokAgentExecutor(agent=agent)
        queue = FakeQueue()
        ctx = _context()

        exec_task = asyncio.create_task(executor.execute(ctx, queue))
        await asyncio.wait_for(agent.started.wait(), timeout=2)
        await executor.cancel(ctx, queue)
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(exec_task, timeout=2)

        self.assertTrue(agent.stopped)
        self.assertFalse(agent.finished)
        self.assertIn(TaskState.TASK_STATE_CANCELED, _canceled_states(queue))
        self.assertNotIn(TaskState.TASK_STATE_COMPLETED, _canceled_states(queue))
        self.assertNotIn(TaskState.TASK_STATE_FAILED, _canceled_states(queue))

    async def test_cancel_after_producer_cancel_still_marks_canceled(self) -> None:
        """SDK cancels execute() first, then calls AgentExecutor.cancel()."""
        agent = HangingAgent()
        executor = GrokAgentExecutor(agent=agent)
        queue = FakeQueue()
        ctx = _context()

        exec_task = asyncio.create_task(executor.execute(ctx, queue))
        await asyncio.wait_for(agent.started.wait(), timeout=2)
        exec_task.cancel()
        await executor.cancel(ctx, queue)
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(exec_task, timeout=2)

        self.assertTrue(agent.stopped)
        self.assertIn(TaskState.TASK_STATE_CANCELED, _canceled_states(queue))

    async def test_cancel_of_terminal_task_is_noop(self) -> None:
        executor = GrokAgentExecutor(agent=GrokAgent(dry_run=True))
        queue = FakeQueue()
        ctx = _context()
        ctx.current_task.status.state = TaskState.TASK_STATE_COMPLETED
        await executor.cancel(ctx, queue)
        self.assertEqual(queue.events, [])

    async def test_dry_run_execute_still_completes(self) -> None:
        executor = GrokAgentExecutor(agent=GrokAgent(dry_run=True))
        queue = FakeQueue()
        ctx = _context()
        await executor.execute(ctx, queue)
        self.assertIn(TaskState.TASK_STATE_COMPLETED, _canceled_states(queue))


class _HangServer:
    """Local TCP server that accepts one HTTP client and never replies."""

    def __init__(self) -> None:
        self.accepted = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.server: asyncio.Server | None = None
        self.base: str = ""

    async def start(self) -> None:
        async def _client_connected(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            self.accepted.set()
            try:
                await reader.read()
            except (ConnectionError, asyncio.IncompleteReadError, asyncio.CancelledError):
                pass
            finally:
                self.disconnected.set()
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionError:
                    pass

        self.server = await asyncio.start_server(_client_connected, "127.0.0.1", 0)
        host, port = self.server.sockets[0].getsockname()[:2]
        self.base = f"http://{host}:{port}"

    async def aclose(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class AgentAbortTests(unittest.IsolatedAsyncioTestCase):
    async def _hanging_agent(self) -> tuple[_HangServer, GrokAgent]:
        hang = _HangServer()
        await hang.start()
        agent = GrokAgent(
            api_key="test-key",
            api_base=hang.base,
            dry_run=False,
            timeout_s=10.0,
        )
        return hang, agent

    async def test_invoke_aborts_in_flight_http(self) -> None:
        hang, agent = await self._hanging_agent()
        abort = asyncio.Event()
        try:
            invoke_task = asyncio.create_task(agent.invoke("hello", abort=abort))
            await asyncio.wait_for(hang.accepted.wait(), timeout=2)
            abort.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(invoke_task, timeout=2)
            await asyncio.wait_for(hang.disconnected.wait(), timeout=2)
        finally:
            await hang.aclose()

    async def test_invoke_task_cancel_still_disconnects(self) -> None:
        """SDK cancels execute() (the producer) before AgentExecutor.cancel()."""
        hang, agent = await self._hanging_agent()
        abort = asyncio.Event()
        try:
            invoke_task = asyncio.create_task(agent.invoke("hello", abort=abort))
            await asyncio.wait_for(hang.accepted.wait(), timeout=2)
            invoke_task.cancel()
            abort.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(invoke_task, timeout=2)
            await asyncio.wait_for(hang.disconnected.wait(), timeout=2)
        finally:
            await hang.aclose()

    async def test_invoke_without_abort_cancels_http(self) -> None:
        hang, agent = await self._hanging_agent()
        try:
            invoke_task = asyncio.create_task(agent.invoke("hello"))
            await asyncio.wait_for(hang.accepted.wait(), timeout=2)
            invoke_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(invoke_task, timeout=2)
            await asyncio.wait_for(hang.disconnected.wait(), timeout=2)
        finally:
            await hang.aclose()


class JsonRpcCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_task_rpc_marks_canceled(self) -> None:
        agent = HangingAgent()
        app = create_app(
            host="127.0.0.1",
            public_url="http://127.0.0.1:9999",
            agent=agent,  # type: ignore[arg-type]
            inbound_token="",
            rate_limit=0,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:9999",
            headers={"A2A-Version": "1.0"},
        ) as client:
            send = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "SendMessage",
                    "params": {
                        "message": {
                            "messageId": "msg-1",
                            "role": "ROLE_USER",
                            "parts": [{"text": "hello"}],
                        },
                        "configuration": {"returnImmediately": True},
                    },
                },
            )
            self.assertEqual(send.status_code, 200, send.text)
            body = send.json()
            self.assertNotIn("error", body, body)
            task_id = body["result"]["task"]["id"]
            self.assertTrue(task_id)

            await asyncio.wait_for(agent.started.wait(), timeout=2)

            cancel = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": "2",
                    "method": "CancelTask",
                    "params": {"id": task_id},
                },
            )
            self.assertEqual(cancel.status_code, 200, cancel.text)
            cancel_body = cancel.json()
            self.assertNotIn("error", cancel_body, cancel_body)
            state = cancel_body["result"]["status"]["state"]
            self.assertEqual(state, "TASK_STATE_CANCELED")
            self.assertTrue(agent.stopped)
            self.assertFalse(agent.finished)

            get_task = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": "3",
                    "method": "GetTask",
                    "params": {"id": task_id},
                },
            )
            self.assertEqual(get_task.status_code, 200, get_task.text)
            get_body = get_task.json()
            self.assertEqual(get_body["result"]["status"]["state"], "TASK_STATE_CANCELED")


if __name__ == "__main__":
    unittest.main()
