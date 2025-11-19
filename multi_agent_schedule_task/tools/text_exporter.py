"""
Text exporter tool.

Exports provided text content to a .txt file.
"""
import logging
from typing import Any, Dict
from pathlib import Path

from ..registry import BaseTool, tool_registry

logger = logging.getLogger(__name__)


class TextExporterTool(BaseTool):
    @property
    def name(self) -> str:
        return "text_exporter"

    @property
    def description(self) -> str:
        return "Export text content to a .txt file"

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        # Expect input_data to be a dict with 'content' and optional 'filename'
        if isinstance(input_data, dict):
            content = input_data.get("content")
            filename = input_data.get("filename", "outputs/report.txt")
        else:
            content = str(input_data)
            filename = "outputs/report.txt"

        if not content:
            logger.error("Text export failed: content parameter is required")
            raise ValueError("content parameter is required")

        out_path = Path(filename)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(str(content))
            logger.info(f"Text exported to: {out_path}")
            return {"filename": str(out_path), "status": "ok"}
        except Exception as e:
            logger.error(f"Text export failed: {e}")
            raise


# Register tool
try:
    tool_registry.register_tool("text_exporter", TextExporterTool)
except Exception:
    logger.debug("text_exporter registration skipped or already registered")
