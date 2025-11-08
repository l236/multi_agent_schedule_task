"""
Tool registration and management system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @abstractmethod
    def run(self, input_data: Any, context: Dict[str, Any]) -> Any:
        """
        Execute the tool with given input and context.

        Args:
            input_data: Input data for the tool
            context: Shared context containing intermediate results

        Returns:
            Tool execution result
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, name: str, tool_class: type) -> None:
        """
        Register a tool class.

        Args:
            name: Tool name
            tool_class: Tool class (must inherit from BaseTool)
        """
        if not issubclass(tool_class, BaseTool):
            raise ValueError(f"Tool class {tool_class} must inherit from BaseTool")

        tool_instance = tool_class()
        self._tools[name] = tool_instance
        logger.info(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a registered tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """
        List all registered tools with their descriptions.

        Returns:
            Dict of tool names to descriptions
        """
        return {name: tool.description for name, tool in self._tools.items()}


# Global tool registry instance
tool_registry = ToolRegistry()
