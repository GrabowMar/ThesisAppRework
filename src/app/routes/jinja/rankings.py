"""
Rankings Routes
===============

Routes for AI model rankings aggregation and selection page.
Provides leaderboard with coding benchmarks and filtering capabilities.

Chapter 4 MSS (Model Selection Score) methodology:
MSS = 0.35×Adoption + 0.30×Benchmarks + 0.20×CostEfficiency + 0.15×Accessibility

Static benchmark data loaded by default for fast page loads.
Live refresh available on-demand via refresh button.
"""

import logging

from flask import Blueprint, request, jsonify, session, flash, redirect, url_for
from flask_login import current_user

from flask import render_template
from app.services.model_rankings_service import get_rankings_service

logger = logging.getLogger(__name__)

# Blueprint for rankings routes
rankings_bp = Blueprint('rankings', __name__, url_prefix='/rankings')


@rankings_bp.before_request
def require_authentication():
    """Require authentication for all rankings endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access model rankings.', 'info')
        return redirect(url_for('auth.login', next=request.url))


@rankings_bp.route('/')
def rankings_index():
    """Main rankings page with filterable leaderboard."""
    service = get_rankings_service()
    
    # Get rankings from cache or static data (fast path)
    rankings = service.aggregate_rankings(force_refresh=False, fetch_live=False)
    
    # Get unique providers for filter dropdown
    providers = sorted(set(r.get('provider', 'unknown') for r in rankings if r.get('provider')))
    
    # Get fetch status
    fetch_status = service.get_fetch_status()
    
    # Get selected models from session
    selected_models = session.get('selected_ranking_models', [])
    
    return render_template(
        'pages/rankings/rankings_main.html',
        rankings=rankings,
        providers=providers,
        fetch_status=fetch_status,
        selected_models=selected_models,
        page_title='AI Model Rankings - Coding Benchmarks'
    )


@rankings_bp.route('/refresh', methods=['POST'])
def refresh_rankings():
    """Force refresh rankings - clears cache and reloads static data."""
    service = get_rankings_service()
    
    try:
        # Clear cache
        service.clear_cache()
        # Reload from static data (fast)
        rankings = service.aggregate_rankings(force_refresh=True, fetch_live=False)
        
        flash(f'Successfully refreshed rankings for {len(rankings)} models from static data.', 'success')
        
    except Exception as e:
        logger.error(f"Error refreshing rankings: {e}")
        flash(f'Error refreshing rankings: {str(e)}', 'error')
    
    return redirect(url_for('rankings.rankings_index'))


@rankings_bp.route('/refresh-live', methods=['POST'])
def refresh_rankings_live():
    """Force refresh rankings from live external sources (slower)."""
    service = get_rankings_service()
    
    try:
        # Clear cache
        service.clear_cache()
        # Fetch from live sources (may take 10-30 seconds)
        rankings = service.aggregate_rankings(force_refresh=True, fetch_live=True)
        
        flash(f'Successfully refreshed rankings for {len(rankings)} models from live sources.', 'success')
        
    except Exception as e:
        logger.error(f"Error refreshing rankings from live sources: {e}")
        flash(f'Error refreshing rankings: {str(e)}', 'error')
    
    return redirect(url_for('rankings.rankings_index'))


@rankings_bp.route('/api/rankings')
def api_get_rankings():
    """API endpoint to get filtered rankings with pagination and search."""
    service = get_rankings_service()
    
    # Get rankings
    rankings = service.aggregate_rankings(force_refresh=False)
    
    # Parse filter parameters
    max_price = request.args.get('max_price', type=float)
    min_context = request.args.get('min_context', type=int)
    provider = request.args.get('provider')  # Single provider from dropdown
    providers = request.args.getlist('providers') or ([provider] if provider else [])
    include_free = request.args.get('exclude_free', '') not in ('1', 'true')
    min_composite = request.args.get('min_composite', type=float)
    has_benchmarks = request.args.get('has_benchmarks', '') in ('1', 'true')
    
    # Search term
    search = request.args.get('search', '').strip().lower()
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    per_page = min(max(per_page, 10), 100)  # Limit between 10 and 100
    
    # Sorting
    sort_by = request.args.get('sort_by', 'composite')
    sort_dir = request.args.get('sort_dir', 'desc')
    
    # Apply filters
    filtered = service.filter_rankings(
        rankings,
        max_price=max_price,
        min_context=min_context,
        providers=providers if providers else None,
        include_free=include_free,
        min_composite=min_composite,
        has_benchmarks=has_benchmarks
    )
    
    # Apply search
    if search:
        filtered = [
            r for r in filtered
            if search in (r.get('model_name', '') or '').lower()
            or search in (r.get('model_id', '') or '').lower()
            or search in (r.get('provider', '') or '').lower()
        ]
    
    # Apply sorting - MSS columns (Chapter 4 methodology)
    sort_key_map = {
        'mss': 'mss_score',
        'composite': 'mss_score',  # Legacy alias
        'adoption': 'adoption_score',
        'benchmark': 'benchmark_score',
        'cost': 'cost_efficiency_score',
        'access': 'accessibility_score',
        'bfcl': 'bfcl_score',
        'webdev': 'webdev_elo',
        'livebench': 'livebench_coding',
        'livecodebench': 'livecodebench',
        'arc_agi': 'arc_agi_score',
        'simplebench': 'simplebench_score',
        'gpqa': 'gpqa_score',
        'seal': 'seal_coding_score',
        'canaicode': 'canaicode_score',
        'context': 'context_length',
        'price': 'price_per_million_input',
        'name': 'model_name'
    }
    sort_key = sort_key_map.get(sort_by, 'mss_score')
    reverse = sort_dir == 'desc'
    
    def get_sort_value(item):
        val = item.get(sort_key)
        # Fallback for mss_score to composite_score for backward compatibility
        if val is None and sort_key == 'mss_score':
            val = item.get('composite_score')
        if val is None:
            return float('-inf') if reverse else float('inf')
        return val
    
    filtered.sort(key=get_sort_value, reverse=reverse)
    
    # Calculate pagination
    total = len(filtered)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]
    
    # Statistics
    unique_providers = set(r.get('provider') for r in filtered if r.get('provider'))
    with_benchmarks = sum(1 for r in filtered if r.get('benchmark_score', 0) > 0)
    
    return jsonify({
        'success': True,
        'count': len(paginated),
        'rankings': paginated,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        },
        'statistics': {
            'total': total,
            'with_benchmarks': with_benchmarks,
            'unique_providers': len(unique_providers)
        }
    })


@rankings_bp.route('/api/top-models')
def api_get_top_models():
    """API endpoint to get top N models with custom weights."""
    service = get_rankings_service()
    
    # Parse parameters
    count = request.args.get('count', 10, type=int)
    count = min(max(count, 1), 50)  # Limit between 1 and 50
    
    # Parse weights (percentages 0-100)
    weights = {}
    weight_keys = ['humaneval_plus', 'swe_bench_verified', 'bigcodebench_hard', 
                   'livebench_coding', 'mbpp_plus', 'livecodebench']
    
    for key in weight_keys:
        weight = request.args.get(f'weight_{key}', type=float)
        if weight is not None and weight > 0:
            weights[key] = weight / 100  # Convert percentage to decimal
    
    # Normalize weights to sum to 1.0
    if weights:
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
    else:
        weights = None  # Use defaults
    
    # Parse filters
    max_price = request.args.get('max_price', type=float)
    min_context = request.args.get('min_context', type=int)
    providers = request.args.getlist('providers')
    include_free = request.args.get('include_free', 'true').lower() == 'true'
    has_benchmarks = request.args.get('has_benchmarks', 'true').lower() == 'true'
    
    # Get top models
    top_models = service.get_top_models(
        count=count,
        weights=weights,
        max_price=max_price,
        min_context=min_context,
        providers=providers if providers else None,
        include_free=include_free,
        has_benchmarks=has_benchmarks
    )
    
    return jsonify({
        'success': True,
        'count': len(top_models),
        'weights_used': weights,
        'models': top_models
    })


@rankings_bp.route('/api/select-models', methods=['POST'])
def api_select_models():
    """Save selected models to session for pipeline use."""
    try:
        data = request.get_json() or {}
        model_ids = data.get('model_ids', [])
        
        # Validate and limit to 10 models
        if len(model_ids) > 10:
            model_ids = model_ids[:10]
        
        # Store in session
        session['selected_ranking_models'] = model_ids
        
        return jsonify({
            'success': True,
            'selected_count': len(model_ids),
            'model_ids': model_ids
        })
        
    except Exception as e:
        logger.error(f"Error selecting models: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@rankings_bp.route('/api/selected-models')
def api_get_selected_models():
    """Get currently selected models."""
    selected = session.get('selected_ranking_models', [])
    return jsonify({
        'success': True,
        'model_ids': selected,
        'count': len(selected)
    })


@rankings_bp.route('/export')
def export_rankings():
    """Export filtered rankings as JSON."""
    service = get_rankings_service()
    
    # Get rankings
    rankings = service.aggregate_rankings(force_refresh=False)
    
    # Parse filter parameters
    max_price = request.args.get('max_price', type=float)
    min_context = request.args.get('min_context', type=int)
    providers = request.args.getlist('providers')
    include_free = request.args.get('include_free', 'true').lower() == 'true'
    has_benchmarks = request.args.get('has_benchmarks', '') in ('1', 'true')
    
    # Apply filters
    filtered = service.filter_rankings(
        rankings,
        max_price=max_price,
        min_context=min_context,
        providers=providers if providers else None,
        include_free=include_free,
        has_benchmarks=has_benchmarks
    )
    
    # Return as downloadable JSON
    response = jsonify({
        'exported_at': __import__('datetime').datetime.now().isoformat(),
        'filter_applied': {
            'max_price': max_price,
            'min_context': min_context,
            'providers': providers,
            'include_free': include_free,
            'has_benchmarks': has_benchmarks
        },
        'count': len(filtered),
        'models': filtered
    })
    response.headers['Content-Disposition'] = 'attachment; filename=model_rankings.json'
    return response


@rankings_bp.route('/status')
def rankings_status():
    """Get status of rankings data sources."""
    service = get_rankings_service()
    fetch_status = service.get_fetch_status()
    
    return jsonify({
        'success': True,
        'status': fetch_status
    })
