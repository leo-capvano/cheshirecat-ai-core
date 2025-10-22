
# Version 2 dev notes

## Intro

- the good and the bad so far
- synthesis of many requests and common issues
- necessity to make maintaining easier
- new standards


## Installation

- user:
  ```bash
  uv init --bare mycat
  cd mycat
  uv add cheshire-cat-ai
  uv run cat
  ```

- contributor:
  ```bash
  git clone ....
  cd core
  uv venv
  uv run cat
  ```

  To run linter and tests
  ```bash
  uv run ruff check
  uv run pytest tests
  ```

- github action:
  ```bash
  uv sync
  uv build
  uv publish --token={TOKEN}
  ```

- the docker is broken btw


## Agents

- there is a new decorator (TODO) `@agent` that allows you to define your own agents. When you send a request to the cat, you can ask a reply from a specific agent (more details below). If the agent name is not specified in the request, a default `SimpleAgent` will be used. 
- you can declare an agent in your plugin using `@agent` and subclassing the `BaseAgent` class, which only requires a method `execute` and a `name` attribute. TODO example.
- the agent router is name based. You can still define a custom routing agent that can do way more complicated stuff (embedding based routing, LLM based routing, etc.).
- So yes, now a plugin can contain one or more agents, and the agents can talk among themselves. I don't recommend such setups in production, but for sure having more agents and having the user decide which one to run, should allow more stable and useful AI apps.
- Agents can decide whether or not to run hooks, and even create new ones. Just call `cat.mad_hatter.execute_hook("my_hook", default_value, cat)` and everything works as it already worked.
- TODO: nice utility method `cat.execute_hook("hook_name", default)`.


## Plugins

- Most core functionality has been moved to plugins (still to be fixed and published). The vision is for a super slim core and more advanced plugins.
- There are many changes and most plugins need to be adjusted (will provide a dedicated guide). The old admin still works with v2 via core plugin `legacy_v1`.
- The cat vector memory can be completely deactivated, or some of it, and can be replaced/extended for example with a graph memory. See plugin `qdrant_vector_memory`
- Due to difficulties in keeping up with langchain, core only depends on `langchain_core`. All LLM and embedder vendors are now packed in a dedicated `langchain_models_pack` plugin so they are isolated and more easily maintained. All langchain imports and all conversions between langchain and cat types happen in a single folder under `cat.protocols.future` waiting for a standard protocol for all LLM services, if ever. Ditching langchain alltogether is possible.
- plugins can contain tests inside a folder names `tests`. This folder will be ignored by the cat at runtime but tests will be run by `pytest`


## Network

- new `/chat` endpoint that supports streaming (GIVE EXAMPLE), accepting `ChatRequest` and returning `ChatResponse` under both http and websocket. You can access this data structures in plugins with `cat.chat_request` and `cat.chat_response`.
- When a client calls the cat, it can specify which agent to use in `ChatRequest.agent`. Default is `simple`, which is the old one.
- conversation history endpoints (GET and POST) have been deleted and there is a new CRUD for chat sessions in core plugin `XXXXXXX`. Convo history as a recommended practice, must be passed via ws or http via `ChatRequest.messages` (similar to OpenAI or Ollama).
- endpoint `/message` has been moved to plugin `legacy_v1`, so it is still available. The main http endpoint to chat with the cat is `/chat` and must receive a `ChatRequest` JSON, which is very similar to the format use by all major LLM/assistant vendors. The endpoint supports streaming
- You can define new agents in your plugin subclassing `BaseAgent` and registering it with a hook:
  ```python
    ESEMPIO CUSTOM AGENT
  ```
