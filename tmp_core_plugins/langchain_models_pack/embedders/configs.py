





# class EmbedderOpenAICompatibleConfig(EmbedderSettings):
#     url: str
#     _pyclass: Type = CustomOpenAIEmbeddings

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "OpenAI-compatible API embedder",
#             "description": "Configuration for OpenAI-compatible API embeddings",
#             "link": "",
#         }
#     )

# class EmbedderOllamaConfig(EmbedderSettings):
#     base_url: str
#     model: str = "mxbai-embed-large"
#     _pyclass: Type = CustomOllamaEmbeddings

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Ollama embeddding models",
#             "description": "Configuration for Ollama embeddings API",
#             "link": "",
#             "model": "mxbai-embed-large",
#         }
#     )


# class EmbedderOpenAIConfig(EmbedderSettings):
#     openai_api_key: str
#     model: str = "text-embedding-ada-002"
#     _pyclass: Type = OpenAIEmbeddings

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "OpenAI Embedder",
#             "description": "Configuration for OpenAI embeddings",
#             "link": "https://platform.openai.com/docs/models/overview",
#         }
#     )


# # https://python.langchain.com/en/latest/_modules/langchain/embeddings/openai.html#OpenAIEmbeddings
# class EmbedderAzureOpenAIConfig(EmbedderSettings):
#     openai_api_key: str
#     model: str
#     azure_endpoint: str
#     openai_api_type: str = "azure"
#     openai_api_version: str
#     deployment: str

#     _pyclass: Type = AzureOpenAIEmbeddings

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Azure OpenAI Embedder",
#             "description": "Configuration for Azure OpenAI embeddings",
#             "link": "https://azure.microsoft.com/en-us/products/ai-services/openai-service",
#         }
#     )


# # Enum for menu selection in the admin!
# FastEmbedModels = Enum(
#     "FastEmbedModels",
#     {
#         item["model"].replace("/", "_").replace("-", "_"): item["model"]
#         for item in TextEmbedding.list_supported_models()
#     },
# )


# class EmbedderQdrantFastEmbedConfig(EmbedderSettings):
#     model_name: FastEmbedModels = Field(title="Model name", default="BAAI/bge-base-en")
#     # Unknown behavior for values > 512.
#     max_length: int = 512
#     # as suggest on fastembed documentation, "passage" is the best option for documents.
#     doc_embed_type: str = "passage"
#     cache_dir: str = "data/models/fast_embed" # TODOV2: data folder is not there anymore

#     _pyclass: Type = FastEmbedEmbeddings

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Qdrant FastEmbed (Local)",
#             "description": "Configuration for Qdrant FastEmbed",
#             "link": "https://qdrant.github.io/fastembed/",
#         }
#     )


# class EmbedderGeminiChatConfig(EmbedderSettings):
#     """Configuration for Gemini Chat Embedder.

#     This class contains the configuration for the Gemini Embedder.
#     """

#     google_api_key: str
#     # Default model https://python.langchain.com/docs/integrations/text_embedding/google_generative_ai
#     model: str = "models/embedding-001"

#     _pyclass: Type = GoogleGenerativeAIEmbeddings

#     model_config = ConfigDict(
#         json_schema_extra={
#             "humanReadableName": "Google Gemini Embedder",
#             "description": "Configuration for Gemini Embedder",
#             "link": "https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/text-embeddings?hl=en",
#         }
#     )