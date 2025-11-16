"""
YAML configuration parsing for task flows.
"""

import yaml
import logging
import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StepConfig:
    """Configuration for a single step."""
    id: str
    name: str
    tool: str
    parameters: Dict[str, Any]
    dependencies: List[str]
    retry_count: int = 3
    retry_delay: float = 1.0
    fallback_tools: Optional[List[str]] = None
    condition: Optional[str] = None  # Conditional execution


@dataclass
class TaskFlowConfig:
    """Configuration for the entire task flow."""
    name: str
    description: str
    steps: List[StepConfig]
    parallel_groups: Optional[List[List[str]]] = None  # Groups of steps that can run in parallel


class ConfigParser:
    """Parses YAML configuration files for task flows."""

    @staticmethod
    def parse_config(config_path: str) -> TaskFlowConfig:
        """
        Parse YAML configuration file.

        Args:
            config_path: Path to YAML config file

        Returns:
            Parsed TaskFlowConfig
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            # Substitute environment variables
            config_data = ConfigParser._substitute_env_vars(config_data)

            return ConfigParser._parse_task_flow(config_data)

        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")

    @staticmethod
    def _parse_task_flow(data: Dict[str, Any]) -> TaskFlowConfig:
        """Parse task flow from dictionary."""
        name = data.get('name', 'Unnamed Task')
        description = data.get('description', '')
        steps_data = data.get('steps', [])
        parallel_groups = data.get('parallel_groups')

        steps = []
        for step_data in steps_data:
            step = ConfigParser._parse_step(step_data)
            steps.append(step)

        return TaskFlowConfig(
            name=name,
            description=description,
            steps=steps,
            parallel_groups=parallel_groups
        )

    @staticmethod
    def _parse_step(data: Dict[str, Any]) -> StepConfig:
        """Parse individual step from dictionary."""
        step_id = data.get('id')
        if not step_id:
            raise ValueError("Step must have an 'id'")

        return StepConfig(
            id=step_id,
            name=data.get('name', step_id),
            tool=data.get('tool', ''),
            parameters=data.get('parameters', {}),
            dependencies=data.get('dependencies', []),
            retry_count=data.get('retry_count', 3),
            retry_delay=data.get('retry_delay', 1.0),
            fallback_tools=data.get('fallback_tools'),
            condition=data.get('condition')
        )

    @staticmethod
    def validate_config(config: TaskFlowConfig) -> List[str]:
        """
        Validate task flow configuration.

        Args:
            config: TaskFlowConfig to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for duplicate step IDs
        step_ids = [step.id for step in config.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append("Duplicate step IDs found")

        # Check dependencies exist
        all_step_ids = set(step_ids)
        for step in config.steps:
            for dep in step.dependencies:
                if dep not in all_step_ids:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep}'")

        # Check parallel groups
        if config.parallel_groups:
            for group in config.parallel_groups:
                for step_id in group:
                    if step_id not in all_step_ids:
                        errors.append(f"Parallel group contains non-existent step '{step_id}'")

        # Check tools are specified
        for step in config.steps:
            if not step.tool:
                errors.append(f"Step '{step.id}' does not specify a tool")

        return errors

    @staticmethod
    def _substitute_env_vars(data: Any) -> Any:
        """
        Recursively substitute environment variables in configuration data.

        Supports syntax: ${VAR_NAME:default_value}
        """
        if isinstance(data, dict):
            return {key: ConfigParser._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [ConfigParser._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            return ConfigParser._substitute_env_var_in_string(data)
        else:
            return data

    @staticmethod
    def _substitute_env_var_in_string(text: str) -> str:
        """Substitute environment variables in a string."""
        # Pattern matches ${VAR:default} or ${VAR}
        pattern = r'\$\{([^:}]+)(?::([^}]*))?\}'

        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""

            # Get environment variable
            env_value = os.getenv(var_name)
            if env_value is not None:
                return env_value
            elif default_value:
                return default_value
            else:
                # Variable not found and no default - leave as is but log warning
                logger.warning(f"Environment variable '{var_name}' not found and no default provided")
                return match.group(0)  # Return original string

        return re.sub(pattern, replace_var, text)