- so input and output data structure have changed, but by keeping active plugin `legacy_v1` old clients should still work (make a PR if you find bugs).
- From now on we only support chat models, text only or text plus images. Pure completion models are not supported anymore. If you need to use one, create your own LLM adapter and hook it via `factory_allowed_llms`.
- Embedders are not automatically associated with the chosen LLM vendor. You will need to configure that yourself, The cat will notify you at every message if the embedder is not set.
- when calling the Cat via websocket and http streaming, all tokens, notifications, agent steps, errors and other lifecycle events (including final response) will be sent following the [AG-UI](https://docs.ag-ui.com/concepts/events) protocol. 
- Settings, Plugins, Auth and Static endpoints have been refined and typed
  - details for each TODO
- new `chats` endpoints


## Folder structure

- `plugins`, `static` and `data` folders live now in the root folder of a project, and are automatically created at first launch. In this way the cat can be used as a simple python package.
- Core plugins are automatically installed at first launch (TODO)
- For the rest, the python package is absolutely stateless and stores no information whatsoever ( TODO check caches)


## Internals

- For v2, not being forced to respect retro-compatibility, I made a much requested move towards `async/await`. Important core contributors were pushing for this, and support for MCP made it a forced choice. The Cat now uses a single thread and should support way more concurrent requests. This implies that many methods that were simple funcions, now are declared `async` and must be awaited with `await`.
- Some of the functions (from core and plugins) work both sync and async. More details on async below.
- All websocket methods (`send_ws_message`, `send_chat_message`, `send_notification`, `send_error`) must be awaited as they are now async:

    ```python
        await send_ws_message(msg)
    ```
- also `cat.llm` is async (dunno, maybe leave it there for retro and have a new `cat.async_llm` but the name sucks). TODO Or maybe use a decorator to make it work both ways
- `cat.llm` got a deep refactoring and has many options XXXXXX
- `StrayCat.working_memory.history` is not kept in RAM, as it is passed by the client and easily found in `cat.chat_request.messages`; history construction is delegated to plugins (so you can decide whether to keep it stored client side, cat side - with custom endpoints - or another service side).
- there is no more distinction between
- A specialized factory is responsible to generate objects for AuthHandler, LLM, Embedder. The factory uses hooks you already had to gather all custom classes from plugins.
- `CatForm` used via the `@form` decorator are not included in core and have been moved to a plugin `form`. It was interesting to do research on this, but we ended up overengineering them: LLMs are way more powerful now and MCP has `elicitation` directly baked into tools.
- Caches are managed directly via an indexed SQL table, so all previous cache versions have been deleted.
- We've got a stabler and easier typing for Cat internals. Import the classes like this:
  ```python
  from cat.types import Message, Resource # and all other types
  ```
- core DB is a simple SQL (supports both sqlite and postgres) and it is used to store settings, chats, contexts and plugin settings. No more `metadata.json`, no `qdrant` in core.
- factory explanation XXX

## Hooks

- you have now in `cat.chat_request` an object of type `ChatRequest`, containing user input and convo history, and in `cat.chat_response` an object of type `ChatResponse`.  
`cat.chat_response` is available since the beginning of the message flow. This is to avoid patterns in which devs stored in working memory stuff to be added later on in the final response via `before_cat_send_message`. Now you can store output data directly in `cat.chat_response` and the client will receive that data.  
Both `cat.chat_request` and `cat.chat_response` are cleared at each message. Use `cat.working_memory` to store arbitrary information across the whole conversation.
- hooks can be declared sync, as in v1, and also async. The async version is recommended and the sync one will trigger a warning. Example:
  ```python
  @hook
  async def before_cat_sends_message(m, cat):
      m.text = await cat.llm("...")
      return m
  ```
- `before_agent_starts` hook now has no argument aside `cat`, as all context/agent_input is directly stored and inserted into prompt based on the content of working memory (you can hook this via `agent_prompt_suffix`)


## Tools

- From now on we need to talk about internal and external (MCP) tools. Both are automatically converted to `CatTool` and made available to the agents
- Tools can now accept multiple arguments, thanks to the implemntation provided by Emanuele Morrone (@pingdred)
- Tool output can be a string, but now we allow also custom data structures and files via CatToolOutput (Yet TODO)


## Auth

Auth system semplifications (TODO review):

- All endpoints, http and websocket, start closed (except XXXXX)
- You can now login into `/docs` using `CCAT_API_KEY`
- The default `CCAT_API_KEY` is `meow`.
- The default `CCAT_JWT_SECRET` is `meow_jwt`
- Both the key and the jwt must be sent via header `Authorization: Bearer xxx`.
- `CCAT_API_KEY_WS` does not exist anymore.
- If you are calling the cat machine-to-machine, use `CCAT_API_KEY`, for both http and ws. Websocket in a machine-to-machine settings supports headers, so you can follow the same schema (query parameter `?token=` is not supported anymore). TODO: still active just for dev v2
- If you are calling the cat form an unsecure client (a browser), use *only* jwt auth.
- You need to authenticate also to see `/docs` and there is a little form to do it in the page
- it is now possible to have `@endpoint` with custom resource and permissions. They can be defined on the endpoint and must be matched by user permissions (which can be assigned via AuthHandler)
- A new installation by default only recognizes one superuser with full permissions, with name `admin` and pass `admin`. To change these credentials use env variable `CCAT_ADMIN_CREDENTIALS` in this format:
  ```bash
    CCAT_ADMIN_CREDENTIALS=username:password
  ```
- there is only one given active AuthHandler at any given time :)
- Utilities to add and edit users have been eradicated from the framework, due to many complications, niche requests from community, and the half baked solution that resulted in v1. Now AuthHandlers can manage users fully on their own. Support for SSO is rolling out!


