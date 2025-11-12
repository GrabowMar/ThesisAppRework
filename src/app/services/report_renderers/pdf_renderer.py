"""
PDF Report Renderer

Generates PDF reports using WeasyPrint from HTML templates.
"""
import logging
from pathlib import Path
from typing import Dict, Any
from flask import render_template, current_app
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

logger = logging.getLogger(__name__)


def render_pdf(report, data: Dict[str, Any], output_path: Path) -> None:
    """
    Render report as PDF using WeasyPrint.
    
    Args:
        report: Report model instance
        data: Report data dictionary
        output_path: Path where PDF file should be saved
    """
    try:
        template_name = _get_template_name(report.report_type)
        
        # Render HTML first
        html_content = render_template(
            template_name,
            report=report,
            data=data,
            generated_at=data.get('timestamp'),
            print_mode=True  # Enable print-specific rendering
        )
        
        # Configure fonts
        font_config = FontConfiguration()
        
        # Get CSS files for print
        css_files = _get_print_css_files()
        css_objects = [CSS(filename=str(css_file), font_config=font_config) for css_file in css_files]
        
        # Generate PDF
        HTML(string=html_content, base_url=str(current_app.static_folder)).write_pdf(
            output_path,
            stylesheets=css_objects,
            font_config=font_config
        )
        
        logger.info(f"Rendered PDF report to {output_path}")
        
    except Exception as e:
        logger.error(f"Error rendering PDF report: {e}", exc_info=True)
        raise


def _get_template_name(report_type: str) -> str:
    """Get Jinja2 template name for report type."""
    template_map = {
        'app_analysis': 'pages/reports/app_analysis.html',
        'model_comparison': 'pages/reports/model_comparison.html',
        'tool_effectiveness': 'pages/reports/tool_effectiveness.html',
        'executive_summary': 'pages/reports/executive_summary.html',
        'custom': 'pages/reports/custom.html'
    }
    
    return template_map.get(report_type, 'pages/reports/default.html')


def _get_print_css_files() -> list:
    """Get list of CSS files to use for PDF generation."""
    static_dir = Path(current_app.static_folder)
    
    css_files = [
        static_dir / 'css' / 'analysis-report.css',
        static_dir / 'css' / 'report-print.css'
    ]
    
    # Only include files that exist
    return [f for f in css_files if f.exists()]
