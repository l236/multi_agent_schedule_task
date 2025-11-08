"""
Django Integration Example for Multi-Agent Schedule Task Framework

This example shows how to integrate the task scheduling framework into a Django project.
"""

import os
import asyncio
from pathlib import Path
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

# Import the framework
from multi_agent_schedule_task import TaskScheduler, ToolRegistry, ContextManager
from multi_agent_schedule_task.config import ConfigParser
from multi_agent_schedule_task.tools.doc_parser import DocParseTool
from multi_agent_schedule_task.tools.retrieval import RetrievalTool
from multi_agent_schedule_task.tools.generation import GenerationTool


class DjangoTaskService:
    """Django service wrapper for task scheduling."""

    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.context_manager = ContextManager(
            expiration_time=getattr(settings, 'TASK_CONTEXT_EXPIRATION', 3600)
        )
        self.scheduler = TaskScheduler(
            self.tool_registry,
            self.context_manager,
            max_workers=getattr(settings, 'TASK_MAX_WORKERS', 4)
        )

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register available tools."""
        self.tool_registry.register_tool("doc_parser", DocParseTool)
        self.tool_registry.register_tool("retrieval", RetrievalTool)
        self.tool_registry.register_tool("generation", GenerationTool)

    async def execute_task_async(self, config_path_or_dict):
        """
        Execute a task asynchronously.

        Args:
            config_path_or_dict: Path to YAML config file or config dict

        Returns:
            Task execution result
        """
        if isinstance(config_path_or_dict, str):
            config = ConfigParser.parse_config(config_path_or_dict)
        else:
            config = ConfigParser._parse_task_flow(config_path_or_dict)

        return await self.scheduler.execute_task(config)

    def execute_task_sync(self, config_path_or_dict):
        """
        Execute a task synchronously.

        Args:
            config_path_or_dict: Path to YAML config file or config dict

        Returns:
            Task execution result
        """
        # Create event loop if one doesn't exist
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If loop is already running, we need to use run_until_complete
            # This is common in Django's synchronous context
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.execute_task_async(config_path_or_dict))
        else:
            return loop.run_until_complete(self.execute_task_async(config_path_or_dict))


# Global service instance
task_service = DjangoTaskService()


@csrf_exempt
@require_http_methods(["POST"])
def execute_task_view(request):
    """
    Django view for executing tasks.

    Expected JSON payload:
    {
        "config": {
            "name": "Task Name",
            "description": "Task Description",
            "steps": [...],
            "parallel_groups": [...]
        },
        "async": false
    }
    """
    try:
        data = json.loads(request.body)
        config = data.get('config', {})
        async_execution = data.get('async', False)

        if not config:
            return JsonResponse({'error': 'Config is required'}, status=400)

        if async_execution:
            # For async execution, you'd typically use Django's background task system
            # like Celery, Django-Q, or similar
            return JsonResponse({
                'message': 'Async execution not implemented in this example',
                'status': 'not_implemented'
            }, status=501)
        else:
            # Synchronous execution
            result = task_service.execute_task_sync(config)

            return JsonResponse({
                'task_id': f"django_sync_{os.getpid()}",
                'success': result.success,
                'execution_time': result.total_execution_time,
                'step_results': {
                    step_id: {
                        'status': step_result.status.value,
                        'execution_time': step_result.execution_time,
                        'error': step_result.error,
                        'tool_used': step_result.tool_used,
                        'output': str(step_result.output)[:500] if step_result.output else None
                    }
                    for step_id, step_result in result.step_results.items()
                },
                'error_summary': result.error_summary
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def list_tools_view(request):
    """List available tools."""
    tools = task_service.tool_registry.list_tools()
    return JsonResponse({
        'tools': tools,
        'count': len(tools)
    })


@csrf_exempt
@require_http_methods(["POST"])
def upload_file_view(request):
    """
    Upload a file for processing.

    Usage: POST with multipart/form-data containing 'file' field.
    """
    try:
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({'error': 'No file provided'}, status=400)

        # Save file using Django's storage system
        file_name = default_storage.save(
            f"task_files/{uploaded_file.name}",
            uploaded_file
        )
        file_path = default_storage.path(file_name)

        return JsonResponse({
            'file_id': file_name,
            'filename': uploaded_file.name,
            'path': file_path,
            'size': uploaded_file.size,
            'url': default_storage.url(file_name)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# URL configuration example (add to urls.py):
"""
from django.urls import path
from . import views

urlpatterns = [
    path('tasks/execute/', views.execute_task_view, name='execute_task'),
    path('tools/', views.list_tools_view, name='list_tools'),
    path('files/upload/', views.upload_file_view, name='upload_file'),
]
"""

# Settings configuration example (add to settings.py):
"""
# Task scheduling settings
TASK_CONTEXT_EXPIRATION = 3600  # 1 hour
TASK_MAX_WORKERS = 4

# File storage for task files
import os
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
"""

# Usage example in Django views/models:
"""
from .django_example import task_service

def process_contract(request, contract_id):
    # Example task configuration
    config = {
        'name': f'Process Contract {contract_id}',
        'steps': [
            {
                'id': 'parse_contract',
                'tool': 'doc_parser',
                'parameters': {'file_path': f'/path/to/contract_{contract_id}.pdf'},
                'retry_count': 2
            },
            {
                'id': 'generate_summary',
                'tool': 'generation',
                'parameters': {
                    'type': 'summary',
                    'data': {'key_points': ['Parse contract', 'Extract key terms']}
                },
                'dependencies': ['parse_contract']
            }
        ]
    }

    result = task_service.execute_task_sync(config)
    return JsonResponse({'result': result.success})
"""
