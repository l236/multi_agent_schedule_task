#!/usr/bin/env python3
"""
Command Line Interface for Multi-Agent Schedule Task Framework

Usage:
    python main.py [config_file] [options]

Options:
    --log-level LEVEL    Set logging level (DEBUG, INFO, WARNING, ERROR)
    --max-workers N      Maximum number of worker threads
    --context-expiration N  Context expiration time in seconds
    --output-format FORMAT  Output format (json, text)
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from multi_agent_schedule_task import TaskScheduler, ToolRegistry, ContextManager
from multi_agent_schedule_task.config import ConfigParser
from multi_agent_schedule_task.tools.doc_parser import DocParseTool
from multi_agent_schedule_task.tools.retrieval import RetrievalTool
from multi_agent_schedule_task.tools.generation import GenerationTool


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('task_execution.log')
        ]
    )


def create_scheduler(max_workers: int = 4, context_expiration: int = 3600) -> TaskScheduler:
    """Create and configure task scheduler."""
    tool_registry = ToolRegistry()
    context_manager = ContextManager(expiration_time=context_expiration)
    scheduler = TaskScheduler(tool_registry, context_manager, max_workers=max_workers)

    # Register default tools
    tool_registry.register_tool("doc_parser", DocParseTool)
    tool_registry.register_tool("retrieval", RetrievalTool)
    tool_registry.register_tool("generation", GenerationTool)

    return scheduler


async def execute_task(config_path: str, scheduler: TaskScheduler, output_format: str = "text"):
    """Execute task and display results."""
    logger = logging.getLogger(__name__)

    try:
        # Load and validate configuration
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        config = ConfigParser.parse_config(config_path)
        validation_errors = ConfigParser.validate_config(config)

        if validation_errors:
            logger.error(f"Configuration validation failed: {validation_errors}")
            return False

        logger.info(f"Loaded task configuration: {config.name}")
        logger.info(f"Steps: {len(config.steps)}")

        # Execute task
        result = await scheduler.execute_task(config)

        # Output results
        if output_format == "json":
            output_result_json(result)
        else:
            output_result_text(result)

        return result.success

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        if output_format == "json":
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error: {e}")
        return False


def output_result_json(result):
    """Output results in JSON format."""
    output = {
        "task_name": result.task_name,
        "success": result.success,
        "execution_time": result.total_execution_time,
        "step_count": len(result.step_results),
        "steps": {},
        "error_summary": result.error_summary
    }

    for step_id, step_result in result.step_results.items():
        output["steps"][step_id] = {
            "status": step_result.status.value,
            "execution_time": step_result.execution_time,
            "error": step_result.error,
            "tool_used": step_result.tool_used,
            "output": step_result.output
        }

    print(json.dumps(output, indent=2, default=str))


def output_result_text(result):
    """Output results in human-readable text format."""
    print("\n" + "="*60)
    print(f"TASK EXECUTION RESULTS: {result.task_name}")
    print("="*60)
    print(f"Success: {result.success}")
    print(".2f")
    print(f"Steps executed: {len(result.step_results)}")

    print("\nSTEP DETAILS:")
    print("-" * 40)
    for step_id, step_result in result.step_results.items():
        status_icon = "✓" if step_result.status.name == "COMPLETED" else "✗" if step_result.status.name == "FAILED" else "○"
        print(f"{status_icon} {step_id}: {step_result.status.name}")
        print(".2f")
        if step_result.error:
            print(f"    Error: {step_result.error}")
        if step_result.tool_used:
            print(f"    Tool: {step_result.tool_used}")
        print()

    # Show final outputs
    if result.success:
        print("FINAL OUTPUTS:")
        print("-" * 40)
        for step_id, step_result in result.step_results.items():
            if step_result.output and step_result.status.name == "COMPLETED":
                print(f"\n{step_id.upper()} OUTPUT:")
                if isinstance(step_result.output, dict):
                    for key, value in step_result.output.items():
                        print(f"  {key}: {value}")
                else:
                    # Truncate long outputs for display
                    output_str = str(step_result.output)
                    if len(output_str) > 500:
                        print(f"  {output_str[:500]}...")
                    else:
                        print(f"  {output_str}")

    # Error summary
    if result.error_summary:
        print("\nERROR SUMMARY:")
        print("-" * 40)
        for error in result.error_summary:
            print(f"• {error}")

    print("\n" + "="*60)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Schedule Task Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py example_config.yaml
  python main.py config.yaml --log-level DEBUG --max-workers 8
  python main.py config.yaml --output-format json
        """
    )

    parser.add_argument(
        "config_file",
        help="Path to YAML configuration file"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of worker threads (default: 4)"
    )

    parser.add_argument(
        "--context-expiration",
        type=int,
        default=3600,
        help="Context expiration time in seconds (default: 3600)"
    )

    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Create scheduler
    scheduler = create_scheduler(args.max_workers, args.context_expiration)

    # Execute task
    success = asyncio.run(execute_task(args.config_file, scheduler, args.output_format))

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
