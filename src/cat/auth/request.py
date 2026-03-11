from __future__ import annotations

from typing import TYPE_CHECKING

import fastapi

if TYPE_CHECKING:
    from cat.auth.user import User
    from cat.looking_glass.cheshire_cat import CheshireCat


class Request(fastapi.Request):
    """Custom Request with `.user` and `.ccat` properties for ergonomic access."""

    @property
    def user(self) -> "User":
        return self.state.user

    @property
    def ccat(self) -> "CheshireCat":
        return self.app.state.ccat
