"""
Content generation tool.
"""

import logging
import os
from typing import Any, Dict
from ..tools import BaseTool

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

logger = logging.getLogger(__name__)


class GenerationTool(BaseTool):
    """Tool for generating content like reports, summaries, etc."""

    @property
    def name(self) -> str:
        return "generation"

    @property
    def description(self) -> str:
        return "Generates content such as reports, summaries, and analysis"

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate content based on input data and context.

        Args:
            input_data: Dictionary containing generation parameters
            context: Execution context with previous step outputs

        Returns:
            Dictionary with generated content and metadata
        """
        try:
            content_type = input_data.get('type', 'report')
            template = input_data.get('template', '')
            data = input_data.get('data', {})
            output_format = input_data.get('output_format', 'text')  # text or pdf
            output_path = input_data.get('output_path', None)

            # Generate content based on type
            if content_type == 'report':
                text_content = self._generate_report(data, template)
            elif content_type == 'summary':
                text_content = self._generate_summary(data)
            elif content_type == 'analysis':
                text_content = self._generate_analysis(data)
            else:
                text_content = self._generate_generic_content(content_type, data, template)

            result = {
                'content': text_content,
                'format': output_format,
                'type': content_type
            }

            # Generate PDF if requested
            if output_format == 'pdf':
                if not HAS_REPORTLAB:
                    raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")

                pdf_path = self._generate_pdf(text_content, data, output_path)
                result['pdf_path'] = pdf_path
                result['pdf_generated'] = True
            else:
                result['pdf_generated'] = False

            return result

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
        """Generate an analysis based on input data and context."""
        subject = data.get('subject', 'Unknown')
        findings = data.get('findings', [])
        recommendations = data.get('recommendations', [])

        analysis = f"CONTRACT COMPLIANCE ANALYSIS REPORT\n\n"
        analysis += f"SUBJECT: {subject.upper()}\n\n"

        # Add contract information from context if available
        contract_info = data.get('contract_info', '')
        if contract_info:
            analysis += f"CONTRACT INFORMATION:\n{contract_info}\n\n"

        # Add regulatory findings
        if findings:
            analysis += "REGULATORY COMPLIANCE FINDINGS:\n"
            for finding in findings:
                analysis += f"• {finding}\n"
            analysis += "\n"
        else:
            analysis += "REGULATORY COMPLIANCE FINDINGS:\n"
            analysis += "• Contract terms appear to comply with general contract law principles\n"
            analysis += "• No immediate regulatory violations identified\n"
            analysis += "• Recommend detailed legal review for specific jurisdiction requirements\n\n"

        # Add recommendations
        if recommendations:
            analysis += "RECOMMENDATIONS:\n"
            for rec in recommendations:
                analysis += f"• {rec}\n"
        else:
            analysis += "RECOMMENDATIONS:\n"
            analysis += "• Ensure all parties have legal capacity to contract\n"
            analysis += "• Verify consideration is adequate and legally sufficient\n"
            analysis += "• Include clear termination and dispute resolution clauses\n"
            analysis += "• Consider data privacy implications if personal information is involved\n"
            analysis += "• Document compliance with applicable regulatory requirements\n"

        analysis += "\nLEGAL ANALYSIS:\n"
        analysis += "This analysis is based on general legal principles and should not be considered\n"
        analysis += "comprehensive legal advice. Consult with qualified legal counsel for specific\n"
        analysis += "situations and jurisdiction-specific requirements.\n"

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

    def _generate_pdf(self, text_content: str, data: Dict[str, Any], output_path: str = None) -> str:
        """Generate PDF from text content."""
        if not HAS_REPORTLAB:
            raise ImportError("ReportLab is required for PDF generation")

        # Generate output path if not provided
        if not output_path:
            import uuid
            # Create outputs directory
            outputs_dir = Path("outputs")
            outputs_dir.mkdir(exist_ok=True)
            output_path = str(outputs_dir / f"analysis_report_{uuid.uuid4().hex[:8]}.pdf")
        else:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()

        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=20,
        )

        normal_style = styles['Normal']

        # Build PDF content
        story = []

        # Add title
        title = data.get('title', 'Analysis Report')
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 12))

        # Process text content and convert to PDF elements
        lines = text_content.split('\n')
        current_paragraph = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_paragraph:
                    # Add accumulated paragraph
                    para_text = ' '.join(current_paragraph)
                    if para_text:
                        story.append(Paragraph(para_text, normal_style))
                        story.append(Spacer(1, 6))
                    current_paragraph = []
            elif line.startswith('# '):
                # Main heading
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    if para_text:
                        story.append(Paragraph(para_text, normal_style))
                    current_paragraph = []
                heading_text = line[2:].strip()
                story.append(Paragraph(heading_text, title_style))
                story.append(Spacer(1, 12))
            elif line.startswith('## '):
                # Sub heading
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    if para_text:
                        story.append(Paragraph(para_text, normal_style))
                    current_paragraph = []
                heading_text = line[3:].strip()
                story.append(Paragraph(heading_text, heading_style))
                story.append(Spacer(1, 12))
            elif line.startswith('- '):
                # Bullet point
                bullet_text = line[2:].strip()
                story.append(Paragraph(f"• {bullet_text}", normal_style))
                story.append(Spacer(1, 6))
            else:
                # Regular text
                current_paragraph.append(line)

        # Add any remaining paragraph
        if current_paragraph:
            para_text = ' '.join(current_paragraph)
            if para_text:
                story.append(Paragraph(para_text, normal_style))

        # Build PDF
        doc.build(story)

        logger.info(f"Generated PDF: {output_path}")
        return output_path
