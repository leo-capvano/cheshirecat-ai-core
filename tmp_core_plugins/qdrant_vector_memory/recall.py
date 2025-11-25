from typing import List, Tuple
from datetime import time, timedelta

from langchain_core.documents import Document

from cat import log
from cat.utils import BaseModelDict, verbal_timedelta

#########################################################
# TODOV2: recall outputs where stored in working memory #
#########################################################
    #episodic_memories: List = []
    #declarative_memories: List = []
    #procedural_memories: List = []


async def recall_relevant_memories_to_working_memory(self, cat, query=None):
    """Retrieve context from memory.

    The method retrieves the relevant memories from the vector collections that are given as context to the LLM.
    Recalled memories are stored in the working memory.

    Parameters
    ----------
    query : str, optional
        The query used to make a similarity search in the Cat's vector memories.  
        If not provided, the query will be derived from the last user's message.

    Examples
    --------
    Recall memories from custom query
    >>> cat.recall_relevant_memories_to_working_memory(query="What was written on the bottle?")

    Notes
    -----
    The user's message is used as a query to make a similarity search in the Cat's vector memories.
    Five hooks allow to customize the recall pipeline before and after it is done.

    See Also
    --------
    cat_recall_query
    before_cat_recalls_memories
    before_cat_recalls_episodic_memories
    before_cat_recalls_declarative_memories
    before_cat_recalls_procedural_memories
    after_cat_recalls_memories
    """

    recall_query = query

    if query is None:
        # If query is not provided, use the user's message as the query
        recall_query = cat.working_memory.user_message_json.text

    # We may want to search in memory
    recall_query = cat.mad_hatter.execute_hook(
        "cat_recall_query", recall_query, cat=cat
    )
    log.info(f"Recall query: '{recall_query}'")

    # Embed recall query
    recall_query_embedding = cat.embedder.embed_query(recall_query)
    cat.working_memory.recall_query = recall_query



    # hook to do something before recall begins
    cat.mad_hatter.execute_hook("before_cat_recalls_memories", cat=cat)

    # Setting default recall configs for each memory
    # TODO: can these data structures become instances of a RecallSettings class?
    default_episodic_recall_config = {
        "embedding": recall_query_embedding,
        "k": 3,
        "threshold": 0.7,
        "metadata": {"source": cat.user_id},
    }

    default_declarative_recall_config = {
        "embedding": recall_query_embedding,
        "k": 3,
        "threshold": 0.7,
        "metadata": {},
    }

    default_procedural_recall_config = {
        "embedding": recall_query_embedding,
        "k": 3,
        "threshold": 0.7,
        "metadata": {},
    }

    # hooks to change recall configs for each memory
    recall_configs = [
        cat.mad_hatter.execute_hook(
            "before_cat_recalls_episodic_memories",
            default_episodic_recall_config,
            cat=cat,
        ),
        cat.mad_hatter.execute_hook(
            "before_cat_recalls_declarative_memories",
            default_declarative_recall_config,
            cat=cat,
        ),
        cat.mad_hatter.execute_hook(
            "before_cat_recalls_procedural_memories",
            default_procedural_recall_config,
            cat=cat,
        ),
    ]

    memory_types = cat.memory.vectors.collections.keys()

    for config, memory_type in zip(recall_configs, memory_types):
        memory_key = f"{memory_type}_memories"

        # recall relevant memories for collection
        vector_memory = getattr(cat.memory.vectors, memory_type)
        memories = vector_memory.recall_memories_from_embedding(**config)

        setattr(
            cat.working_memory, memory_key, memories
        )  # self.working_memory.procedural_memories = ...

    # hook to modify/enrich retrieved memories
    cat.mad_hatter.execute_hook("after_cat_recalls_memories", cat=self)


