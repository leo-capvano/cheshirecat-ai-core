import os
import glob
import shutil
import inspect
from copy import deepcopy
from typing import List, Dict, Any, Callable
from pathlib import Path

from cat.log import log
import cat.utils as utils
from cat.db.models import SettingDB
from cat.mad_hatter.plugin_extractor import PluginExtractor
from cat.mad_hatter.plugin import Plugin
from cat.mad_hatter.decorators.hook import CatHook
from cat.mad_hatter.decorators.tool import CatTool
from cat.mad_hatter.decorators.endpoint import CatEndpoint


# This class is responsible for plugins functionality:
# - loading
# - prioritizing
# - executing
class MadHatter:
    """Plugin manager"""

    def __init__(self):

        # plugins dictionary, contains all of them (active and inactive)
        # it is kept in sync with the contents of plugin folders
        # for a list of active plugins (stored in db), see MadHatter.get_active_plugins
        self.plugins: Dict[str, Plugin] = {}

        # caches for decorated functions
        self.hooks: Dict[str, List[CatHook]] = {}
        self.tools: List[CatTool] = []
        self.endpoints: List[CatEndpoint] = []

        # callback out of the hook system to notify other components about a refresh
        self.on_refresh_callbacks: List[Callable] = []

    async def install_plugin(self, package_plugin) -> Plugin:
        # extract zip/tar file into plugin folder
        extractor = PluginExtractor(package_plugin)
        plugin_path = extractor.extract(utils.get_plugins_path())

        # remove zip after extraction
        os.remove(package_plugin)

        # create plugin obj
        try:
            plugin = Plugin(plugin_path)
        except Exception as e:
            log.error("Could not install plugin in {plugin_path}. Removing it.")
            shutil.rmtree(plugin_path)
            raise e

        # activate it
        self.plugins[plugin.id] = plugin
        await self.toggle_plugin(plugin.id)
        return self.plugins[plugin.id]

    async def uninstall_plugin(self, plugin_id):

        # plugin exists and it is not a core plugin
        if not self.plugin_exists(plugin_id):
            raise Exception(f"Plugin {plugin_id} is not installed")

        # deactivate plugin if it is active (will sync cache)
        if plugin_id in await self.get_active_plugins():
            await self.toggle_plugin(plugin_id)

        # remove plugin from cache
        plugin_path = self.plugins[plugin_id].path
        del self.plugins[plugin_id]

        # remove plugin folder
        shutil.rmtree(plugin_path)

    async def find_plugins(self):
        # emptying plugin dictionary, plugins will be discovered from disk
        # and stored in a dictionary plugin_id -> plugin_obj
        self.plugins = {}

        # active plugins ids (stored in db)
        active_plugins = await self.get_active_plugins()

        # plugins are found in the `./plugins` folder
        all_plugin_folders = \
            glob.glob( f"{utils.get_plugins_path()}/*/")

        log.info("Active Plugins:")
        log.info(active_plugins)

        # discover plugins, folder by folder
        for folder in all_plugin_folders:
            try:
                plugin = Plugin(folder)
                self.plugins[plugin.id] = plugin
                if plugin.id in active_plugins:
                    plugin.activate()
            except Exception:
                log.error(f"Could not load plugin in {folder}")

        await self.refresh_caches()

    # Load decorated functions from active plugins into MadHatter
    async def refresh_caches(self):
        # emptying caches
        self.hooks = {}
        self.tools = []
        self.endpoints = []

        for _, plugin in self.plugins.items():
            # load decorated funcs from plugins (only active ones have them populated)
            self.tools += plugin.tools
            self.endpoints += plugin.endpoints

            # cache hooks (indexed by hook name)
            for h in plugin.hooks:
                if h.name not in self.hooks.keys():
                    self.hooks[h.name] = []
                self.hooks[h.name].append(h)

        # sort each hooks list by priority
        for hook_name in self.hooks.keys():
            self.hooks[hook_name].sort(key=lambda x: x.priority, reverse=True)

        # Notify subscribers about finished refresh
        for callback in self.on_refresh_callbacks:
            await utils.run_sync_or_async(callback)

    def plugin_exists(self, plugin_id) -> bool:
        """Check if a plugin exists locally."""
        return plugin_id in self.plugins.keys()

    async def get_active_plugins(self):
        active_plugins = await SettingDB.get(name="active_plugins")
        return active_plugins.value
    
    async def set_active_plugins(self, active_plugins):
        ap = await SettingDB.get(name="active_plugins")
        ap.value = list(set(active_plugins))
        await ap.save()

    async def toggle_plugin(self, plugin_id):
        """Activate / deactivate a plugin."""

        if not self.plugin_exists(plugin_id):
            raise Exception(f"Plugin {plugin_id} not present in plugins folder")

        active_plugins = await self.get_active_plugins()
        plugin_is_active = plugin_id in active_plugins

        # update list of active plugins
        if plugin_is_active:
            log.warning(f"Toggle plugin {plugin_id}: Deactivate")

            # Deactivate the plugin
            self.plugins[plugin_id].deactivate()
            # Remove the plugin from the list of active plugins
            active_plugins.remove(plugin_id)
        else:
            log.warning(f"Toggle plugin {plugin_id}: Activate")

            # Activate the plugin
            try:
                self.plugins[plugin_id].activate()
                # Add the plugin in the list of active plugins
                active_plugins.append(plugin_id)
            except Exception as e:
                # Couldn't activate the plugin
                raise e

        # update DB with list of active plugins, delete duplicate plugins
        await self.set_active_plugins(active_plugins)
        # update cache
        await self.refresh_caches()


    def execute_hook(self, hook_name, *args, cat) -> Any:
        """Execute a hook."""

        # check if hook is supported
        if hook_name not in self.hooks.keys():
            log.debug(f"Hook {hook_name} not present in any plugin")
            if len(args)==0:
                return
            else:
                return args[0]

        # Hook has no arguments (aside cat)
        #  no need to pipe
        if len(args) == 0:
            for hook in self.hooks[hook_name]:
                try:
                    log.debug(
                        f"Executing {hook.plugin_id}::{hook.name} with priority {hook.priority}"
                    )
                    hook.function(cat=cat)
                except Exception:
                    log.error(f"Error in plugin {hook.plugin_id}::{hook.name}")
                    plugin_obj = self.plugins[hook.plugin_id]
                    log.warning(plugin_obj.plugin_specific_error_message())
            return

        # Hook with arguments.
        #  First argument is passed to `execute_hook` is the pipeable one.
        #  We call it `tea_cup` as every hook called will receive it as an input,
        #  can add sugar, milk, or whatever, and return it for the next hook
        tea_cup = deepcopy(args[0])

        # run hooks
        for hook in self.hooks[hook_name]:
            try:
                # pass tea_cup to the hooks, along other args
                # hook has at least one argument, and it will be piped
                log.debug(
                    f"Executing {hook.plugin_id}::{hook.name} with priority {hook.priority}"
                )
                tea_spoon = hook.function(
                    deepcopy(tea_cup), *deepcopy(args[1:]), cat=cat
                )
                # log.debug(f"Hook {hook.plugin_id}::{hook.name} returned {tea_spoon}")
                if tea_spoon is not None:
                    tea_cup = tea_spoon
            except Exception:
                log.error(f"Error in plugin {hook.plugin_id}::{hook.name}")
                plugin_obj = self.plugins[hook.plugin_id]
                log.warning(plugin_obj.plugin_specific_error_message())

        # tea_cup has passed through all hooks. Return final output
        return tea_cup

    def get_plugin(self):
        """Get plugin object (used from within a plugin)"""

        # who's calling?
        calling_frame = inspect.currentframe().f_back
        # Get the module associated with the frame
        module = inspect.getmodule(calling_frame)
        # Get the absolute and then relative path of the calling module's file
        abs_path = inspect.getabsfile(module)
        
        # Replace the root and get only the current plugin folder
        plugin_suffix = os.path.normpath(
            abs_path.replace(utils.get_plugins_path() + "/", "")
        )
        # Plugin's folder
        name = plugin_suffix.split("/")[0]
        return self.plugins[name]

