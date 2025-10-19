
import asyncio
import time
from uuid import uuid4
from collections.abc import AsyncGenerator
from typing import Literal, get_args, List, Dict, Union, Any, Callable

from cat.protocols.agui import events
from cat.auth.permissions import User
from cat.looking_glass.cheshire_cat import CheshireCat
from cat.protocols.future.llm_wrapper import LLMWrapper
from cat.memory.working_memory import WorkingMemory
from cat.types import Message, ChatRequest, ChatResponse
from cat.mad_hatter.decorators import CatTool
from cat import utils
from cat.log import log

MSG_TYPES = Literal["notification", "chat", "error", "chat_token"]

# The Stray cat goes around tools, hooks and endpoints... making troubles
class StrayCat:
    """Session object containing user data, conversation state and many utility pointers.
    The framework creates an instance for every http request and websocket connection, making it available for plugins.

    You will be interacting with an instance of this class directly from within your plugins:

     - in `@hook`, `@tool` and `@endpoint` decorated functions will be passed as argument `cat` or `stray`

    Parameters
    ----------
    user : User
        User object.
    
    """

    chat_request: ChatRequest | None = None
    """The ChatRequest object coming from the client, containining the request for this conversation turn."""
    
    chat_response: ChatResponse | None = None
    """ChatResponse object that will go out to the client once the conversation turn is finished.
        It is available since the beginning of the Cat flow."""

    working_memory: WorkingMemory
    """State machine containing the conversation state, persisted across conversation turns, acting as a simple dictionary / object.
    Can be used in plugins to store and retrieve data to drive the conversation or do anything else.

    Examples
    --------
    Store a value in the working memory during conversation
    >>> cat.working_memory["location"] = "Rome"
    or
    >>> cat.working_memory.location = "Rome"

    Retrieve a value in later conversation turns
    >>> cat.working_memory["location"]
    "Rome"
    >>> cat.working_memory.location
    "Rome"
    """

    def __init__(
        self,
        user: User,
        ccat: CheshireCat
    ):

        # user data
        self.user = user

        # pointer to CheshireCat instance
        self._ccat = ccat


    def __repr__(self):
        return f"StrayCat(user_id={self.user_id}, user_name={self.user.name})"

    # TODOV2: method should be one and should be `send_message`.
    #         Stray should not know about websockets or anything network related
    async def __send_ws_json(self, data: Any):
        
        if self.message_callback:
            await self.message_callback(data)

    async def _load_working_memory(self):
        """Load working memory from DB."""
        
        # TODOV2: load from DB
        self.working_memory = WorkingMemory()

    async def _save_working_memory(self):
        """Save working memory to DB."""

        # TODOV2: save to DB
        pass

    # TODOV2: take away `ws` and simplify these methods so it is only one
    async def send_ws_message(self, content: str | dict, msg_type: MSG_TYPES = "notification"):
        """Send a message via websocket.

        This method is useful for sending a message via websocket directly without passing through the LLM.  
        In case there is no connection the message is skipped and a warning is logged.

        Parameters
        ----------
        content : str
            The content of the message.
        msg_type : str
            The type of the message. Should be either `notification` (default), `chat`, `chat_token` or `error`

        Examples
        --------
        Send a notification via websocket
        >>> await cat.send_ws_message("Hello, I'm a notification!")

        Send a chat message via websocket
        >>> await cat.send_ws_message("Meooow!", msg_type="chat")
        
        Send an error message via websocket
        >>> await cat.send_ws_message("Something went wrong", msg_type="error")

        Send custom data
        >>> await cat.send_ws_message({"What day it is?": "It's my unbirthday"})
        """

        options = get_args(MSG_TYPES)

        if msg_type not in options:
            raise ValueError(
                f"The message type `{msg_type}` is not valid. Valid types: {', '.join(options)}"
            )

        if msg_type == "error":
            await self.__send_ws_json(
                {"type": msg_type, "name": "GenericError", "description": str(content)}
            )
        else:
            await self.__send_ws_json({"type": msg_type, "content": content})


    async def send_chat_message(self, message: str | ChatResponse):
        """Sends a chat message to the user using the active WebSocket connection.  
        In case there is no connection the message is skipped and a warning is logged

        Parameters
        ----------
        message: str, CatMessage
            Message to send
        save: bool | optional
            Save the message in the conversation history. Defaults to False.

        Examples
        --------
        Send a chat message during conversation
        >>> cat.send_chat_message("Hello, dear!")

        Using a `CatMessage` object
        >>> message = CatMessage(text="Hello, dear!", user_id=cat.user_id)
        ... cat.send_chat_message(message)
        """

        if isinstance(message, str):
            message = ChatResponse(text=message, user_id=self.user_id)

        await self.__send_ws_json(message.model_dump())


    async def send_notification(self, content: str):
        """Sends a notification message to the user using the active WebSocket connection.  
        In case there is no connection the message is skipped and a warning is logged

        Parameters
        ----------
        content: str
            Message to send

        Examples
        --------
        Send a notification to the user
        >>> cat.send_notification("It's late!")
        """
        await self.send_ws_message(content=content, msg_type="notification")


    async def send_error(self, error: Union[str, Exception]):
        """Sends an error message to the user using the active WebSocket connection.

        In case there is no connection the message is skipped and a warning is logged

        Parameters
        ----------
        error: str, Exception
            Message to send

        Examples
        --------
        Send an error message to the user
        >>> cat.send_error("Something went wrong!")
        or
        >>> cat.send_error(CustomException("Something went wrong!"))
        """

        if isinstance(error, str):
            error_message = {
                "type": "error",
                "name": "GenericError",
                "description": str(error),
            }
        else:
            error_message = {
                "type": "error",
                "name": error.__class__.__name__,
                "description": str(error),
            }

        await self.__send_ws_json(error_message)

    async def agui_event(self, event: events.BaseEvent):
        await self.__send_ws_json(dict(event))
    
    async def llm(
            self,
            system_prompt: str,
            model: str | None = None,
            messages: list[Message] = [],
            tools: list[CatTool] = [],
            stream: bool = True,
        ) -> Message:
        """Generate a response using the Large Language Model.

        Parameters
        ----------
        system_prompt : str
            The system prompt (context, personality, or a simple instruction/request).
        prompt_variables : dict
            Structured info to hydrate the system_prompt.
        messages : list[Message]
            Chat messages so far, as a list of `HumanMessage` and `CatMessage`.
        tools : TODOV2
        model : str | None
            LLM to use, in the format `vendor:model`, e.g. `openai:gpt-5`.
            If None, uses default LLM as in the settings.
        stream : bool
            Whether to stream the tokens via websocket or not.

        Returns
        -------
        str
            The generated LLM response.

        Examples
        -------
        Detect profanity in a message
        >>> message = cat.working_memory.user_message_json.text
        ... cat.llm(f"Does this message contain profanity: '{message}'?  Reply with 'yes' or 'no'.")
        "no"

        Run the LLM and stream the tokens via websocket
        >>> cat.llm("Tell me which way to go?", stream=True)
        "It doesn't matter which way you go"
        """
        
        if model:
            _llm = self._ccat.llms[model]
        else:
            _llm = self._llm

        new_mex: Message = await LLMWrapper.invoke(
            self,
            model=_llm,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            stream=stream
        )
        return new_mex
    

    async def execute_hook(self, hook_name, default_value):
        return self.mad_hatter.execute_hook( # TODOV2: have hook execution async
            hook_name,
            default_value,
            cat=self
        )
    
    async def execute_agent(self, slug):
        await self._ccat.agents[slug].execute(self)

    async def get_system_prompt(self) -> str:

        # obtain prompt parts from plugins
        # TODOV2: give better naming to these hooks
        prompt_prefix = await self.execute_hook(
            "agent_prompt_prefix",
            self.chat_request.context.instructions
        )
        prompt_suffix = await self.execute_hook("agent_prompt_suffix", "")

        return prompt_prefix + prompt_suffix


    async def list_tools(self) -> List[CatTool]:
        """
        Get both plugins' tools and MCP tools in CatTool format.
        """

        mcp_tools = await self.mcp.list_tools()
        mcp_tools = [
            CatTool.from_fastmcp(t, self.mcp.call_tool)
            for t in mcp_tools
        ]
        return mcp_tools + self.mad_hatter.tools
    

    # TODO: should support MCP notation call_tool("name", {a: 32})
    async def call_tool(self, tool_call, *args, **kwargs): # TODO: annotate CatToolResult?
        """Call a tool."""

        name = tool_call["name"]
        for t in await self.list_tools():
            if t.name == name:
                return await t.execute(self, tool_call)
            
        raise Exception(f"Tool {name} not found")
            

    async def __call__(
        self,
        chat_request: ChatRequest,
        message_callback: Callable | None = None
    ) -> ChatResponse:
        """Run the conversation turn.

        This method is called on the user's message received from the client.  
        It is the main pipeline of the Cat, it is called automatically.

        Parameters
        ----------
        chat_request : ChatRequest
            ChatRequest object received from the client via http or websocket.
        message_callback : Callable | None
            A function that will be used to emit messages via http (streaming) or websocket.
            If None, this method will not emit messages and will only return the final ChatResponse.

        Returns
        -------
        chat_response : ChatResponse | None
            ChatResponse object, the Cat's answer to be sent back to the client.
            If message_callback is passed, this method will return None and emit the final response via the message_callback
        """

        # Store message_callback to send messages back to the client
        self.message_callback = message_callback

        # Both request and response are available during the whole run
        self.chat_request = chat_request
        self.chat_response = ChatResponse()

        log.info(self.chat_request.model_dump())

        # get working memory from DB or create a new one
        await self._load_working_memory()

        # Run a totally custom reply (skips all the side effects of the framework)
        fast_reply = self.mad_hatter.execute_hook(
            "fast_reply", {}, cat=self
        )
        if fast_reply != {}: # TODOV2: dunno if this breaks pydantic validation on the output
            return fast_reply
        
        #return self._ccat.mcp_clients.get_user_client(
        #    self.user_id, config
        #)
        async with self._ccat.mcp_clients.get_user_client(self) as mcp_client:
            
            # store reference for easy access
            self.mcp = mcp_client

            # hook to modify/enrich user input
            # TODOV2: shuold be compatible with the old `user_message_json`
            self.chat_request = self.mad_hatter.execute_hook(
                "before_cat_reads_message", self.chat_request, cat=self
            )

            # run agent(s). They will populate the ChatResponse
            requested_agent = self.chat_request.agent
            await self.execute_agent(requested_agent)

            # run final response through plugins
            self.chat_response = self.mad_hatter.execute_hook(
                "before_cat_sends_message", self.chat_response, cat=self
            )

            self.mcp = None

        # save working memory to DB
        await self._save_working_memory()

        # Return final reply
        log.info(self.chat_response.model_dump())
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
        thread_id = str(uuid4()) # TODO: should it be the one in the db? Was request.thread

        # AGUI event for agent run start
        yield events.RunStartedEvent(
            timestamp=int(time.time()),
            thread_id=thread_id,
            run_id=run_id
        )

        # build queue and task
        queue: asyncio.Queue[str | None] = asyncio.Queue()
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



    async def classify(
        self, sentence: str, labels: List[str] | Dict[str, List[str]], score_threshold: float = 0.5
    ) -> str | None:
        """Classify a sentence.

        Parameters
        ----------
        sentence : str
            Sentence to be classified.
        labels : List[str] or Dict[str, List[str]]
            Possible output categories and optional examples.

        Returns
        -------
        label : str
            Sentence category.

        Examples
        -------
        >>> cat.classify("I feel good", labels=["positive", "negative"])
        "positive"

        Or giving examples for each category:

        >>> example_labels = {
        ...     "positive": ["I feel nice", "happy today"],
        ...     "negative": ["I feel bad", "not my best day"],
        ... }
        ... cat.classify("it is a bad day", labels=example_labels)
        "negative"

        """

        if isinstance(labels, dict):
            labels_names = labels.keys()
            examples_list = "\n\nExamples:"
            for label, examples in labels.items():
                for ex in examples:
                    examples_list += f'\n"{ex}" -> "{label}"'
        else:
            labels_names = labels
            examples_list = ""

        labels_list = '"' + '", "'.join(labels_names) + '"'

        prompt = f"""Classify this sentence:
"{sentence}"

Allowed classes are:
{labels_list}{examples_list}

"{sentence}" -> """

        response = await self.llm(prompt).content.text # TODOV2: not tested

        # find the closest match and its score with levenshtein distance
        best_label, score = min(
            ((label, utils.levenshtein_distance(response, label)) for label in labels_names),
            key=lambda x: x[1],
        )

        return best_label if score < score_threshold else None
    
    @property
    def user_id(self) -> str:
        """The user's id. Complete user object is under `cat.user`.
        
        Returns
        -------
        user_id : str
            Current user's id.
        """
        return self.user.id

    @property
    def agent(self):
        """Instance of the agent invoked via endpoint.
        """
        slug = self.chat_request.agent
        if slug not in self._ccat.agents:
            raise Exception(f'Agent "{slug}" not found')
        return self._ccat.agents[slug]

    @property
    def _llm(self):
        """
        Low level LLM instance.
        Only use it if you know what you are doing, prefer method `cat.llm(prompt)` otherwise.
        """
        slug = self.chat_request.model
        if slug not in self._ccat.llms:
            raise Exception(f'Model "{slug}" not found')
        return self._ccat.llms[slug]

    @property
    def _embedder(self):
        """
        Low level embedder instance. Use `cat.embed` instead.
        """
        slug = self.chat_request.embedder
        if slug not in self._ccat.embedders:
            raise Exception(f'Embedder "{slug}" not found')
        return self._ccat.embedders[slug]

    @property
    def mad_hatter(self):
        """Gives access to the `MadHatter` plugin manager.

        Returns
        -------
        mad_hatter : MadHatter
            Module to manage plugins.


        Examples
        --------

        Obtain the path in which your plugin is located
        >>> cat.mad_hatter.get_plugin().path
        /app/cat/plugins/my_plugin

        Obtain plugin settings
        >>> await cat.mad_hatter.get_plugin().load_settings()
        {"num_cats": 44, "rows": 6, "remainder": 2}
        """
        return self._ccat.mad_hatter
        
