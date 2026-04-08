# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Plugin System
Dynamic plugin loading and management for extending functionality
"""
import os
import json
import importlib
import inspect
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod

from .config import VERSION, USER_HOME

logger = logging.getLogger("sokol.plugins")


@dataclass
class PluginMetadata:
    """Plugin metadata structure"""
    name: str
    version: str
    description: str
    author: str
    category: str
    tags: List[str]
    dependencies: List[str]
    min_sokol_version: str
    max_sokol_version: Optional[str]
    entry_point: str
    config_schema: Optional[Dict[str, Any]]
    permissions: List[str]
    enabled: bool = True


@dataclass
class PluginInfo:
    """Plugin information with runtime data"""
    metadata: PluginMetadata
    module: Optional[Any]
    instance: Optional[Any]
    loaded: bool = False
    enabled: bool = True
    load_time: Optional[datetime] = None
    error: Optional[str] = None
    stats: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = {}


class PluginInterface(ABC):
    """Base interface for all plugins"""
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize plugin with configuration"""
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """Shutdown plugin and cleanup resources"""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get plugin runtime information"""
        pass
    
    def get_commands(self) -> List[Dict[str, Any]]:
        """Get plugin commands (optional)"""
        return []
    
    def handle_command(self, command: str, params: Dict[str, Any]) -> Any:
        """Handle plugin command (optional)"""
        return None
    
    def on_sokol_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle Sokol events (optional)"""
        pass


