from cat.auth import get_user, User

from .settings import router

@router.get("")
async def get_user_info(
    user: User = get_user(),
) -> User:
    """Returns user information."""
    return user
