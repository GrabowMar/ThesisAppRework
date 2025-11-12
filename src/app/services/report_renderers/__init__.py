# Report Renderers Package
# Provides rendering functions for different report formats

from .html_renderer import render_html
from .excel_renderer import render_excel
from .json_renderer import render_json

# PDF requires WeasyPrint with GTK libs on Windows - make optional
try:
    from .pdf_renderer import render_pdf
    PDF_AVAILABLE = True
except (ImportError, OSError) as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"PDF rendering unavailable: {e}")
    PDF_AVAILABLE = False
    
    def render_pdf(*args, **kwargs):
        """Placeholder when WeasyPrint unavailable"""
        raise RuntimeError("PDF rendering requires GTK libraries - see WeasyPrint docs for Windows installation")

__all__ = ['render_html', 'render_pdf', 'render_excel', 'render_json', 'PDF_AVAILABLE']
