from langchain_core.embeddings import FakeEmbeddings

class DefaultEmbedder(FakeEmbeddings):
    """Defaul LLM, replying with random numbers. Used before a proper one is added."""
    
    size: int = 8