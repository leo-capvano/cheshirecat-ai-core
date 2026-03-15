from cat.memory.vector_memory import VectorMemory, create_vector_memory


# This class represents the Cat long term memory (content the cat saves on disk).
class LongTermMemory:
    """Cat's non-volatile memory.

    This is an abstract class to interface with the Cat's vector memory collections.

    Attributes
    ----------
    vectors : VectorMemory
        Vector Memory collection.
    """

    def __init__(self, vector_memory_config={}):
        # Vector based memory (will store embeddings and their metadata)
        self.vectors = create_vector_memory(**vector_memory_config)

        # What type of memory is coming next?
        # Surprise surprise, my dear!
