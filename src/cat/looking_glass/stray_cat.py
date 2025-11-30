
import asyncio
import time
from uuid import uuid4
from collections.abc import AsyncGenerator
from typing import Any, Callable
from pydantic import BaseModel, ConfigDict

from cat.protocols.agui import events
from cat.types import ChatRequest, ChatResponse
from cat.mixin.runtime import CatMixin

from cat import log


class StrayCat(BaseModel, CatMixin):
    """
    Session object used as entry point for agent(s) execution.
    The framework creates an instance for every http request and websocket connection, making it available for plugins.

    You will be interacting with an instance of this class directly from within your plugins:

     - in `@hook`, `@tool` and `@endpoint` decorated functions will be passed as argument `cat` or `stray`
    """

    model_config = ConfigDict(extra='allow') # tmp BaseModel to make it work with new tools

    async def __call__(
        self,
        chat_request: ChatRequest,
        stream_callback: Callable | None = None
    ) -> ChatResponse:
        """Run the conversation turn.

        This method is called on the user's message received from the client.  
        It is the main pipeline of the Cat, it is called automatically.

        Parameters
        ----------
        chat_request : ChatRequest
            ChatRequest object received from the client via http or websocket.
        stream_callback : Callable | None
            A function that will be used to emit messages via http (streaming) or websocket.
            If None, this method will not emit messages and will only return the final ChatResponse.

        Returns
        -------
        chat_response : ChatResponse | None
            ChatResponse object, the Cat's answer to be sent back to the client.
            If stream_callback is passed, this method will return None and emit the final response via the stream_callback
        """

        # Store stream_callback to send messages back to the client
        self.stream_callback = stream_callback

        # Both request and response are available during the whole run
        self.chat_request = chat_request
        self.chat_response = ChatResponse()

        # Run a totally custom reply (skips all the side effects of the framework)
        fast_reply = await self.execute_hook("fast_reply", {})
        if fast_reply != {}: 
            return fast_reply # TODOV2: this probably breaks pydantic validation on the output

        # hook to modify/enrich user input
        # TODOV2: shuold be compatible with the old `user_message_json`
        self.chat_request = await self.execute_hook(
            "before_cat_reads_message", self.chat_request
        )

        # run agent(s). They will populate the ChatResponse
        slug = self.chat_request.agent
        agent = await self.get_agent(slug)
        
        # run agent
        await agent()

        # run final response through plugins
        self.chat_response = await self.execute_hook(
            "before_cat_sends_message", self.chat_response
        )

        # Return final reply
        return self.chat_response


    async def run(
        self,
        request: ChatRequest,
    ) -> AsyncGenerator[Any, None]:
        """Runs the Cat keeping a queue of its messages in order to stream them or send them via websocket.
        Emits the main AGUI lifecycle events
        """

        # unique id for this run
        run_id = str(uuid4())
        thread_id = str(uuid4())

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
                final_reply = await self(request, callback)

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
                raise e
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
            raise e