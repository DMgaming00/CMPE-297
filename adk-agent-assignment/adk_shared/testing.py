"""Test utilities: a scripted (fake) LLM for deterministic ADK flow tests.

``ScriptedLlm`` is a test double.  Tests that use it exercise ADK's real Runner, tool
dispatch, callbacks, state and confirmation machinery - but NOT Gemini.  Model quality
is evaluated separately with ``adk eval`` (see docs/TESTING.md).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types


def call(name: str, **args: Any) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def text(value: str) -> types.Part:
    return types.Part(text=value)


ScriptStep = types.Part | Callable[[LlmRequest], types.Part]


class ScriptedLlm(BaseLlm):
    """Returns pre-recorded parts, one per model call.

    A step may be a callable receiving the ``LlmRequest`` so it can reference values
    produced by earlier tool calls (e.g. a quote id).
    """

    model: str = "scripted-test-model"
    script: list[Any] = []
    requests: list[Any] = []

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False
                                     ) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        step = self.script.pop(0) if self.script else text("(script exhausted)")
        part = step(llm_request) if callable(step) else step
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def last_tool_response(llm_request: LlmRequest, tool_name: str) -> Any:
    """Most recent function_response payload for ``tool_name`` in the request history."""
    for content in reversed(llm_request.contents or []):
        for part in content.parts or []:
            if part.function_response and part.function_response.name == tool_name:
                return part.function_response.response
    raise AssertionError(f"no response for {tool_name} in request history")


async def run_turn(runner: InMemoryRunner, user_id: str, session_id: str,
                   message: types.Content) -> list[Any]:
    events = []
    async for event in runner.run_async(user_id=user_id, session_id=session_id,
                                        new_message=message):
        events.append(event)
    return events


def user_text(value: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=value)])


def confirmation_reply(function_call_id: str, confirmed: bool) -> types.Content:
    return types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
        id=function_call_id, name="adk_request_confirmation", response={"confirmed": confirmed}))])


def function_calls(events: list[Any]) -> list[types.FunctionCall]:
    return [p.function_call for e in events for p in (e.content.parts if e.content else [])
            if p.function_call]


def function_responses(events: list[Any]) -> list[types.FunctionResponse]:
    return [p.function_response for e in events for p in (e.content.parts if e.content else [])
            if p.function_response]
