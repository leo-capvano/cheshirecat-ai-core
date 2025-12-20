



from cat.auth.permissions import AuthPermission, AuthResource, get_user
from cat.auth.user import User

from .settings import router

@router.get("")
async def get_user_info(
    user: User = get_user(AuthResource.CHAT, AuthPermission.READ),
) -> User:
    """Returns user information."""
    return user