class PluginManager:
    """Main plugin manager for loading and managing plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, PluginInfo] = {}
        self.plugin_dirs = [
            os.path.join(USER_HOME, ".sokol", "plugins"),
            os.path.join(os.path.dirname(__file__), "plugins"),
            "plugins"  # Local plugins directory
        ]
        self.config_file = os.path.join(USER_HOME, ".sokol", "plugin_config.json")
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.command_handlers: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        
        self.logger = logging.getLogger("sokol.plugin_manager")
        
        # Ensure plugin directories exist
        self._ensure_plugin_dirs()
        
        # Load configuration
        self.config = self._load_config()
    
    def _ensure_plugin_dirs(self):
        """Ensure plugin directories exist"""
        for plugin_dir in self.plugin_dirs:
            os.makedirs(plugin_dir, exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load plugin configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load plugin config: {e}")
        
        return {
            "enabled_plugins": {},
            "plugin_settings": {},
            "auto_discover": True,
            "security_level": "medium"
        }
    
    def _save_config(self):
        """Save plugin configuration"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save plugin config: {e}")
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins in plugin directories"""
        discovered = []
        
        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                continue
            
            for item in os.listdir(plugin_dir):
                plugin_path = os.path.join(plugin_dir, item)
                
                # Check if it's a plugin directory
                if os.path.isdir(plugin_path):
                    metadata_file = os.path.join(plugin_path, "plugin.json")
                    if os.path.exists(metadata_file):
                        discovered.append(plugin_path)
                
                # Check if it's a single Python file plugin
                elif item.endswith('.py') and not item.startswith('_'):
                    discovered.append(plugin_path)
        
        return discovered
    
    def load_plugin_metadata(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Load plugin metadata from plugin.json or file"""
        try:
            if os.path.isdir(plugin_path):
                # Directory plugin
                metadata_file = os.path.join(plugin_path, "plugin.json")
                if not os.path.exists(metadata_file):
                    return None
                
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Set entry point if not specified
                if 'entry_point' not in data:
                    data['entry_point'] = f"{data['name']}.py"
                
                return PluginMetadata(**data)
            
            elif plugin_path.endswith('.py'):
                # Single file plugin
                with open(plugin_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract metadata from file header
                metadata = self._extract_metadata_from_file(plugin_path, content)
                return metadata
                
        except Exception as e:
            self.logger.error(f"Failed to load metadata from {plugin_path}: {e}")
        
        return None
    
    def _extract_metadata_from_file(self, file_path: str, content: str) -> Optional[PluginMetadata]:
        """Extract metadata from Python file header"""
        try:
            # Look for metadata in comments
            metadata_block = {}
            
            # Parse JSON metadata block
            if '"""' in content:
                start = content.find('"""')
                end = content.find('"""', start + 3)
                if start != -1 and end != -1:
                    metadata_text = content[start + 3:end].strip()
                    try:
                        metadata_block = json.loads(metadata_text)
                    except json.JSONDecodeError:
                        pass
            
            # Extract basic metadata from filename if no JSON block
            if not metadata_block:
                filename = os.path.basename(file_path)
                name = filename[:-3]  # Remove .py extension
                
                metadata_block = {
                    "name": name,
                    "version": "1.0.0",
                    "description": f"Plugin: {name}",
                    "author": "Unknown",
                    "category": "utility",
                    "tags": [],
                    "dependencies": [],
                    "min_sokol_version": "8.0",
                    "max_sokol_version": None,
                    "entry_point": filename,
                    "config_schema": None,
                    "permissions": []
                }
            
            return PluginMetadata(**metadata_block)
            
        except Exception as e:
            self.logger.error(f"Failed to extract metadata from {file_path}: {e}")
            return None
    
    def load_plugin(self, plugin_path: str) -> bool:
        """Load a single plugin"""
        with self._lock:
            try:
                # Load metadata
                metadata = self.load_plugin_metadata(plugin_path)
                if not metadata:
                    self.logger.error(f"No metadata found for {plugin_path}")
                    return False
                
                # Check compatibility
                if not self._check_compatibility(metadata):
                    self.logger.error(f"Plugin {metadata.name} is not compatible with current Sokol version")
                    return False
                
                # Check dependencies
                if not self._check_dependencies(metadata):
                    self.logger.error(f"Plugin {metadata.name} has unmet dependencies")
                    return False
                
                # Load the plugin module
                module, instance = self._load_plugin_module(plugin_path, metadata)
                
                if module and instance:
                    # Initialize plugin
                    config = self.config.get("plugin_settings", {}).get(metadata.name, {})
                    
                    if hasattr(instance, 'initialize') and not instance.initialize(config):
                        self.logger.error(f"Failed to initialize plugin {metadata.name}")
                        return False
                    
                    # Register plugin
                    plugin_info = PluginInfo(
                        metadata=metadata,
                        module=module,
                        instance=instance,
                        loaded=True,
                        enabled=self.config.get("enabled_plugins", {}).get(metadata.name, True),
                        load_time=datetime.now()
                    )
                    
                    self.plugins[metadata.name] = plugin_info
                    
                    # Register commands and event handlers
                    self._register_plugin_handlers(plugin_info)
                    
                    self.logger.info(f"Successfully loaded plugin: {metadata.name} v{metadata.version}")
                    return True
                else:
                    self.logger.error(f"Failed to load plugin module: {metadata.name}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Failed to load plugin {plugin_path}: {e}")
                return False
    
    def _check_compatibility(self, metadata: PluginMetadata) -> bool:
        """Check plugin compatibility with current Sokol version"""
        current_version = VERSION
        
        # Check minimum version
        if metadata.min_sokol_version:
            if not self._version_compatible(current_version, metadata.min_sokol_version, 'min'):
                return False
        
        # Check maximum version
        if metadata.max_sokol_version:
            if not self._version_compatible(current_version, metadata.max_sokol_version, 'max'):
                return False
        
        return True
    
    def _version_compatible(self, current: str, required: str, check_type: str) -> bool:
        """Check version compatibility"""
        try:
            current_parts = [int(x) for x in current.split('.')]
            required_parts = [int(x) for x in required.split('.')]
            
            # Pad with zeros
            max_len = max(len(current_parts), len(required_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            required_parts.extend([0] * (max_len - len(required_parts)))
            
            if check_type == 'min':
                return current_parts >= required_parts
            elif check_type == 'max':
                return current_parts <= required_parts
            
        except Exception:
            pass
        
        return True
    
    def _check_dependencies(self, metadata: PluginMetadata) -> bool:
        """Check plugin dependencies"""
        for dep in metadata.dependencies:
            # Check if dependency is another plugin
            if dep in self.plugins:
                if not self.plugins[dep].loaded:
                    return False
            # Check if dependency is a Python package
            else:
                try:
                    importlib.import_module(dep)
                except ImportError:
                    return False
        
        return True
    
    def _load_plugin_module(self, plugin_path: str, metadata: PluginMetadata) -> tuple[Optional[Any], Optional[Any]]:
        """Load plugin module and create instance"""
        try:
            if os.path.isdir(plugin_path):
                # Directory plugin
                module_name = metadata.name
                entry_file = os.path.join(plugin_path, metadata.entry_point)
                
                # Add plugin directory to path
                if plugin_path not in os.sys.path:
                    os.sys.path.insert(0, plugin_path)
                
                # Import module
                spec = importlib.util.spec_from_file_location(module_name, entry_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
            else:
                # Single file plugin
                module_name = os.path.basename(plugin_path)[:-3]
                spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            
            # Find plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginInterface) and 
                    obj != PluginInterface):
                    plugin_class = obj
                    break
            
            if plugin_class:
                instance = plugin_class()
                return module, instance
            else:
                # If no class found, use module as plugin
                return module, module
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin module: {e}")
            return None, None
    
    def _register_plugin_handlers(self, plugin_info: PluginInfo):
        """Register plugin commands and event handlers"""
        instance = plugin_info.instance
        
        # Register commands
        if hasattr(instance, 'get_commands'):
            try:
                commands = instance.get_commands()
                for command in commands:
                    cmd_name = command.get('name')
                    if cmd_name:
                        self.command_handlers[cmd_name] = (instance, command)
            except Exception as e:
                self.logger.error(f"Failed to register commands for {plugin_info.metadata.name}: {e}")
        
        # Register event handlers
        if hasattr(instance, 'on_sokol_event'):
            try:
                # Register for all events
                for event_type in ['system_start', 'system_shutdown', 'command_executed', 'error_occurred']:
                    if event_type not in self.event_handlers:
                        self.event_handlers[event_type] = []
                    self.event_handlers[event_type].append(instance.on_sokol_event)
            except Exception as e:
                self.logger.error(f"Failed to register event handlers for {plugin_info.metadata.name}: {e}")
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        with self._lock:
            if plugin_name not in self.plugins:
                return False
            
            plugin_info = self.plugins[plugin_name]
            
            try:
                # Shutdown plugin
                if plugin_info.instance and hasattr(plugin_info.instance, 'shutdown'):
                    plugin_info.instance.shutdown()
                
                # Unregister handlers
                self._unregister_plugin_handlers(plugin_info)
                
                # Remove from plugins
                del self.plugins[plugin_name]
                
                self.logger.info(f"Successfully unloaded plugin: {plugin_name}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to unload plugin {plugin_name}: {e}")
                return False
    
    def _unregister_plugin_handlers(self, plugin_info: PluginInfo):
        """Unregister plugin handlers"""
        # Remove command handlers
        commands_to_remove = []
        for cmd_name, (instance, _) in self.command_handlers.items():
            if instance == plugin_info.instance:
                commands_to_remove.append(cmd_name)
        
        for cmd_name in commands_to_remove:
            del self.command_handlers[cmd_name]
        
        # Remove event handlers
        for event_type, handlers in self.event_handlers.items():
            self.event_handlers[event_type] = [
                h for h in handlers if h != plugin_info.instance.on_sokol_event
            ]
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].enabled = True
            self.config["enabled_plugins"][plugin_name] = True
            self._save_config()
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin"""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].enabled = False
            self.config["enabled_plugins"][plugin_name] = False
            self._save_config()
            return True
        return False
    
    def execute_plugin_command(self, command: str, params: Dict[str, Any]) -> Any:
        """Execute plugin command"""
        if command in self.command_handlers:
            instance, command_info = self.command_handlers[command]
            
            try:
                if hasattr(instance, 'handle_command'):
                    return instance.handle_command(command, params)
                else:
                    # Call the command function directly
                    cmd_function = command_info.get('function')
                    if cmd_function and hasattr(instance, cmd_function):
                        return getattr(instance, cmd_function)(**params)
            except Exception as e:
                self.logger.error(f"Failed to execute plugin command {command}: {e}")
                return {"error": str(e)}
        
        return None
    
    def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event to all plugins"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_type, data)
                except Exception as e:
                    self.logger.error(f"Plugin event handler error: {e}")
    
    def load_all_plugins(self) -> int:
        """Load all discovered plugins"""
        if not self.config.get("auto_discover", True):
            return 0
        
        discovered = self.discover_plugins()
        loaded_count = 0
        
        for plugin_path in discovered:
            if self.load_plugin(plugin_path):
                loaded_count += 1
        
        self.logger.info(f"Loaded {loaded_count} out of {len(discovered)} discovered plugins")
        return loaded_count
    
    def get_plugin_list(self) -> List[Dict[str, Any]]:
        """Get list of all plugins with their status"""
        plugins_list = []
        
        for plugin_name, plugin_info in self.plugins.items():
            plugin_data = {
                "name": plugin_name,
                "version": plugin_info.metadata.version,
                "description": plugin_info.metadata.description,
                "author": plugin_info.metadata.author,
                "category": plugin_info.metadata.category,
                "loaded": plugin_info.loaded,
                "enabled": plugin_info.enabled,
                "load_time": plugin_info.load_time.isoformat() if plugin_info.load_time else None,
                "error": plugin_info.error
            }
            plugins_list.append(plugin_data)
        
        return plugins_list
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a plugin"""
        if plugin_name not in self.plugins:
            return None
        
        plugin_info = self.plugins[plugin_name]
        
        info = {
            "metadata": asdict(plugin_info.metadata),
            "loaded": plugin_info.loaded,
            "enabled": plugin_info.enabled,
            "load_time": plugin_info.load_time.isoformat() if plugin_info.load_time else None,
            "error": plugin_info.error,
            "stats": plugin_info.stats
        }
        
        # Get runtime info from plugin instance
        if plugin_info.instance and hasattr(plugin_info.instance, 'get_info'):
            try:
                runtime_info = plugin_info.instance.get_info()
                info["runtime"] = runtime_info
            except Exception as e:
                info["runtime_error"] = str(e)
        
        return info
    
    def shutdown_all_plugins(self):
        """Shutdown all plugins"""
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)
        
        self.logger.info("All plugins shutdown")


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get global plugin manager instance"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def initialize_plugins() -> int:
    """Initialize plugin system and load all plugins"""
    manager = get_plugin_manager()
    return manager.load_all_plugins()


if __name__ == "__main__":
    # Test plugin system
    print("Plugin System Test")
    print("==================")
    
    manager = PluginManager()
    
    # Discover plugins
    discovered = manager.discover_plugins()
    print(f"Discovered {len(discovered)} plugins")
    
    # Load plugins
    loaded = manager.load_all_plugins()
    print(f"Loaded {loaded} plugins")
    
    # List plugins
    plugins = manager.get_plugin_list()
    print("\nLoaded plugins:")
    for plugin in plugins:
        status = "enabled" if plugin["enabled"] else "disabled"
        print(f"  - {plugin['name']} v{plugin['version']} ({status})")
    
    print("\nPlugin system test completed!")
