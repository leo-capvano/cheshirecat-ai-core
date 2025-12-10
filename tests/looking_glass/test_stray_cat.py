import pytest

from cat.auth import User
from cat.types import ChatResponse, ChatRequest
from cat.looking_glass.stray_cat import StrayCat
from cat.memory.working_memory import WorkingMemory
from cat.mad_hatter.decorators.hook import Hook

from tests.utils import get_request

@pytest.fixture(scope="function")
def stray_cat(async_client):
    user = User(
        id="Alice",
        name="Alice" # TODOV2: user_id should be unique, user name anything
    )
    yield StrayCat() # update with mixin usage


def test_stray_initialization(stray_cat):
    assert isinstance(stray_cat, StrayCat)
    assert stray_cat.user_id == "Alice"
    assert isinstance(stray_cat.working_memory, WorkingMemory)


@pytest.mark.asyncio
async def test_stray_nlp(stray_cat):
    res = await stray_cat.llm("hey") # TODOV2: more tests for .llm
    assert "You did not configure" in res

    embedding = stray_cat.embedder.embed_documents(["hey"])
    assert isinstance(embedding[0], list)
    assert isinstance(embedding[0][0], float)


@pytest.mark.asyncio
async def test_stray_call_with_text(stray_cat):

    reply = await stray_cat( get_request() )

    assert isinstance(reply, ChatResponse)
    assert "You did not configure" in reply.text
    assert reply.user_id == "Alice"


@pytest.mark.asyncio
async def test_stray_call_with_text_and_image(stray_cat):
    
    reply = await stray_cat( get_request() )

    assert isinstance(reply, ChatResponse)
    assert "You did not configure" in reply.text
    assert reply.user_id == "Alice"


# TODO: update these tests once we have a real LLM in tests
@pytest.mark.asyncio
async def test_stray_classify(stray_cat):
    label = await stray_cat.classify("I feel good", labels=["positive", "negative"])
    assert label is None  # TODO: should be "positive"

    label = await stray_cat.classify(
        "I feel bad", labels={"positive": ["I'm happy"], "negative": ["I'm sad"]}
    )
    assert label is None  # TODO: should be "negative"


# TODOV2: where do we put this
"""
def test_recall_to_working_memory(stray_cat):
    # empty working memory / episodic
    assert stray_cat.working_memory.episodic_memories == []

    msg_text = "Where do I go?"
    msg = {"text": msg_text, "user_id": "Alice"}

    # send message
    stray_cat.__call__(msg)

    # recall after episodic memory was stored
    stray_cat.recall_relevant_memories_to_working_memory(msg_text)

    assert stray_cat.working_memory.recall_query == msg_text
    assert len(stray_cat.working_memory.episodic_memories) == 1
    assert stray_cat.working_memory.episodic_memories[0][0].page_content == msg_text
"""
    
# TODOV2: update
@pytest.mark.asyncio
async def test_stray_fast_reply_hook(stray_cat):
    user_msg = "hello"
    fast_reply_msg = "This is a fast reply"

    def fast_reply_hook(fast_reply: dict, cat):
        if user_msg in stray_cat.request.messages[-1].content.text:
            return ChatResponse(user_id=cat.user_id, text=fast_reply_msg)

    fast_reply_hook = Hook(name="fast_reply", func=fast_reply_hook, priority=0)
    fast_reply_hook.plugin_id = "fast_reply_hook"
    stray_cat.mad_hatter.hooks["fast_reply"] = [fast_reply_hook]

    msg = ChatRequest.model_validate({
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": user_msg
                    }
                }
            ]
        }
    )

    # send message
    res = await stray_cat.__call__(msg)

    assert isinstance(res, ChatResponse)
    assert res.text == fast_reply_msg

    # there should be NO side effects
    assert stray_cat.request.messages[-1].content.text == user_msg
