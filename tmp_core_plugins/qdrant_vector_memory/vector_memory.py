import sys
import socket
import time

from qdrant_client import QdrantClient

from cat import log
from cat.env import get_env
from cat.utils import get_data_path
from cat.utils import extract_domain_from_url, is_https
from cat.mad_hatter.decorators import hook

from .vector_memory_collection import VectorMemoryCollection

@hook
def after_cat_bootstrap(cat):

    #### TODOV2 #####
    return
    ########

    """
    # Load Memory and add it to CheshireCat core

    # Get embedder size (langchain classes do not store it)
    embedder_size = len(cat.embedder.embed_query("hello world"))

    # Get embedder name (useful for for vectorstore aliases)
    if hasattr(cat.embedder, "model"):
        embedder_name = cat.embedder.model
    elif hasattr(cat.embedder, "repo_id"):
        embedder_name = cat.embedder.repo_id
    else:
        embedder_name = "default_embedder"

    # instantiate long term memory
    vector_memory_config = {
        "embedder_name": embedder_name,
        "embedder_size": embedder_size,
    }

    cat.memory.vectors = VectorMemory(
        embedder_name=embedder_name,
        embedder_size=embedder_size
    )
    """


@hook
def before_cat_sends_message(msg, cat):
    
    # Store conversation turns with session id
    pass
    #human_message = {}
    #cat.store()

    #cat_message = {}
    #cat.store()

    # user_message_text = cat.working_memory.user_message_json.text
    #doc = Document(
    #    page_content=user_message_text,
    #    metadata={"source": self.user_id, "when": time.time()},
    #)
    #doc = self.mad_hatter.execute_hook(
    #    "before_cat_stores_episodic_memory", doc, cat=self
    #)
    # store user message in episodic memory
    #user_message_embedding = self.embedder.embed_documents([user_message_text])
    #_ = self.memory.vectors.episodic.add_point(
    #    doc.page_content,
    #    user_message_embedding[0],
    #    doc.metadata,
    #)

def build_embedded_procedures_hashes(self, embedded_procedures):
    hashes = {}
    for ep in embedded_procedures:
        metadata = ep.payload["metadata"]
        content = ep.payload["page_content"]
        source = metadata["source"]
        # there may be legacy points with no trigger_type
        trigger_type = metadata.get("trigger_type", "unsupported")

        p_hash = f"{source}.{trigger_type}.{content}"
        hashes[p_hash] = ep.id

    return hashes


def build_active_procedures_hashes(self, active_procedures):
    hashes = {}
    for ap in active_procedures:
        for trigger_type, trigger_list in ap.triggers_map.items():
            for trigger_content in trigger_list:
                p_hash = f"{ap.name}.{trigger_type}.{trigger_content}"
                hashes[p_hash] = {
                    "obj": ap,
                    "source": ap.name,
                    "type": ap.procedure_type,
                    "trigger_type": trigger_type,
                    "content": trigger_content,
                }
    return hashes

# TODOV2: still not attached to core
def embed_procedures(self):
    # Retrieve from vectorDB all procedural embeddings
    embedded_procedures, _ = self.memory.vectors.procedural.get_all_points()
    embedded_procedures_hashes = self.build_embedded_procedures_hashes(
        embedded_procedures
    )

    # Easy access to active procedures in mad_hatter (source of truth!)
    active_procedures_hashes = self.build_active_procedures_hashes(
        self.mad_hatter.procedures
    )

    # points_to_be_kept     = set(active_procedures_hashes.keys()) and set(embedded_procedures_hashes.keys()) not necessary
    points_to_be_deleted = set(embedded_procedures_hashes.keys()) - set(
        active_procedures_hashes.keys()
    )
    points_to_be_embedded = set(active_procedures_hashes.keys()) - set(
        embedded_procedures_hashes.keys()
    )

    points_to_be_deleted_ids = [
        embedded_procedures_hashes[p] for p in points_to_be_deleted
    ]
    if points_to_be_deleted_ids:
        log.info("Deleting procedural triggers:")
        log.info(points_to_be_deleted)
        self.memory.vectors.procedural.delete_points(points_to_be_deleted_ids)

    active_triggers_to_be_embedded = [
        active_procedures_hashes[p] for p in points_to_be_embedded
    ]
    
    if active_triggers_to_be_embedded:
        log.info("Embedding new procedural triggers:")
    for t in active_triggers_to_be_embedded:


        metadata = {
            "source": t["source"],
            "type": t["type"],
            "trigger_type": t["trigger_type"],
            "when": time.time(),
        }

        trigger_embedding = self.embedder.embed_documents([t["content"]])
        self.memory.vectors.procedural.add_point(
            t["content"],
            trigger_embedding[0],
            metadata,
        )

        log.info(
            f" {t['source']}.{t['trigger_type']}.{t['content']}"
        )


class VectorMemory:
    local_vector_db = None

    def __init__(
        self,
        embedder_name=None,
        embedder_size=None,
    ) -> None:
        # connects to Qdrant and creates self.vector_db attribute
        self.connect_to_vector_memory()

        # Create vector collections
        # - Episodic memory will contain user and eventually cat utterances
        # - Declarative memory will contain uploaded documents' content
        # - Procedural memory will contain tools and knowledge on how to do things
        self.collections = {}
        for collection_name in ["episodic", "declarative", "procedural"]:
            # Instantiate collection
            collection = VectorMemoryCollection(
                client=self.vector_db,
                collection_name=collection_name,
                embedder_name=embedder_name,
                embedder_size=embedder_size,
            )

            # Update dictionary containing all collections
            # Useful for cross-searching and to create/use collections from plugins
            self.collections[collection_name] = collection

            # Have the collection as an instance attribute
            # (i.e. do things like cat.memory.vectors.declarative.something())
            setattr(self, collection_name, collection)

    def connect_to_vector_memory(self) -> None:
        db_path = get_data_path() + "/local_vector_memory/"
        qdrant_host = get_env("CCAT_QDRANT_HOST")

        if not qdrant_host:
            log.debug(f"Qdrant path: {db_path}")
            # Qdrant local vector DB client

            # reconnect only if it's the first boot and not a reload
            if VectorMemory.local_vector_db is None:
                VectorMemory.local_vector_db = QdrantClient(
                    path=db_path, force_disable_check_same_thread=True
                )

            self.vector_db = VectorMemory.local_vector_db
        else:
            # Qdrant remote or in other container
            qdrant_port = int(get_env("CCAT_QDRANT_PORT"))
            qdrant_https = is_https(qdrant_host)
            qdrant_host = extract_domain_from_url(qdrant_host)
            qdrant_api_key = get_env("CCAT_QDRANT_API_KEY")
            
            qdrant_client_timeout = get_env("CCAT_QDRANT_CLIENT_TIMEOUT")
            qdrant_client_timeout = int(qdrant_client_timeout) if qdrant_client_timeout is not None else None

            try:
                s = socket.socket()
                s.connect((qdrant_host, qdrant_port))
            except Exception:
                log.error(f"QDrant does not respond to {qdrant_host}:{qdrant_port}")
                sys.exit()
            finally:
                s.close()

            # Qdrant vector DB client
            self.vector_db = QdrantClient(
                host=qdrant_host,
                port=qdrant_port,
                https=qdrant_https,
                api_key=qdrant_api_key,
                timeout=qdrant_client_timeout
            )

    def delete_collection(self, collection_name: str):
        """Delete specific vector collection"""
        
        return self.vector_db.delete_collection(collection_name)
    
    def get_collection(self, collection_name: str):
        """Get collection info"""
        
        return self.vector_db.get_collection(collection_name)