## MCP support

- this offers amazing opportunities for integration, as tens of thousands of MCP servers are now available. There are still just a few MCP clients, and the Cat is the furriest one.
- you can access the MCP client directly from the `StrayCat`:
  ```python
      tools = await cat.list_tools()
      prompts = await cat.list_prompts()
      resources = await cat.list_resources()
  ```
  Note `list_tools` gives a list of `CatTool` objects, which uniform both intenral plugin tools and MCP tools.
- you can connect to the cat only MCP servers that have http transport. Do not even try to ask me to run stdio based servers inside the cat. Use a proper proxy and aggregator for your local stuff, for example [MetaMCP](https://docs.metamcp.com/en).


## Others

- all http errors, both the ones coming from the cat and the ones coming from fastAPI validation, return an `HTTPException`
- statci files are protected



## TODO

- update core plugins so they attach to hooks exposed by core and provide their own hooks for other plugins
- `qdrant_vector_memory` should deal with embedder changes, maybe reactivating the snapshot
- security must be always ON, also on a fresh installation, with a default jwt secret and API key. Pages in `/docs` should allow logging in
- `StrayCat.__call_` should be an async generator using `yield` to send tokens and notifications. Those yielded result are then managed at the transport layer (websocket or http/streaming/sse). Cat internals should know absolutely nothing about network protocols.
- core tests should only deal with core (also because plugin install dependencies is mocked!!!)
- allow plugin settings with conditionals and subpages with json schema primitives `if`, `oneOf`, etc.
- AG-UI should send `event: {xxx}`, leave `data: {xxx}` for the legacy messaging style 
- static files ownership in DB table or via route checks, i.e `static/me`
- internal user_id, to avoid throwing around email, could be a uuid5 (based on namespace installation_id)
- some packages used by core occupy a lot of space and do basically nothing (find alts)
  `du -h .venv/lib/python3.13/site-packages --max-depth=1 | sort -hr`
- `@hook` decorator should support autocomplete for the hooks names, and allow custom strings
- check for memory leaks (see Luca Gobbi's setup for locust)
- recover core plugins as they are all broken
- `cat` argument in hooks and tools should be optional
- update to langchain v1

## Questions

- should core plugins hooks have priority 0 so they go first?
- should all hooks be able to return a ChatResponse and interrupt the flow with the direct final response?
- new plugins with custom requirements may not work as expected (need a restart).
- as there are docker and pyPI releases, makes no sense to have a `develop` branch
- move plugin settings out of plugin folder and into DB?
- should we finally get rid of `BaseModelDict`?

## Challenges

- Create an "auto" agent that automatically redirects execution to the most competent agent (TODO agents should have a description)
- Log into the Cat with your Google account
