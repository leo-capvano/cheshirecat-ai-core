from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from cat.mad_hatter.decorators import hook, plugin
from cat.env import get_env


# TODOV2: make discovery automatic by checking class type

# @hook
# def factory_allowed_embedders(configs, cat):
    
#     return configs + [
#         embedders_configs.EmbedderQdrantFastEmbedConfig,
#         embedders_configs.EmbedderOllamaConfig,
#         embedders_configs.EmbedderOpenAIConfig,
#         embedders_configs.EmbedderOpenAICompatibleConfig,
#         embedders_configs.EmbedderAzureOpenAIConfig,
#         embedders_configs.EmbedderGeminiChatConfig,
#     ]


class OpenAISettings(BaseModel):
    openai_api_key: str
    temperature: float = 0.5
    streaming: bool = True

@plugin
def settings_model():
    return OpenAISettings 


@hook
def factory_allowed_llms(models, cat):

    # insert new vendor slug
    vendor = "openai"
    
    # build an object for each model
    for m in ["gpt-5-nano", "gpt-5-mini", "gpt-5", "gpt-4.1", "gpt-4", "gpt-4o"]:
        slug = f"{vendor}:{m}"  # "openai:gpt-5"
        models[slug] = ChatOpenAI(
            model = m,
            api_key = get_env("OPENAI_KEY"), # TODOV2: load it from plugin settings
            temperature = 0.2,
            streaming = True
        )
        # TODOV2: not yet loading the settings

    return models
