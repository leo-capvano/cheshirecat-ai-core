from typing import Dict
from fastapi import Request, APIRouter, HTTPException

from cat.mad_hatter.decorators import endpoint
from cat.looking_glass.cheshire_cat import CheshireCat
from cat.auth import AuthPermission, AuthResource, check_permissions
from cat.looking_glass.stray_cat import StrayCat
from cat import log

from ..vector_memory import VectorMemory

# TODOV2: add POST method to create collection
# TODOV2: take away procedural collection for internal use
# TODOV2: no need to force the three classic collections, allow extension

# GET collection list with some metadata
@endpoint.get("/collections", prefix="/memory", tags=["Vector Memory"])
async def get_collections(
    request: Request,
    cat: StrayCat = check_permissions("MEMORY", AuthPermission.READ)
) -> Dict:
    """Get list of available collections"""
    
    vector_memory: VectorMemory = cat.memory.vectors
    collections = list(vector_memory.collections.keys())
    
    collections_metadata = []
    for c in collections:
        coll_meta = vector_memory.get_collection(c)
        collections_metadata.append({
            "name": c,
            "vectors_count": coll_meta.points_count
        })

    return {"collections": collections_metadata}


# DELETE all collections
@endpoint.delete("/collections", prefix="/memory", tags=["Vector Memory"])
async def wipe_collections(
    request: Request,
    cat: StrayCat = check_permissions("MEMORY", AuthPermission.DELETE),
) -> Dict:
    """Delete and create all collections"""

    vector_memory: VectorMemory = cat.memory.vectors
    collections = list(vector_memory.collections.keys())

    to_return = {}
    for c in collections:
        ret = vector_memory.delete_collection(c)
        to_return[c] = ret
    
    #ccat: CheshireCat = request.app.state.ccat
    #ccat.load_memory()  # recreate the long term memories
    #ccat.mad_hatter.find_plugins() # should not be needed!

    return {
        "deleted": to_return,
    }


# DELETE one collection
@endpoint.delete("/collections/{collection_id}", prefix="/memory", tags=["Vector Memory"])
async def wipe_single_collection(
    request: Request,
    collection_id: str,
    cat: StrayCat = check_permissions("MEMORY", AuthPermission.DELETE),
) -> Dict:
    """Delete and recreate a collection"""

    vector_memory: VectorMemory = cat.memory.vectors
    collections = list(vector_memory.collections.keys())
    
    if collection_id not in collections:
        raise HTTPException(
            status_code=400, detail="Collection does not exist."
        )

    to_return = {}
    ret = vector_memory.delete_collection(collection_id)
    to_return[collection_id] = ret

    #ccat: CheshireCat = request.app.state.ccat
    #ccat.load_memory()  # recreate the long term memories
    #ccat.mad_hatter.find_plugins() # should not be needed!

    return {
        "deleted": to_return,
    }


