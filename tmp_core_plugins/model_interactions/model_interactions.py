from cat.mad_hatter.decorators import hook

# TODOV2 clean up latest interactions in working memory as soon as message arrive
# keeping track of model interactions
# StrayCat.working_memory.model_interactions = []


# TODOV2 types
# catmesg.why.model_interactions: List[LLMModelInteraction | EmbedderModelInteraction]
# NOTE: check if why exists

# TODOV2 done doing recall
# keep track of embedder model usage
#cat.working_memory.model_interactions.append(
#    EmbedderModelInteraction(
#        prompt=[recall_query],
#        source=utils.get_caller_info(skip=1),
#        reply=recall_query_embedding, # TODO: should we avoid storing the embedding?
#        input_tokens=len(tiktoken.get_encoding("cl100k_base").encode(recall_query)),
#    )
#)


# TODOV2 handlers
# add to hook `llm_callbacks` (revise name)
# ModelInteractionHandler(cat, utils.get_caller_info(skip=1))
@hook
def llm_callbacks(callbacks, caller):
    return callbacks # TODOV2 append the handlers


# TODOV2 was attached both to working memory and why
# working_memory.model_interactions: List[ModelInteraction] = []
# CatMessage.why.model_interactions: List[ModelInteraction] = [] # check if why exists
