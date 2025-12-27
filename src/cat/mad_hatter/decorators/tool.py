import inspect
import time
from uuid import uuid4
from dataclasses import asdict
from typing import Callable, List, Dict, TYPE_CHECKING

from fastmcp.tools.tool import FunctionTool, ParsedFunction
from fastmcp.client.client import CallToolResult
from ag_ui.core.events import EventType # take away after they fix the bug

from cat.protocols.agui import events
from cat.utils import run_sync_or_async

if TYPE_CHECKING:
    from cat.types import Message
    from cat.types.messages import TextContent

class Tool:
    """Cat tool uniforming @tool decorated functions in plugins and MCP tools."""

    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        input_schema: Dict,
        output_schema: Dict,
        is_internal: bool = True,
        return_direct: bool = False,
        examples: List[str] = [],
    ):
        self.func = func
        self.name = name 
        self.description = description 
        self.input_schema = input_schema 
        self.output_schema = output_schema

        self.return_direct = return_direct
        self.examples = examples
        self.is_internal = is_internal
    
        # will be assigned by MadHatter
        self.plugin_id = None

    @classmethod
    def from_decorated_function(
        cls,
        func: Callable,
        return_direct: bool = False,
        examples: List[str] = []
    ) -> 'Tool':
        
        parsed_function = ParsedFunction.from_function(
            func,
            exclude_args=["cat", "self"], # awesome, will only be used at execution
            validate=False
        )

        return cls(
            func,
            name = parsed_function.name,
            description = parsed_function.description,
            input_schema = parsed_function.input_schema,
            output_schema = parsed_function.output_schema,
            return_direct = return_direct,
            examples = examples
        )

    @classmethod
    def from_fastmcp(
        cls,
        t: FunctionTool,
        mcp_client_func: Callable
    ) -> "Tool":
        
        return cls(
            func = mcp_client_func,
            name = t.name,
            description = t.description or t.name,
            input_schema = t.inputSchema,
            output_schema = t.outputSchema,
            is_internal = False
        )
    
    def __repr__(self) -> str:
        return f"Tool(name={self.name}, input_schema={self.input_schema}, internal={self.is_internal})"

    async def execute(self, agent, tool_call) -> "Message":
        """
        Execute a Tool with the provided tool_call data structure (which is returned by the LLM).
        Will emit AGUI events for tool execution and return a Message with role="tool".

        Parameters
        ----------
        agent : Agent
            Agent calling the tool.
        tool_call : dict
            Dictionary representing the choice of tool and its args (produced by LLM)

        Returns
        -------
        Message
            A Message with role="tool" and the tool output.
        """

        # Emit AGUI events
        await self.emit_agui_tool_start_events(agent, tool_call)

        # execute the tool
        if self.is_internal:
            # internal tool
            tool_result: str = await run_sync_or_async(
                self.func, **tool_call["args"], cat=agent # TODOV2: cat optional
            )
        else:
            # MCP tool
            async with agent.mcp:
                tool_result: CallToolResult = await self.func(self.name, tool_call["args"])
        
        # Standardize output
        tool_result = self.standardize_output(tool_call, tool_result) 
        
        # Emit AGUI events
        await self.emit_agui_tool_end_events(agent, tool_call, tool_result)

        # TODOV2: should return something analogous to:
        #   https://modelcontextprotocol.info/specification/2024-11-05/server/tools/#tool-result
        #   Only supporting text for now
        return tool_result

    def standardize_output(self, tool_call, tool_result):

        from cat.types import Message, TextContent

        if isinstance(tool_result, str):
            # legacy tools
            tool_result = CallToolResult(
                content = [
                    TextContent(
                        text=tool_result
                    )
                ],
                structured_content=None
            )
        elif isinstance(tool_result, Message):
            # returning the output of .llm() directly
            tool_result = CallToolResult(
                content = [tool_result.content],
                structured_content=None
            )

        text = ""
        for c in tool_result.content:
            if c.type == "text":
                text += c.text # TODO: many content blocks here of different types, also embedded resources
        
        return Message(
            role="tool",
            content=TextContent(
                text=text,
                tool={
                    "in": tool_call,
                    "out": asdict(tool_result) # it's a dataclass
                }
            )
        )

    async def emit_agui_tool_start_events(self, agent, tool_call):
        await agent.agui_event(
            events.ToolCallStartEvent(
                timestamp=int(time.time()),
                tool_call_id=str(tool_call["id"]),
                tool_call_name=tool_call["name"]
            )
        )
        await agent.agui_event(
            events.ToolCallArgsEvent(
                timestamp=int(time.time()),
                tool_call_id=str(tool_call["id"]),
                delta=str(tool_call["args"]), # here the protocol assumes tool args are streamed
                raw_event=tool_call
            )
        )
    
    async def emit_agui_tool_end_events(self, agent, tool_call, tool_output):
        await agent.agui_event(
            events.ToolCallEndEvent(
                timestamp=int(time.time()),
                tool_call_id=str(tool_call["id"]) # may be more than one?
            )
        )
        await agent.agui_event(
            events.ToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT, # bug in the lib, this should not be necessary
                timestamp=int(time.time()),
                message_id=str(uuid4()), # shold be the id of the last user message
                tool_call_id=str(tool_call["id"]),
                content=tool_output.content.text,
                raw_event=tool_output.model_dump()
            )
        )

    def bind_to(self, instance) -> 'Tool':
        """Bind this tool's function to an instance (for class-based tools)."""

        original_func = self.func
        sig = inspect.signature(original_func)
        valid_params = set(sig.parameters.keys()) - {'self'}

        # Bind the method
        bound_method = original_func.__get__(instance, instance.__class__)

        # Create wrapper
        def create_bound_wrapper(bound_func, params):
            async def wrapper(**kwargs):
                filtered_kwargs = {k: v for k, v in kwargs.items() if k in params}
                if inspect.iscoroutinefunction(bound_func):
                    return await bound_func(**filtered_kwargs)
                else:
                    return bound_func(**filtered_kwargs)

            return wrapper

        # Return a NEW Tool with the bound function
        return Tool(
            func=create_bound_wrapper(bound_method, valid_params),
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            return_direct=self.return_direct,
            examples=self.examples,
            is_internal=self.is_internal
        )


def tool(*args, return_direct: bool = False, examples: List[str] = []) -> Tool:

    if len(args) == 1 and callable(args[0]):
        return Tool.from_decorated_function(
            args[0],
            return_direct=return_direct,
            examples=examples
        )
    else:
        def wrapper(func):
            return Tool.from_decorated_function(
                func,
                return_direct=return_direct,
                examples=examples
            )
        return wrapper


