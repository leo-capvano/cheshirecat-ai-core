from cat import log
from .hook_context import HookContext

StrayCat = HookContext  # for backward compatibility

def wrn():
    log.deprecation_warning("StrayCat is deprecated, use HookContext instead.")
wrn()