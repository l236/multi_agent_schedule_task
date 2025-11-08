#!/usr/bin/env python3
"""
FastAPI HTTP Service for Multi-Agent Schedule Task Framework

Provides REST API endpoints for task scheduling functionality.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

from multi_agent_schedule_task import TaskScheduler, ToolRegistry, ContextManager
from multi_agent_schedule_task.config import ConfigParser
from multi_agent_schedule_task.tools.doc_parser import DocParseTool
from multi_agent_schedule_task.tools.retrieval import RetrievalTool
from multi_agent_schedule_task.tools.generation import GenerationTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Agent Schedule Task API",
    description="REST API for automated task scheduling and execution",
    version="1.0.0"
)

# Global instances
tool_registry = ToolRegistry()
context_manager = ContextManager(expiration_time=int(os.getenv("CONTEXT_EXPIRATION", "3600")))
scheduler = TaskScheduler(tool_registry, context_manager, max_workers=int(os.getenv("MAX_WORKERS", "4")))

# Task storage (in production, use a proper database)
task_results = {}


class TaskConfig(BaseModel):
    """Task configuration model."""
    name: str = Field(..., description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    steps: List[Dict[str, Any]] = Field(..., description="Task steps")
    parallel_groups: Optional[List[List[str]]] = Field(None, description="Parallel execution groups")


class TaskExecutionRequest(BaseModel):
    """Task execution request model."""
    config: TaskConfig
    async_execution: bool = Field(False, description="Execute asynchronously")


class TaskStatus(BaseModel):
    """Task execution status."""
    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


@app.on_event("startup")
async def startup_event():
    """Initialize tools on startup."""
    try:
        # Register default tools
        tool_registry.register_tool("doc_parser", DocParseTool)
        tool_registry.register_tool("retrieval", RetrievalTool)
        tool_registry.register_tool("generation", GenerationTool)

        logger.info("Registered default tools:")
        for name, desc in tool_registry.list_tools().items():
            logger.info(f"  - {name}: {desc}")

    except Exception as e:
        logger.error(f"Failed to initialize tools: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Multi-Agent Schedule Task API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now()}


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {
        "tools": tool_registry.list_tools(),
        "count": len(tool_registry.list_tools())
    }


@app.post("/tasks/execute")
async def execute_task(request: TaskExecutionRequest, background_tasks: BackgroundTasks):
    """
    Execute a task synchronously or asynchronously.

    For async execution, returns a task ID immediately.
    For sync execution, waits for completion and returns results.
    """
    try:
        # Convert Pydantic model to dict for ConfigParser
        config_dict = request.config.dict()
        config = ConfigParser._parse_task_flow(config_dict)

        # Validate configuration
        validation_errors = ConfigParser.validate_config(config)
        if validation_errors:
            raise HTTPException(status_code=400, detail=f"Configuration validation failed: {validation_errors}")

        if request.async_execution:
            # Async execution
            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(config_dict))}"

            # Store initial status
            task_results[task_id] = TaskStatus(
                task_id=task_id,
                status="running",
                created_at=datetime.now()
            )

            # Execute in background
            background_tasks.add_task(execute_task_background, task_id, config)

            return {
                "task_id": task_id,
                "status": "accepted",
                "message": "Task execution started asynchronously"
            }
        else:
            # Sync execution
            result = await scheduler.execute_task(config)

            return {
                "task_id": f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "status": "completed",
                "success": result.success,
                "execution_time": result.total_execution_time,
                "step_results": {
                    step_id: {
                        "status": step_result.status.value,
                        "execution_time": step_result.execution_time,
                        "error": step_result.error,
                        "tool_used": step_result.tool_used,
                        "output": step_result.output
                    }
                    for step_id, step_result in result.step_results.items()
                },
                "error_summary": result.error_summary
            }

    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def execute_task_background(task_id: str, config):
    """Execute task in background and store results."""
    try:
        result = await scheduler.execute_task(config)

        task_results[task_id] = TaskStatus(
            task_id=task_id,
            status="completed",
            created_at=task_results[task_id].created_at,
            completed_at=datetime.now(),
            result={
                "success": result.success,
                "execution_time": result.total_execution_time,
                "step_results": {
                    step_id: {
                        "status": step_result.status.value,
                        "execution_time": step_result.execution_time,
                        "error": step_result.error,
                        "tool_used": step_result.tool_used,
                        "output": step_result.output
                    }
                    for step_id, step_result in result.step_results.items()
                },
                "error_summary": result.error_summary
            }
        )

        logger.info(f"Background task {task_id} completed")

    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}")
        task_results[task_id] = TaskStatus(
            task_id=task_id,
            status="failed",
            created_at=task_results[task_id].created_at,
            completed_at=datetime.now(),
            result={"error": str(e)}
        )


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task execution status."""
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")

    task_status = task_results[task_id]
    return {
        "task_id": task_status.task_id,
        "status": task_status.status,
        "created_at": task_status.created_at,
        "completed_at": task_status.completed_at,
        "result": task_status.result
    }


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file for processing.

    Returns a file ID that can be used in task configurations.
    """
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        # Generate unique filename
        file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = upload_dir / file_id

        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "file_id": file_id,
            "filename": file.filename,
            "path": str(file_path),
            "size": len(content)
        }

    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_id}")
async def download_file(file_id: str):
    """Download a previously uploaded file."""
    file_path = Path("uploads") / file_id

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_id,
        media_type="application/octet-stream"
    )


@app.post("/config/validate")
async def validate_config(config: TaskConfig):
    """Validate a task configuration."""
    try:
        config_dict = config.dict()
        parsed_config = ConfigParser._parse_task_flow(config_dict)
        validation_errors = ConfigParser.validate_config(parsed_config)

        return {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "config": parsed_config.dict() if validation_errors else None
        }

    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "config": None
        }


@app.get("/config/templates")
async def get_config_templates():
    """Get available configuration templates."""
    templates = {
        "contract_analysis": {
            "name": "Contract Analysis Pipeline",
            "description": "Automated pipeline for parsing contracts, retrieving regulations, and generating analysis reports",
            "steps": [
                {
                    "id": "parse_contract",
                    "name": "Parse Contract Document",
                    "tool": "doc_parser",
                    "parameters": {"file_path": "contract.txt"},
                    "retry_count": 2
                },
                {
                    "id": "retrieve_regulations",
                    "name": "Retrieve Relevant Regulations",
                    "tool": "retrieval",
                    "parameters": {"query": "contract law regulatory compliance"},
                    "dependencies": ["parse_contract"]
                },
                {
                    "id": "generate_analysis",
                    "name": "Generate Analysis Report",
                    "tool": "generation",
                    "parameters": {
                        "type": "analysis",
                        "data": {"subject": "Contract Compliance Analysis"}
                    },
                    "dependencies": ["parse_contract", "retrieve_regulations"]
                }
            ],
            "parallel_groups": [["retrieve_regulations", "generate_analysis"]]
        }
    }

    return {"templates": templates}


if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "api_service:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True
    )
