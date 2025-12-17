from uuid import uuid5, NAMESPACE_DNS
from urllib.parse import urljoin
from typing import Dict

from cat import urls
from cat.env import get_env

from .base import Auth, AuthPermission, AuthResource, User

class DefaultAuth(Auth):
    """Defaul auth handler, only admin user, based on environment variables."""

    slug = "default"
    name = "Default Auth handler"
    description = "Default auth handler, only admin user, based on environment variables."

    def get_admin(self) -> User:
        return User(
            id=uuid5(NAMESPACE_DNS, "admin"),
            name="admin",
            permissions=self.get_full_permissions()
        )
    
    async def authorize_user_from_jwt(
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
        # if no user is returned, request shall not pass

    async def authorize_user_from_key(
            self,
            key: str,
            auth_resource: AuthResource,
            auth_permission: AuthPermission,
    ) -> User | None:
        
        env_key = get_env("CCAT_API_KEY")

        if (env_key is None) or (env_key == key):
            return self.get_admin()
        
        # if no user is returned, request shall not pass

    async def get_provider_login_url(
        self,
        redirect_uri: str
    ) -> str:
        
        return urljoin(
            urls.BASE_URL, f"/auth/internal-idp?redirect_uri={redirect_uri}"
        )

    async def authorize_user_from_oauth_code(
        self,
        redirect_uri: str,
        query_params: Dict 
    ) -> User | None:
        
        # mock idp, not calling /token endpoint
        #  not sure how to simulate the code
        if query_params["code"] == "1":
            return 
        
        return self.get_admin()
