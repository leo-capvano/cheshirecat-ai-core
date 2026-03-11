from pydantic import BaseModel

from cat.mad_hatter.decorators import endpoint
from cat.auth import get_user, User

class Item(BaseModel):
    name: str
    description: str

@endpoint.endpoint(path="/endpoint", methods=["GET"])
def test_endpoint():
    return {"result":"endpoint default prefix"}

@endpoint.endpoint(path="/endpoint", prefix="/tests", methods=["GET"], tags=["Tests"])
def test_endpoint_prefix():
    return {"result":"endpoint prefix tests"}

# from this one on endpoints are secured with permissions checks
@endpoint.get(path="/crud", prefix="/tests", tags=["Tests"])
def test_get(user: User = get_user("plugins:list")):
    return {"result":"ok", "user_id": str(user.id)}

@endpoint.post(path="/crud", prefix="/tests", tags=["Tests"])
def test_post(
    item: Item,
    user: User = get_user("plugins:edit")
):
    return {"id": 1, "name": item.name, "description": item.description}

@endpoint.put(path="/crud/{item_id}", prefix="/tests", tags=["Tests"])
def test_put(
    item_id: int,
    item: Item,
    user: User = get_user("plugins:write")
):
    return {"id": item_id, "name": item.name, "description": item.description}

@endpoint.delete(path="/crud/{item_id}", prefix="/tests", tags=["Tests"])
def test_delete(
    item_id: int,
    user: User = get_user("plugins:delete")
):
    return {"result": "ok", "deleted_id": item_id}

@endpoint.get(path="/permission", prefix="/tests", tags=["Tests"])
def test_custom_permissions(
    user: User = get_user("custom-resource:custom-permission")
):
    return {"result": "ok"}
