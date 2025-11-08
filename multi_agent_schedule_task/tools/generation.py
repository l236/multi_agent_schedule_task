"""
Content generation tool.
"""

import logging
from typing import Any, Dict
from ..tools import BaseTool

logger = logging.getLogger(__name__)


class GenerationTool(BaseTool):
    """Tool for generating content like reports, summaries, etc."""

    @property
    def name(self) -> str:
        return "generation"

    @property
    def description(self) -> str:
        return "Generates content such as reports, summaries, and analysis"

    def run(self, input_data: Any, context: Dict[str, Any]) -> str:
        """
        Generate content based on input data and context.

        Args:
            input_data: Dictionary containing generation parameters
            context: Execution context with previous step outputs

        Returns:
            Generated content
        """
        try:
            content_type = input_data.get('type', 'report')
            template = input_data.get('template', '')
            data = input_data.get('data', {})

            if content_type == 'report':
                return self._generate_report(data, template)
            elif content_type == 'summary':
                return self._generate_summary(data)
            elif content_type == 'analysis':
                return self._generate_analysis(data)
            else:
                return self._generate_generic_content(content_type, data, template)

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            raise

    def _generate_report(self, data: Dict[str, Any], template: str) -> str:
        """Generate a structured report."""
        title = data.get('title', 'Analysis Report')
        sections = data.get('sections', [])

        report = f"# {title}\n\n"

        for section in sections:
            section_title = section.get('title', 'Section')
            content = section.get('content', '')
            report += f"## {section_title}\n\n{content}\n\n"

        if template:
            report += f"\n**Template Used:** {template}\n"

        logger.info(f"Generated report: {title}")
        return report

    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate a summary of provided data."""
        source_data = data.get('source_data', '')
        key_points = data.get('key_points', [])

        summary = "SUMMARY\n\n"
        summary += f"Source: {source_data[:100]}...\n\n" if source_data else ""

        if key_points:
            summary += "Key Points:\n"
            for i, point in enumerate(key_points, 1):
                summary += f"{i}. {point}\n"
        else:
            summary += "No specific key points provided.\n"

        logger.info("Generated summary")
        return summary

    def _generate_analysis(self, data: Dict[str, Any]) -> str:
        """Generate an analysis based on input data."""
        subject = data.get('subject', 'Unknown')
        findings = data.get('findings', [])
        recommendations = data.get('recommendations', [])

        analysis = f"ANALYSIS: {subject.upper()}\n\n"

        if findings:
            analysis += "FINDINGS:\n"
            for finding in findings:
                analysis += f"- {finding}\n"
            analysis += "\n"

        if recommendations:
            analysis += "RECOMMENDATIONS:\n"
            for rec in recommendations:
                analysis += f"- {rec}\n"
        else:
            analysis += "No specific recommendations provided.\n"

        logger.info(f"Generated analysis for: {subject}")
        return analysis

    def _generate_generic_content(self, content_type: str, data: Dict[str, Any], template: str) -> str:
        """Generate generic content."""
        content = f"Generated {content_type.upper()}\n\n"

        if template:
            content += f"Template: {template}\n\n"

        for key, value in data.items():
            content += f"{key.title()}: {value}\n"

        logger.info(f"Generated generic content: {content_type}")
        return content
