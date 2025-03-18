from typing import Dict, Any, List

from .base_collector import BaseCollector
from .bool_collector import BoolCollector
from .class_inherits_collector import ClassInheritsCollector
from .class_name_regex_collector import ClassNameRegexCollector
from .decorator_usage_collector import DecoratorUsageCollector
from .directory_collector import DirectoryCollector
from .file_regex_collector import FileRegexCollector
from .function_name_regex_collector import FunctionNameRegexCollector


class CollectorFactory:
    @staticmethod
    def create(config: Dict[str, Any], paths: List[str], exclude_files: List[str]) -> BaseCollector:
        collector_type = config.get("type")
        if collector_type == "file_regex":
            return FileRegexCollector(config, paths, exclude_files)
        elif collector_type == "class_inherits":
            return ClassInheritsCollector(config)
        elif collector_type == "class_name_regex":
            return ClassNameRegexCollector(config, paths, exclude_files)
        elif collector_type == "function_name_regex":
            return FunctionNameRegexCollector(config)
        elif collector_type == "directory":
            return DirectoryCollector(config, paths, exclude_files)
        elif collector_type == "decorator_usage":
            return DecoratorUsageCollector(config)
        elif collector_type == "bool":
            return BoolCollector(config, paths, exclude_files)
        elif collector_type == "custom":
            class_path = config.get("class")
            if not class_path:
                raise ValueError("Custom collector requires 'class' field")

            try:
                module_name, class_name = class_path.rsplit(".", 1)
            except ValueError:
                raise ValueError(f"Invalid class path format: {class_path}")

            try:
                module = __import__(module_name, fromlist=[class_name])
            except ImportError as e:
                raise ValueError(f"Failed to import module '{module_name}': {str(e)}")

            cls = getattr(module, class_name, None)
            if not cls:
                raise ValueError(f"Class '{class_name}' not found in {module_name}")

            plugin_config = {
                "params": config.get("params", {}),
                "paths": paths,
                "exclude_files": exclude_files,
            }

            try:
                return cls(plugin_config)
            except TypeError as e:
                raise ValueError(f"Error initializing {class_path}: {str(e)}")
        else:
            raise ValueError(f"Unknown collector type: {collector_type}")
