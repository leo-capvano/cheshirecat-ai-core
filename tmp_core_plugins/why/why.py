from typing import List
from cat.utils import BaseModelDict
from cat.mad_hatter.decorators import hook


# TODOV2: this was at the end of the MainAgent
# memory_agent_out.intermediate_steps += procedures_agent_out.intermediate_steps

class MessageWhy(BaseModelDict):
    """
    A class for encapsulating the context and reasoning behind a message, providing details on 
    input, intermediate steps, memory, and interactions with models.

    Attributes
    ----------
    input : str
        The initial input message that triggered the response.
    intermediate_steps : List
        A list capturing intermediate steps or actions taken as part of processing the message.
    memory : dict
        A dictionary containing relevant memory information used during the processing of the message.
    """

    input: str
    intermediate_steps: List
    memory: dict


@hook
def before_cat_sends_message(msg, cat):

    # build data structure for output (response and why with memories)
    
    episodic_report = []
    declarative_report = []
    procedural_report = []

    if hasattr(cat.working_memory, "episodic_memories"): # vector memory may not be enabled
        episodic_report = [
            dict(d[0]) | {"score": float(d[1]), "id": d[3]}
            for d in cat.working_memory.episodic_memories
        ]
        declarative_report = [
            dict(d[0]) | {"score": float(d[1]), "id": d[3]}
            for d in cat.working_memory.declarative_memories
        ]
        procedural_report = [
            dict(d[0]) | {"score": float(d[1]), "id": d[3]}
            for d in cat.working_memory.procedural_memories
        ]

    intermediate_steps = [] # agent_output.intermediate_steps
    # agent_output = {} # agent_output.model_dump()

    # why this response?
    msg.why = MessageWhy(
        input=cat.request.messages[-1].content.text,
        intermediate_steps=intermediate_steps,
        # agent_output=agent_output,
        memory={
            "episodic": episodic_report,
            "declarative": declarative_report,
            "procedural": procedural_report,
        }
    )

    return msg



# TODOV2 TESTS (note: they are mixes with model interactions)
"""
# why
why = reply["why"]
assert {"input", "intermediate_steps", "memory", "model_interactions", "agent_output"} == set(why.keys())
assert isinstance(why["input"], str)
assert isinstance(why["intermediate_steps"], list)
assert isinstance(why["memory"], dict)
assert {"procedural", "declarative", "episodic"} == set(why["memory"].keys())
assert isinstance(why["model_interactions"], list)

# model interactions
for mi in why["model_interactions"]:
    assert mi["model_type"] in ["llm", "embedder"]
    assert isinstance(mi["source"], str)
    assert isinstance(mi["prompt"], list)
    for p in mi["prompt"]:
        assert isinstance(p, str)
    assert isinstance(mi["input_tokens"], int)
    # assert mi["input_tokens"] > 0 # TODOV2: default LLM is not a ChatModel
    assert isinstance(mi["started_at"], float)
    assert mi["started_at"] < time.time()

    if mi["model_type"] == "llm":
        assert isinstance(mi["reply"], str)
        assert "You did not configure" in mi["reply"]
        assert isinstance(mi["output_tokens"], int)
        assert mi["output_tokens"] > 0
        assert isinstance(mi["ended_at"], float)
        assert mi["ended_at"] > mi["started_at"]
        assert mi["source"] == "DefaultAgent.execute"
    else:
        assert mi["model_type"] == "embedder"
        assert isinstance(mi["reply"], list)
        assert isinstance(mi["reply"][0], float)
        assert mi["source"] == "StrayCat.recall_relevant_memories_to_working_memory"
"""