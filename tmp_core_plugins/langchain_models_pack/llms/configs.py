



# class LLMOpenAICompatibleConfig(LLMSettings):
#     url: str
#     temperature: float = 0.01
#     model_name: str
#     api_key: str
#     streaming: bool = True
#     _pyclass: Type = CustomOpenAI

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "OpenAI-compatible API",
#             "description": "Configuration for OpenAI-compatible APIs, e.g. llama-cpp-python server, text-generation-webui, OpenRouter, TinyLLM, TogetherAI and many others.",
#             "link": "",
#         }
#     )


# class LLMOpenAIChatConfig(LLMSettings):
#     openai_api_key: str
#     model_name: str = "gpt-4o-mini"
#     temperature: float = 0.7
#     streaming: bool = True
#     _pyclass: Type = ChatOpenAI

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "OpenAI ChatGPT",
#             "description": "Chat model from OpenAI",
#             "link": "https://platform.openai.com/docs/models/overview",
#         }
#     )


# class LLMOllamaConfig(LLMSettings):
#     base_url: str
#     model: str = "llama3"
#     num_ctx: int = 2048
#     repeat_last_n: int = 64
#     repeat_penalty: float = 1.1
#     temperature: float = 0.8

#     _pyclass: Type = CustomOllama

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Ollama",
#             "description": "Configuration for Ollama",
#             "link": "https://ollama.ai/library",
#         }
#     )


# class LLMGeminiChatConfig(LLMSettings):
#     """Configuration for the Gemini large language model (LLM).

#     This class inherits from the `LLMSettings` class and provides default values for the following attributes:

#     * `google_api_key`: The Google API key used to access the Google Natural Language Processing (NLP) API.
#     * `model`: The name of the LLM model to use. In this case, it is set to "gemini".
#     * `temperature`: The temperature of the model, which controls the creativity and variety of the generated responses.
#     * `top_p`: The top-p truncation value, which controls the probability of the generated words.
#     * `top_k`: The top-k truncation value, which controls the number of candidate words to consider during generation.
#     * `max_output_tokens`: The maximum number of tokens to generate in a single response.

#     The `LLMGeminiChatConfig` class is used to create an instance of the Gemini LLM model, which can be used to generate text in natural language.
#     """

#     google_api_key: str
#     model: str = "gemini-1.5-pro-latest"
#     temperature: float = 0.1
#     top_p: int = 1
#     top_k: int = 1
#     max_output_tokens: int = 29000

#     _pyclass: Type = ChatGoogleGenerativeAI

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Google Gemini",
#             "description": "Configuration for Gemini",
#             "link": "https://deepmind.google/technologies/gemini",
#         }
#     )


# class LLMAnthropicChatConfig(LLMSettings):
#     api_key: str
#     model: str = "claude-3-5-sonnet-20241022"
#     temperature: float = 0.7
#     max_tokens: int = 8192
#     max_retries: int = 2

#     _pyclass: Type = ChatAnthropic

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Anthropic",
#             "description": "Configuration for Anthropic",
#             "link": "https://www.anthropic.com/",
#         }
#     )