from uuid import uuid5, NAMESPACE_DNS

from cat.env import get_env
from cat.log import log

from .base import BaseAuth
from ..permissions import (
    AuthPermission, AuthResource
)
from ..user import User


class DefaultAuth(BaseAuth):
    """Defaul auth handler, based on environment variables."""

    def authorize_user_from_jwt(
        self,
        token: str,
        auth_resource: AuthResource,
        auth_permission: AuthPermission
    ) -> User | None:
            
        # decode token
        payload = self.decode_jwt(token)

        if payload:
            return User(
                id=payload["sub"],
                name=payload["username"],
                permissions=self.get_full_permissions()
            )
        # if nothing is returned, request shall not pass

    def authorize_user_from_key(
            self,
            key: str,
            auth_resource: AuthResource,
            auth_permission: AuthPermission,
    ) -> User | None: 
        
        ########## tmp #######
        return User(
                id=str(uuid5(NAMESPACE_DNS, "admin")),
                name="admin",
                permissions=self.get_full_permissions()
            )
        ######################

        # allow access with full permissions
        if key == get_env("CCAT_API_KEY"):
            username = get_env("CCAT_ADMIN_CREDENTIALS").split(":")[0]
            return User(
                id=str(uuid5(NAMESPACE_DNS, username)),
                name=username,
                permissions=self.get_full_permissions()
            )
        # if nothing is returned, request shall not pass