"""
Task scheduler with serial/parallel execution and exception handling.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum

from .config import TaskFlowConfig, StepConfig
from .registry import ToolRegistry, BaseTool
from .context import ContextManager

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Execution status of a step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a step execution."""
    step_id: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    tool_used: Optional[str] = None


@dataclass
class TaskExecutionResult:
    """Result of entire task execution."""
    task_name: str
    success: bool
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    total_execution_time: float = 0.0
    error_summary: List[str] = field(default_factory=list)


class TaskScheduler:
    """Main task scheduler."""

    def __init__(self,
                 tool_registry: ToolRegistry,
                 context_manager: ContextManager,
                 max_workers: int = 4):
        """
        Initialize task scheduler.

        Args:
            tool_registry: Tool registry instance
            context_manager: Context manager instance
            max_workers: Maximum number of worker threads for parallel execution
        """
        self.tool_registry = tool_registry
        self.context_manager = context_manager
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def execute_task(self, config: TaskFlowConfig) -> TaskExecutionResult:
        """
        Execute a task flow.

        Args:
            config: Task flow configuration

        Returns:
            Task execution result
        """
        start_time = time.time()
        logger.info(f"Starting task execution: {config.name}")

        # Validate configuration
        errors = self._validate_config(config)
        if errors:
            error_msg = f"Configuration validation failed: {errors}"
            logger.error(error_msg)
            return TaskExecutionResult(
                task_name=config.name,
                success=False,
                error_summary=errors
            )

        # Initialize step results
        step_results = {step.id: StepResult(step.id, StepStatus.PENDING)
                       for step in config.steps}

        try:
            # Execute steps
            await self._execute_steps(config, step_results)

            # Check overall success
            success = all(result.status == StepStatus.COMPLETED
                         for result in step_results.values()
                         if result.status != StepStatus.SKIPPED)

            total_time = time.time() - start_time

            result = TaskExecutionResult(
                task_name=config.name,
                success=success,
                step_results=step_results,
                total_execution_time=total_time
            )

            logger.info(f"Task execution completed: {config.name}, success={success}")
            return result

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return TaskExecutionResult(
                task_name=config.name,
                success=False,
                step_results=step_results,
                total_execution_time=time.time() - start_time,
                error_summary=[str(e)]
            )

    async def _execute_steps(self,
                           config: TaskFlowConfig,
                           step_results: Dict[str, StepResult]) -> None:
        """Execute steps according to dependencies and parallel groups."""
        # Create dependency graph
        dependency_graph = self._build_dependency_graph(config.steps)

        # Execute steps in topological order
        while True:
            # Find ready steps (all dependencies completed)
            ready_steps = []
            for step in config.steps:
                if step_results[step.id].status == StepStatus.PENDING:
                    deps_completed = all(
                        step_results[dep].status == StepStatus.COMPLETED
                        for dep in step.dependencies
                    )
                    if deps_completed:
                        # Check condition if present
                        if self._check_condition(step, step_results):
                            ready_steps.append(step)
                        else:
                            step_results[step.id].status = StepStatus.SKIPPED
                            logger.info(f"Step {step.id} skipped due to condition")

            if not ready_steps:
                break

            # Group ready steps by parallel execution
            parallel_groups = self._group_parallel_steps(ready_steps, config.parallel_groups)

            # Execute parallel groups
            tasks = []
            for group in parallel_groups:
                if len(group) == 1:
                    # Single step
                    task = asyncio.create_task(
                        self._execute_step(group[0], step_results)
                    )
                    tasks.append(task)
                else:
                    # Parallel group
                    group_task = asyncio.create_task(
                        self._execute_parallel_group(group, step_results)
                    )
                    tasks.append(group_task)

            # Wait for all groups to complete
            await asyncio.gather(*tasks)

    async def _execute_step(self,
                           step: StepConfig,
                           step_results: Dict[str, StepResult]) -> None:
        """Execute a single step."""
        step_results[step.id].status = StepStatus.RUNNING
        start_time = time.time()

        try:
            # Get tool
            tool = self.tool_registry.get_tool(step.tool)
            if not tool:
                raise ValueError(f"Tool '{step.tool}' not found")

            # Prepare input from context and parameters
            input_data = self._prepare_step_input(step, step_results)

            # Execute with retry logic
            result = await self._execute_with_retry(tool, input_data, step)

            # Store result
            execution_time = time.time() - start_time
            step_results[step.id] = StepResult(
                step_id=step.id,
                status=StepStatus.COMPLETED,
                output=result,
                execution_time=execution_time,
                tool_used=step.tool
            )

            # Store in context
            self.context_manager.set(f"step_{step.id}_output", result, step.id)

            logger.info(f"Step {step.id} completed successfully")

        except Exception as e:
            execution_time = time.time() - start_time
            step_results[step.id] = StepResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(e),
                execution_time=execution_time
            )
            logger.error(f"Step {step.id} failed: {e}")

    async def _execute_parallel_group(self,
                                    group: List[StepConfig],
                                    step_results: Dict[str, StepResult]) -> None:
        """Execute a group of steps in parallel."""
        tasks = [self._execute_step(step, step_results) for step in group]
        await asyncio.gather(*tasks)

    async def _execute_with_retry(self,
                                tool: BaseTool,
                                input_data: Any,
                                step: StepConfig) -> Any:
        """Execute tool with retry logic and fallback."""
        last_error = None

        # Try primary tool with retries
        for attempt in range(step.retry_count + 1):
            try:
                context = self.context_manager.get_all()
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor, tool.run, input_data, context
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < step.retry_count:
                    logger.warning(f"Step {step.id} attempt {attempt + 1} failed, retrying: {e}")
                    await asyncio.sleep(step.retry_delay)
                else:
                    logger.error(f"Step {step.id} all retries failed: {e}")

        # Try fallback tools
        if step.fallback_tools:
            for fallback_tool_name in step.fallback_tools:
                try:
                    fallback_tool = self.tool_registry.get_tool(fallback_tool_name)
                    if fallback_tool:
                        logger.info(f"Trying fallback tool {fallback_tool_name} for step {step.id}")
                        context = self.context_manager.get_all()
                        result = await asyncio.get_event_loop().run_in_executor(
                            self.executor, fallback_tool.run, input_data, context
                        )
                        return result
                except Exception as e:
                    logger.warning(f"Fallback tool {fallback_tool_name} failed: {e}")

        # All attempts failed
        raise last_error or Exception("All execution attempts failed")

    def _prepare_step_input(self,
                           step: StepConfig,
                           step_results: Dict[str, StepResult]) -> Any:
        """Prepare input data for step execution."""
        # Merge parameters with dependency outputs
        input_data = step.parameters.copy()

        for dep in step.dependencies:
            if dep in step_results and step_results[dep].output is not None:
                input_data[f"dep_{dep}_output"] = step_results[dep].output

        return input_data

    def _check_condition(self, step: StepConfig, step_results: Dict[str, StepResult]) -> bool:
        """Check if step should be executed based on condition."""
        if not step.condition:
            return True

        # Simple condition evaluation (can be extended)
        try:
            # For now, support simple dependency checks
            if step.condition.startswith("dep_"):
                dep_id = step.condition[4:]  # Remove "dep_" prefix
                return step_results.get(dep_id, StepResult("", StepStatus.PENDING)).status == StepStatus.COMPLETED
            return True
        except:
            return True

    def _build_dependency_graph(self, steps: List[StepConfig]) -> Dict[str, List[str]]:
        """Build dependency graph."""
        graph = {}
        for step in steps:
            graph[step.id] = step.dependencies
        return graph

    def _group_parallel_steps(self,
                            ready_steps: List[StepConfig],
                            parallel_groups: Optional[List[List[str]]]) -> List[List[StepConfig]]:
        """Group steps for parallel execution."""
        if not parallel_groups:
            # No parallel groups defined, execute sequentially
            return [[step] for step in ready_steps]

        # Group by defined parallel groups
        groups = []
        used_steps = set()

        # First, add defined parallel groups
        for group_ids in parallel_groups:
            group = [s for s in ready_steps if s.id in group_ids and s.id not in used_steps]
            if group:
                groups.append(group)
                used_steps.update(s.id for s in group)

        # Add remaining steps as individual groups
        for step in ready_steps:
            if step.id not in used_steps:
                groups.append([step])

        return groups

    def _validate_config(self, config: TaskFlowConfig) -> List[str]:
        """Validate task configuration."""
        errors = []

        # Check for cycles in dependencies (simplified check)
        # This is a basic check - a full topological sort would be better
        step_ids = {step.id for step in config.steps}
        for step in config.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    errors.append(f"Step '{step.id}' depends on unknown step '{dep}'")

        return errors
