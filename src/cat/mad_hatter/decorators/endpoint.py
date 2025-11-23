from typing import Callable
from fastapi import APIRouter
from cat.log import log


class CatEndpoint(APIRouter):

    def __repr__(self) -> str:
        if hasattr(self, 'plugin_id'):
            plugin = self.plugin_id # will be added by mad hatter
        else:
            plugin = "unkwown"
        return f"CatEndpoint(plugin={plugin} routes={self.routes})"


class CatEndpointDecorator:

    def _wrap(self, method: str, path: str, **kwargs):

        def decorator(func: Callable):
            
            prefix = kwargs.pop("prefix", "")
            full_path = f"{prefix}{path}"

            router = CatEndpoint()
            router.add_api_route(
                path=full_path,
                endpoint=func,
                methods=[method.upper()],
                **kwargs
            )

            return router
        return decorator

    def get(self, path: str, **kwargs):
        return self._wrap("get", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._wrap("post", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self._wrap("put", path, **kwargs)
    
    def patch(self, path: str, **kwargs):
        return self._wrap("patch", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._wrap("delete", path, **kwargs)


endpoint = CatEndpointDecorator()