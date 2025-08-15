"""
Testing Routes
=============

Routes for managing testing operations and configurations.
"""

import logging
from flask import Blueprint, jsonify

# Set up logger
logger = logging.getLogger(__name__)

testing_bp = Blueprint('testing', __name__, url_prefix='/testing')


@testing_bp.route('/')
def testing_center():
    """Deprecated: Redirect to Analysis hub."""
    from flask import redirect, url_for, flash
    flash('Testing has moved to Analysis.', 'info')
    return redirect(url_for('analysis.analysis_hub'))


@testing_bp.route('/security')
def security_testing():
    """Deprecated: Redirect to Analysis → Create (Security)."""
    from flask import redirect, flash
    flash('Security testing moved to Analysis → Create.', 'info')
    return redirect('/analysis/create#security')


@testing_bp.route('/performance')
def performance_testing():
    """Deprecated: Redirect to Analysis → Create (Performance)."""
    from flask import redirect, flash
    flash('Performance testing moved to Analysis → Create.', 'info')
    return redirect('/analysis/create#performance')


@testing_bp.route('/batch')
def batch_testing():
    """Deprecated: Redirect to Analysis Hub."""
    from flask import redirect, url_for, flash
    flash('Batch testing is centralized in Analysis → Analyses.', 'info')
    return redirect(url_for('analysis.analyses_list_page'))


@testing_bp.route('/results')
def testing_results():
    """Deprecated: Redirect to Analysis hub."""
    from flask import redirect, url_for, flash
    flash('Testing results are visible in Analysis lists and detail pages.', 'info')
    return redirect(url_for('analysis.analyses_list_page'))


"""Legacy Testing API Endpoints (deprecated).

These routes were superseded by unified /analysis endpoints and are kept only
to avoid breaking external callers. They now return 410 Gone with guidance.
"""

@testing_bp.route('/api/run-with-config', methods=['POST'])
def run_test_with_config():
    return jsonify({
        'success': False,
        'error': 'Deprecated. Use /analysis endpoints instead.'
    }), 410


@testing_bp.route('/api/results/enhanced')
def get_enhanced_results():
    return jsonify({
        'success': False,
        'error': 'Deprecated. Use /analysis list endpoints instead.'
    }), 410


@testing_bp.route('/api/results/<int:result_id>/detail')
def get_result_detail(result_id):
    return jsonify({
        'success': False,
        'error': 'Deprecated. Use /analysis results pages instead.'
    }), 410


@testing_bp.route('/api/results/<int:result_id>/download')
def download_result(result_id):
    return jsonify({
        'success': False,
        'error': 'Deprecated. Use /analysis results pages instead.'
    }), 410


@testing_bp.route('/api/results/export')
def export_results():
    return jsonify({
        'success': False,
        'error': 'Deprecated. Use /analysis list pages instead.'
    }), 410


# @testing_bp.route('/enhanced-config')
# def enhanced_config():
#     """Enhanced testing configuration page with models and apps loaded.
#     
#     NOTE: This route is commented out as configuration should be dynamically 
#     created before tests based on the selected model, not directly accessed.
#     The configuration functionality is now integrated into the test workflow.
#     """
#     try:
#         from ..models import ModelCapability, GeneratedApplication
#         from sqlalchemy import desc
# 
#         # Load all available models
#         models = ModelCapability.query.order_by(ModelCapability.model_name).all()
#         
#         # Load recent applications for quick access
#         recent_applications = GeneratedApplication.query.order_by(
#             desc(GeneratedApplication.created_at)
#         ).limit(50).all()
#         
#         # Group applications by model for easier access
#         apps_by_model = {}
#         for app in recent_applications:
#             if app.model_slug not in apps_by_model:
#                 apps_by_model[app.model_slug] = []
#             apps_by_model[app.model_slug].append(app)
# 
#         return render_template(
#             'single_page.html',
#             page_title='Enhanced Testing Configuration',
#             page_icon='fa-cogs',
#             page_subtitle='Advanced analyzer configuration with database integration',
#             main_partial='partials/testing/enhanced_config.html',
#             models=models,
#             recent_applications=recent_applications,
#             apps_by_model=apps_by_model
#         )
#     except Exception as e:
#         logger.error(f"Error loading enhanced config: {e}")
#         flash('Error loading enhanced configuration page', 'error')
#         return render_template(
#             'single_page.html',
#             page_title='Error',
#             page_icon='fa-triangle-exclamation',
#             page_subtitle='Enhanced Config Error',
#             main_partial='partials/common/error.html',
#             error_code=500,
#             error_title='Enhanced Config Error',
#             error_message=str(e)
#         )
