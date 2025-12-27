
from typing import List, TYPE_CHECKING

from cat.types import Context
from ..service import RequestService


class Directive(RequestService):
    """Base class for a Directive, to inspect and change model context before generation."""

    service_type = "directives"

    async def step(self, context: Context) -> Context | None:
        """
        Modify the model context before generation. Override in subclasses.

        Parameters
        ----------
        context : Context
            The model context to modify.
        user : User
            The user storing the resources.
        """
        return context