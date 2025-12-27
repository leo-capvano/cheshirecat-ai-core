# Helper classes for connection handling
# Credential extraction from ws / http connections is not delegated to the custom auth handlers,
#  to have a standard auth interface.

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from fastapi import (
    Request,
    WebSocket,
    HTTPException,
    WebSocketException,
    Depends
)

from fastapi.security.api_key import APIKeyHeader

from cat.auth import (
    AuthPermission,
    AuthResource,
    User,
)


class Connection(ABC):

    def __init__(
            self,
            resource: AuthResource | str,
            permission: AuthPermission | str,
        ):

        self.resource = resource
        self.permission = permission

    @abstractmethod
    async def __call__(self, *args, **kwargs) -> AsyncGenerator[Request | WebSocket, None]:
        pass

    @abstractmethod
    def not_allowed(self, connection: Request | WebSocket):
        pass

    async def authorize(
        self,
        connection: Request | WebSocket,
        credential: str | None
    ) -> AsyncGenerator[Request | WebSocket, None]:

        ccat = connection.app.state.ccat
        auth_handlers = await ccat.get_auth_handlers()
        for ah in auth_handlers.values():
            user: User = await ah.authorize_user_from_credential(
                credential, self.resource, self.permission
            )
            if user and isinstance(user, User):
                # Attach user to connection state
                connection.state.user = user
                # Yield the connection itself
                yield connection
                return

        # if no user was obtained, raise exception
        self.not_allowed()


class HTTPConnection(Connection):

    async def __call__(
        self,
        connection: Request,
        credential = Depends(APIKeyHeader(
            name="Authorization",
            description="Insert here your CCAT_API_KEY, or Bearer JWT token.",
            auto_error=False
        )), # this mess for the damn swagger
    ) -> AsyncGenerator[Request, None]:

        # check Authorization header
        if credential is not None:
            credential = credential.replace("Bearer ", "")
        
        # check cookies
        if credential is None:
            credential = connection.cookies.get("access_token")
        
        async for stray in self.authorize(connection, credential):
            yield stray

    def not_allowed(self):
        raise HTTPException(status_code=403, detail="Invalid Credentials")
        

# TODOV2: do websockets support headers now?
class WebsocketConnection(Connection):

    async def __call__(
        self,
        connection: WebSocket,
    ) -> AsyncGenerator[WebSocket, None]:
        
        async for stray in self.authorize(
            connection,
            connection.query_params.get("token")
        ):
            yield stray
        
    def not_allowed(self):
        raise WebSocketException(code=1004, reason="Invalid Credentials")
