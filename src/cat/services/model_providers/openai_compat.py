import json
from typing import TYPE_CHECKING
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI, NOT_GIVEN

from cat.types import Message
from cat.protocols.model_context.type_wrappers import TextContent
from .base import ModelProvider

if TYPE_CHECKING:
    from cat.mad_hatter.decorators import Tool


class OpenAICompatibleProvider(ModelProvider):
    """
    Base for providers using OpenAI-compatible APIs.
    Subclasses only need to set slug/description and configure `self.client` in setup().
    """

    slug = "openai_compatible"
    description = "Base provider for OpenAI-compatible APIs."

    client: AsyncOpenAI

    async def llm(
        self,
        model: str,
        messages: list[Message],
        system_prompt: str = "",
        tools: list["Tool"] = [],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> Message:
        oai_messages = self.build_messages(system_prompt, messages)
        oai_tools = self.build_tools(tools) if tools else NOT_GIVEN

        if on_token:
            return await self.stream_completion(model, oai_messages, oai_tools, on_token)

        resp = await self.client.chat.completions.create(
            model=model, messages=oai_messages, tools=oai_tools
        )
        return self.parse_response(resp.choices[0].message)

    def build_messages(self, system_prompt: str, messages: list[Message]) -> list[dict]:
        oai = []
        if system_prompt:
            oai.append({"role": "system", "content": system_prompt})
        for m in messages:
            oai.append(self.convert_message(m))
        return oai

    def convert_message(self, m: Message) -> dict:
        if m.role == "user":
            parts = []
            for block in m.content:
                if block.type == "text":
                    parts.append({"type": "text", "text": block.text})
                elif block.type == "image":
                    parts.append({"type": "image_url", "image_url": {"url": block.data}})
            content = parts[0]["text"] if len(parts) == 1 and parts[0]["type"] == "text" else parts
            return {"role": "user", "content": content}

        elif m.role == "assistant":
            msg = {"role": "assistant", "content": m.text}
            if m.tool_calls:
                msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                    for tc in m.tool_calls
                ]
            return msg

        elif m.role == "tool":
            return {"role": "tool", "content": m.text, "tool_call_id": m.tool_call_id}

    def build_tools(self, tools: list["Tool"]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t.name.strip().replace(" ", "_"),
                "description": t.description,
                "parameters": t.input_schema
            }}
            for t in tools
        ]

    def parse_response(self, choice) -> Message:
        tool_calls = []
        if choice.tool_calls:
            tool_calls = [
                {"id": tc.id, "name": tc.function.name,
                 "args": json.loads(tc.function.arguments)}
                for tc in choice.tool_calls
            ]
        return Message(
            role="assistant",
            content=[TextContent(text=choice.content or "")],
            tool_calls=tool_calls
        )

    async def embed(self, text: str, model: str) -> list[float]:
        resp = await self.client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding

    async def stream_completion(self, model, oai_messages, oai_tools, on_token) -> Message:
        full_text = ""
        tool_calls_acc = {}  # index -> {id, name, args}

        stream = await self.client.chat.completions.create(
            model=model, messages=oai_messages, tools=oai_tools, stream=True
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                await on_token(delta.content)
                full_text += delta.content
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc_delta.id, "name": "", "args": ""}
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["args"] += tc_delta.function.arguments

        tool_calls = [
            {"id": tc["id"], "name": tc["name"], "args": json.loads(tc["args"] or "{}")}
            for tc in tool_calls_acc.values()
        ]
        return Message(
            role="assistant",
            content=[TextContent(text=full_text)],
            tool_calls=tool_calls
        )
