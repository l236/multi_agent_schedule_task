"""
PDF exporter tool.

Exports provided text content to a PDF file using ReportLab.
"""
import logging
from typing import Any, Dict
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from ..registry import BaseTool, tool_registry

logger = logging.getLogger(__name__)


class PdfExporterTool(BaseTool):
    @property
    def name(self) -> str:
        return "pdf_exporter"

    @property
    def description(self) -> str:
        return "Export text content to a PDF file"

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        # Expect input_data to be a dict with 'content' and optional 'filename'
        if isinstance(input_data, dict):
            content = input_data.get("content")
            filename = input_data.get("filename", "outputs/report.pdf")
        else:
            content = str(input_data)
            filename = "outputs/report.pdf"

        if not content:
            logger.error("PDF export failed: content parameter is required")
            raise ValueError("content parameter is required")

        out_path = Path(filename)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            c = canvas.Canvas(str(out_path), pagesize=letter)
            width, height = letter
            # Simple text wrapping
            lines = str(content).splitlines()
            y = height - 72
            for line in lines:
                # If line too long, wrap by 100 chars
                for i in range(0, len(line), 100):
                    c.drawString(72, y, line[i:i+100])
                    y -= 14
                    if y < 72:
                        c.showPage()
                        y = height - 72
            c.save()
            logger.info(f"PDF exported to: {out_path}")
            return {"filename": str(out_path), "status": "ok"}
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            raise


# Register tool
try:
    tool_registry.register_tool("pdf_exporter", PdfExporterTool)
except Exception:
    logger.debug("pdf_exporter registration skipped or already registered")
