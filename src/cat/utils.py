"""Various utiles used from the projects."""

import inspect
from datetime import timedelta
from typing import Any
from pydantic import BaseModel

from rapidfuzz.distance import Levenshtein

from cat import log


def to_camel_case(text: str) -> str:
    """Format string to camel case.

    Takes a string of words separated by either hyphens or underscores and returns a string of words in camel case.

    Parameters
    ----------
    text : str
        String of hyphens or underscores separated words.

    Returns
    -------
    str
        Camel case formatted string.
    """
    s = text.replace("-", " ").replace("_", " ").capitalize()
    s = s.split()
    if len(text) == 0:
        return text
    return s[0] + "".join(i.capitalize() for i in s[1:])


def verbal_timedelta(td: timedelta) -> str:
    """Convert a timedelta in human form.

    The function takes a timedelta and converts it to a human-readable string format.

    Parameters
    ----------
    td : timedelta
        Difference between two dates.

    Returns
    -------
    str
        Human-readable string of time difference.

    Examples
    --------
    >>> verbal_timedelta(timedelta(days=2, weeks=1)
    'One week and two days ago'
    """

    if td.days != 0:
        abs_days = abs(td.days)
        if abs_days > 7:
            abs_delta = "{} weeks".format(td.days // 7)
        else:
            abs_delta = "{} days".format(td.days)
    else:
        abs_minutes = abs(td.seconds) // 60
        if abs_minutes > 60:
            abs_delta = "{} hours".format(abs_minutes // 60)
        else:
            abs_delta = "{} minutes".format(abs_minutes)
    if td < timedelta(0):
        return "{} ago".format(abs_delta)
    else:
        return "{} ago".format(abs_delta)


def levenshtein_distance(prediction: str, reference: str) -> int:
    res = Levenshtein.normalized_distance(prediction, reference)
    return res


def parse_json(
        json_string: str,
        pydantic_model: BaseModel = None
    ) -> dict | BaseModel:
    """
    Parse a JSON string produced by an LLM in an actual dictionary.
    Optionally provide a pydantic BaseModel to get an instance.
    """
    
    # to avoid circular imports
    from cat.protocols.future.llm_wrapper import LLMWrapper
    return LLMWrapper.parse_json(json_string, pydantic_model)


def get_caller_info(skip=2, return_short=True, return_string=True):
    """Get the name of a caller in the format module.class.method.

    Adapted from: https://gist.github.com/techtonik/2151727

    Parameters
    ----------
    skip :  int
        Specifies how many levels of stack to skip while getting caller name.
    return_string : bool
        If True, returns the caller info as a string, otherwise as a tuple.

    Returns
    -------
    package : str
        Caller package.
    module : str
        Caller module.
    klass : str
        Caller classname if one otherwise None.
    caller : str
        Caller function or method (if a class exist).
    line : int
        The line of the call.


    Notes
    -----
    skip=1 means "who calls me",
    skip=2 "who calls my caller" etc.

    None is returned if skipped levels exceed stack height.
    """

    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return None

    parentframe = stack[start][0]

    # module and packagename.
    module_info = inspect.getmodule(parentframe)
    if module_info:
        mod = module_info.__name__.split(".")
        package = mod[0]
        module = ".".join(mod[1:])

    # class name.
    klass = ""
    if "self" in parentframe.f_locals:
        klass = parentframe.f_locals["self"].__class__.__name__

    # method or function name.
    caller = None
    if parentframe.f_code.co_name != "<module>":  # top level usually
        caller = parentframe.f_code.co_name

    # call line.
    line = parentframe.f_lineno

    # Remove reference to frame
    # See: https://docs.python.org/3/library/inspect.html#the-interpreter-stack
    del parentframe

    if return_string:
        if return_short:
            return f"{klass}.{caller}"
        else:
            return f"{package}.{module}.{klass}.{caller}::{line}"
    return package, module, klass, caller, line


async def run_sync_or_async(f, *args, **kwargs) -> Any:
    if inspect.iscoroutinefunction(f):
        return await f(*args, **kwargs)
    path = inspect.getfile(f)
    log.deprecation_warning(f"Function {f.__name__} in {path} should be async.")
    return f(*args, **kwargs)


# This is our masterwork during tea time
class singleton:
    instances = {}

    def __new__(cls, class_):
        def getinstance(*args, **kwargs):
            if class_ not in cls.instances:
                cls.instances[class_] = class_(*args, **kwargs)
            return cls.instances[class_]

        return getinstance


