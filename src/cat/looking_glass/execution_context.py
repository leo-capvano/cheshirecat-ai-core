
import asyncio
import time
from uuid import uuid4
from collections.abc import AsyncGenerator
from typing import Any, Callable

from cat.auth.user import User
from cat.looking_glass.cheshire_cat import CheshireCat
from cat.protocols.agui import events
from cat.types import ChatRequest, ChatResponse
from cat.mad_hatter.plugin import Plugin
from cat.mad_hatter.decorators import Service
from cat.agents.base import Agent
from cat import log


class ExecutionContext:
    """
    Request execution context.
    It is instantiated  for every request and passed to plugins for easy access to:
     - the main app `ccat`
     - current `user`
     - current `plugin`
     - services offered by framework and plugins (llms, agents, memories, etc.)

    You will be interacting with an instance of this class directly from within your plugins:

     - in `@hook`, `@tool` and `@endpoint` decorated functions will be passed as argument `ctx` (in version 1 was called `cat`).
     - Agents have it under self.ctx.
    """

    def __init__(
        self,
        ccat: CheshireCat,
        user: User | None = None
    ):
        """
        Initialize the ExecutionContext.
        
        Parameters
        ----------
        ccat : CheshireCat
            The main Cat application instance.
            Gives access to all the plugins, services, agents, etc.
        user : User | None
            The current user instance.
            During bootstrap and scheduled jobs can be None (no user in that scope).
        """
        self.ccat = ccat
        self.user = user
        self.stream_callback = lambda x: None

    def get_service(self, type: str, slug: str) -> Service | None:
        """Get a service instance by type and slug.

        Parameters
        ----------
        type : str
            The type of the service (e.g. "llm", "memory", "agent", etc.)
        slug : str
            The slug of the service.

        Returns
        -------
        service : Service | None
            The service instance if found, else None.
        """
        return self.ccat.get_service(type, slug)

    async def __call__(
        self,
        request: ChatRequest,
        stream_callback: Callable = lambda x: None
    ) -> ChatResponse:
        """Run the conversation turn.

        This method is called on the user's message received from the client.  
        It is the main pipeline of the Cat, it is called automatically.

        Parameters
        ----------
        request : ChatRequest
            ChatRequest object received from the client via http or websocket.
        stream_callback : Callable | None
            A function that will be used to emit messages via http (streaming) or websocket.
            If None, this method will not emit messages and will only return the final ChatResponse.

        Returns
        -------
        response : ChatResponse | None
            ChatResponse object, the Cat's answer to be sent back to the client.
            If stream_callback is passed, this method will return None and emit the final response via the stream_callback
        """

        # used to stream messages back to the client via queue
        self.stream_callback = stream_callback

        # TODOV2: fast_reply hook has no access to messages
        # Run a totally custom reply (skips all the side effects of the framework)
        fast_reply = await self.mad_hatter.execute_hook(
            "fast_reply", {}, ctx=self)
        if fast_reply != {}:
            return fast_reply # TODOV2: this probably breaks pydantic validation on the output

        # hook to modify/enrich user input
        # TODOV2: shuold be compatible with the old `user_message_json`
        request = await self.mad_hatter.execute_hook(
            "before_cat_reads_message", request, ctx=self
        )

        # run agent(s). They will populate the ChatResponse
        slug = request.agent
        AgentClass = self.ccat.agents.get(slug)
        if not AgentClass:
            raise Exception(f'Agent "{slug}" not found')
        agent = AgentClass(self)
        response: ChatResponse = await agent(request)

        # run final response through plugins
        response = await self.mad_hatter.execute_hook(
            "before_cat_sends_message", response, ctx=self
        )

        # Return final reply
        return response

    async def stream(
        self,
        request: ChatRequest,
    ) -> AsyncGenerator[Any, None]:
        """Run the execution keeping a queue of its messages in order to stream them or send them via websocket.
        Emits the main AGUI lifecycle events
        """

        # unique id for this run
        run_id = str(uuid4()) # TODOV2: can be generated in ChatRequest construction
        thread_id = "_"

        # AGUI event for agent run start
        yield events.RunStartedEvent(
            timestamp=int(time.time()),
            thread_id=thread_id,
            run_id=run_id
        )

        # build queue and task
        queue: asyncio.Queue = asyncio.Queue()
        async def callback(msg) -> None:
            await queue.put(msg) # TODO have a timeout
        async def runner() -> None:
            try:
                # Main entry point to StrayCat.__call__, contains the main AI flow
                final_reply = await self(
                    request,
                    stream_callback=callback
                )

                # AGUI event for agent run finish
                await callback(
                    events.RunFinishedEvent(
                        timestamp=int(time.time()),
                        thread_id=thread_id,
                        run_id=run_id,
                        result=final_reply.model_dump()
                    )
                )
            except Exception as e:
                await callback(
                    events.RunErrorEvent(
                        timestamp=int(time.time()),
                        message=str(e)
                        # result= TODOV2 this should be the final response
                    )
                )
                log.error(e)
            finally:
                await queue.put(None)

        try:
            # run the task
            runner_task: asyncio.Task[None] = asyncio.create_task(runner())

            # wait for new messages to stream or websocket back to the client
            while True:
                msg = await queue.get() # TODO have a timeout
                if msg is None:
                    break
                yield msg
        except Exception as e:
            runner_task.cancel()
            yield events.RunErrorEvent(
                timestamp=int(time.time()),
                message=str(e)
            )
            log.error(e)
        
    # TODOV2:
    # recover legacy V1 properties and methods for easier plugin migration
    # (use log.deprecation_warning inside each of them)

    async def execute_hook(self, hook_name, default_value):
        """Execute a plugin hook."""
        return await self.ccat.mad_hatter.execute_hook(
            hook_name,
            default_value,
            ctx=self
        )
            
    @property
    def user_id(self) -> str:
        """Get the user ID."""
        return self.user.id
    
    @property
    def mad_hatter(self):
        """Gives access to the `MadHatter` plugin manager."""
        return self.ccat.mad_hatter
    
    @property
    def plugin(self) -> Plugin:
        """Get the current plugin. Can be None if called outside plugin scope."""
        return self.ccat.plugin
    
    @property
    def agent(self) -> Agent | None:
        """Get access to the agent being executed. Can be None outside agent execution."""
        return self.agent