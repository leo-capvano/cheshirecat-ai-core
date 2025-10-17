# Helper classes for connection handling
# Credential extraction from ws / http connections is not delegated to the custom auth handlers,
#  to have a standard auth interface.

from abc import ABC, abstractmethod
from typing import AsyncGenerator
from urllib.parse import urlencode

from fastapi import (
    Request,
    WebSocket,
    HTTPException,
    WebSocketException,
    Depends
)
from fastapi.requests import HTTPConnection
from fastapi.security.api_key import APIKeyHeader

from cat.auth.permissions import (
    AuthPermission,
    AuthResource,
    User,
)
from cat.looking_glass.stray_cat import StrayCat
from cat.log import log


class BaseAuth(ABC):

    def __init__(
            self,
            resource: AuthResource | str,
            permission: AuthPermission | str,
        ):

        self.resource = resource
        self.permission = permission

    @abstractmethod
    async def __call__(self, *args, **kwargs) -> AsyncGenerator[StrayCat, None]:
        pass

    @abstractmethod
    def not_allowed(self, connection: HTTPConnection):
        pass

    async def authorize(
        self,
        connection: HTTPConnection,
        credential: str | None
    ) -> AsyncGenerator[StrayCat | None, None]:
        
        for ah in connection.app.state.ccat.auth_handlers.values():
            user: User = await ah.authorize_user_from_credential(
                credential, self.resource, self.permission
            )
            if user:
                # create new StrayCat
                cat = StrayCat(user, connection.app.state.ccat)
                
                # StrayCat is passed to the endpoint
                yield cat

                return

        # if no StrayCat was obtained, raise exception
        self.not_allowed()


class HTTPAuth(BaseAuth):

    async def __call__(
        self,
        connection: Request,
        credential = Depends(APIKeyHeader(
            name="Authorization",
            description="Insert here your CCAT_API_KEY. Default is: meow",
            auto_error=False
        )), # this mess for the damn swagger
    ) -> AsyncGenerator[StrayCat | None, None]:

        if credential is not None:
            credential = credential.replace("Bearer ", "")
        
        async for stray in self.authorize(connection, credential):
            yield stray

    def not_allowed(self):
        raise HTTPException(status_code=403, detail="Invalid Credentials")
        

# TODOV2: do websockets support headers now?
class WebsocketAuth(BaseAuth):

    async def __call__(
        self,
        connection: WebSocket,
    ) -> AsyncGenerator[StrayCat | None, None]:
        
        async for stray in self.authorize(
            connection,
            connection.query_params.get("token")
        ):
            yield stray
        
    def not_allowed(self):
        raise WebSocketException(code=1004, reason="Invalid Credentials")