def format_agent_input(self, cat):
    """Format the input for the Agent.

    The method formats the strings of recalled memories and chat history that will be provided to the Langchain
    Agent and inserted in the prompt.

    Returns
    -------
    BaseModelDict
        Formatted output to be parsed by the Agent executor. Works both as a dict and as an object.

    Notes
    -----
    The context of memories and conversation history is properly formatted before being parsed by the and, hence,
    information are inserted in the main prompt.
    All the formatting pipeline is hookable and memories can be edited.

    See Also
    --------
    agent_prompt_episodic_memories
    agent_prompt_declarative_memories
    agent_prompt_chat_history
    """

    # format memories to be inserted in the prompt
    episodic_memory_formatted_content = self.agent_prompt_episodic_memories(
        cat.working_memory.episodic_memories
    )
    declarative_memory_formatted_content = self.agent_prompt_declarative_memories(
        cat.working_memory.declarative_memories
    )

    # format conversation history to be inserted in the prompt
    # TODOV2: take away
    conversation_history_formatted_content = cat.working_memory.stringify_chat_history()

    return BaseModelDict(**{
        "episodic_memory": episodic_memory_formatted_content,
        "declarative_memory": declarative_memory_formatted_content,
        "tools_output": "",
        "input": cat.working_memory.user_message_json.text,  # TODOV2: take away
        "chat_history": conversation_history_formatted_content, # TODOV2: take away
    })

def agent_prompt_episodic_memories(
    self, memory_docs: List[Tuple[Document, float]]
) -> str:
    """Formats episodic memories to be inserted into the prompt.

    Parameters
    ----------
    memory_docs : List[Document]
        List of Langchain `Document` retrieved from the episodic memory.

    Returns
    -------
    memory_content : str
        String of retrieved context from the episodic memory.
    """

    # convert docs to simple text
    memory_texts = [m[0].page_content.replace("\n", ". ") for m in memory_docs]

    # add time information (e.g. "2 days ago")
    memory_timestamps = []
    for m in memory_docs:
        # Get Time information in the Document metadata
        timestamp = m[0].metadata["when"]

        # Get Current Time - Time when memory was stored
        delta = timedelta(seconds=(time.time() - timestamp))

        # Convert and Save timestamps to Verbal (e.g. "2 days ago")
        memory_timestamps.append(f" ({verbal_timedelta(delta)})")

    # Join Document text content with related temporal information
    memory_texts = [a + b for a, b in zip(memory_texts, memory_timestamps)]

    # Format the memories for the output
    memories_separator = "\n  - "
    memory_content = (
        "## Context of things the Human said in the past: "
        + memories_separator
        + memories_separator.join(memory_texts)
    )

    # if no data is retrieved from memory don't erite anithing in the prompt
    if len(memory_texts) == 0:
        memory_content = ""

    return memory_content

def agent_prompt_declarative_memories(
    self, memory_docs: List[Tuple[Document, float]]
) -> str:
    """Formats the declarative memories for the prompt context.
    Such context is placed in the `agent_prompt_prefix` in the place held by {declarative_memory}.

    Parameters
    ----------
    memory_docs : List[Document]
        list of Langchain `Document` retrieved from the declarative memory.

    Returns
    -------
    memory_content : str
        String of retrieved context from the declarative memory.
    """

    # convert docs to simple text
    memory_texts = [m[0].page_content.replace("\n", ". ") for m in memory_docs]

    # add source information (e.g. "extracted from file.txt")
    memory_sources = []
    for m in memory_docs:
        # Get and save the source of the memory
        source = m[0].metadata["source"]
        memory_sources.append(f" (extracted from {source})")

    # Join Document text content with related source information
    memory_texts = [a + b for a, b in zip(memory_texts, memory_sources)]

    # Format the memories for the output
    memories_separator = "\n  - "

    memory_content = (
        "## Context of documents containing relevant information: "
        + memories_separator
        + memories_separator.join(memory_texts)
    )

    # if no data is retrieved from memory don't write anithing in the prompt
    if len(memory_texts) == 0:
        memory_content = ""

    return memory_content


