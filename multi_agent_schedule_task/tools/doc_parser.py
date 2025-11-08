"""
Document parsing tool.
"""

import os
import logging
from typing import Any, Dict
from ..tools import BaseTool

logger = logging.getLogger(__name__)


class DocParseTool(BaseTool):
    """Tool for parsing documents."""

    @property
    def name(self) -> str:
        return "doc_parser"

    @property
    def description(self) -> str:
        return "Parses documents and extracts text content"

    def run(self, input_data: Any, context: Dict[str, Any]) -> str:
        """
        Parse a document file.

        Args:
            input_data: Dictionary containing 'file_path' key
            context: Execution context

        Returns:
            Extracted text content
        """
        try:
            file_path = input_data.get('file_path')
            if not file_path:
                raise ValueError("file_path parameter is required")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Simple text file parsing (can be extended for PDF, DOCX, etc.)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"Parsed document: {file_path}")
            return content

        except Exception as e:
            logger.error(f"Document parsing failed: {e}")
            raise
