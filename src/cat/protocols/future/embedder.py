from langchain_core.embeddings import FakeEmbeddings

class EmbedderDefault(FakeEmbeddings):
    """Defaul embedder, spits out random vectors. Used before a proper one is added."""

    def __init__(self, *args, **kwargs):
        kwargs["size"] = 128
        super().__init__(*args, **kwargs)