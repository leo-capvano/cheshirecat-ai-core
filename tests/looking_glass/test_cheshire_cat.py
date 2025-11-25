import pytest

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings


from cat.mad_hatter.mad_hatter import MadHatter
from cat.memory.long_term_memory import LongTermMemory
from cat.factory.defaults import EmbedderDefault
from cat.factory.defaults import LLMDefault


@pytest.fixture(scope="function")
def cheshire_cat(client):
    yield client.app.state.ccat


def test_main_modules_loaded(cheshire_cat):
    assert isinstance(
        cheshire_cat.mad_hatter, MadHatter
    )
    assert isinstance(cheshire_cat.memory, LongTermMemory)
    assert isinstance(cheshire_cat._llm, BaseChatModel)
    assert isinstance(cheshire_cat.embedder, Embeddings)


def test_default_llm_loaded(cheshire_cat):
    assert isinstance(cheshire_cat._llm, LLMDefault)


def test_default_embedder_loaded(cheshire_cat):
    assert isinstance(cheshire_cat.embedder, EmbedderDefault)

    sentence = "I'm smarter than a random embedder BTW"
    sample_embed = EmbedderDefault().embed_query(sentence)
    out = cheshire_cat.embedder.embed_query(sentence)
    # DefaultEmbedder is random, so they will be different but same size
    for e in [sample_embed, out]:
        assert len(e) == 128
        for i in e:
            assert isinstance(i, float)

# TODOV2 where do we put this
"""
def test_procedures_embedded(cheshire_cat):
    # get embedded tools
    procedures, _ = cheshire_cat.memory.vectors.procedural.get_all_points()
    assert len(procedures) == 3

    for p in procedures:
        assert p.payload["metadata"]["source"] == "get_the_time"
        assert p.payload["metadata"]["type"] == "tool"
        trigger_type = p.payload["metadata"]["trigger_type"]
        content = p.payload["page_content"]
        assert trigger_type in ["start_example", "description"]

        if trigger_type == "start_example":
            assert content in ["what time is it", "get the time"]
        if trigger_type == "description":
            assert (
                content
                == "get_the_time: Useful to get the current time when asked. Input is always None."
            )

        # some check on the embedding
        assert isinstance(p.vector, list)
        expected_embed = cheshire_cat.embedder.embed_query(content)
        assert len(p.vector) == len(expected_embed)  # same embed
        # assert p.vector == expected_embed TODO: Qdrant does unwanted normalization
"""