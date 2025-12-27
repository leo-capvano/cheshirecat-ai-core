from abc import ABC, abstractmethod
from typing import Dict, List
from datetime import datetime, timedelta

from pytz import utc
import jwt
from jwt.exceptions import InvalidTokenError

from cat.auth.permissions import (
    AuthPermission, AuthResource
)
from cat.auth.user import User
from cat.env import get_env
from cat import log

from ..service import SingletonService

class Auth(ABC, SingletonService):
    """
    Base class to build custom Auth systems.
    """

    service_type = "auths"

    def get_full_permissions(self) -> Dict[AuthResource, List[AuthPermission]]:
        """
        Returns all available resources and permissions.
        """
        # TODOV2: should include plugins defined permissions
        perms = {}
        for res in AuthResource:
            perms[res.name] = [p.name for p in AuthPermission]
        return perms


    def get_base_permissions(self) -> Dict[AuthResource, List[AuthPermission]]:
        """
        Returns the default permissions for new users (chat only!).
        """

        all_permissions = [p.name for p in AuthPermission]

        # TODOV2: should include plugins defined permissions
        return {
            AuthResource.CHAT: all_permissions,
            AuthResource.FILE: all_permissions,
        }
        
    def is_jwt(self, token: str) -> bool:
        """
        Returns whether a given string is a JWT.
        """
        try:
            # Decode the JWT without verification to check its structure
            jwt.decode(token, options={"verify_signature": False})
            return True
        except InvalidTokenError:
            return False

    def issue_jwt(self, user: User) -> str | None:
        
        # TODOAUTH: expiration with timezone needs to be tested
        # using seconds for easier testing
        expire_delta_in_seconds = float(get_env("CCAT_JWT_EXPIRE_MINUTES")) * 60
        expires = datetime.now(utc) + timedelta(seconds=expire_delta_in_seconds)

        jwt_content = {
            "sub": str(user.id),                 # Subject (the user ID)
            "username": user.name,               # Username
            "permissions": user.permissions,     # User permissions
            "custom": user.custom,                 # Additional information
            "exp": expires                       # Expiry date as a Unix timestamp
        }
        return jwt.encode(
            jwt_content,
            get_env("CCAT_JWT_SECRET"),
            algorithm="HS256",
        )
    
    def decode_jwt(self, token) -> dict:
        """Decode jwt.
        Will return None if not able to decode or signature is wrong."""
        try:
            payload = jwt.decode(
                token,
                get_env("CCAT_JWT_SECRET"),
                algorithms=["HS256"],
            )
            return payload
        except Exception:
            log.warning("Could not decode JWT")

    async def authorize_user_from_credential(
        self,
        credential: str,
        auth_resource: AuthResource,
        auth_permission: AuthPermission,
    ) -> User | None:

        if self.is_jwt(credential):
            # JSON Web Token auth
            return await self.authorize_user_from_jwt(
                credential, auth_resource, auth_permission
            )
        else:
            # API_KEY auth
            return await self.authorize_user_from_key(
                credential, auth_resource, auth_permission
            )
    
    @abstractmethod
    async def authorize_user_from_jwt(
        self,
        token: str,
        auth_resource: AuthResource,
        auth_permission: AuthPermission
    ) -> User | None:
        pass

    @abstractmethod
    async def authorize_user_from_key(
        self,
        api_key: str,
        auth_resource: AuthResource,
        auth_permission: AuthPermission
    ) -> User | None:
        pass

    async def get_provider_login_url(
        self,
        redirect_uri: str
    ) -> str:
        """Return the OAuth provider login URL.
        Implement this method to have your Auth handler support OAuth.
        """
        raise Exception(
            "To support OAuth, auth handlers must implement " +
            "`build_redirect_uri` and `authorize_user_from_oauth_code`"
        )

    async def authorize_user_from_oauth_code(
        self,
        redirect_uri: str,
        query_params: Dict 
    ) -> User | None:
        """
        Exchange OAuth provider code/state for user info and map it to internal User.
        Implement this method to have your Auth handler support OAuth.
        """
        raise Exception(
            "To support OAuth, auth handlers must implement " +
            "`build_redirect_uri` and `authorize_user_from_oauth_code`"
        )