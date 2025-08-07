@testing_bp.route("/api/containerized-test/<int:test_id>/status")
def get_containerized_test_status(test_id):
    """Get status of a containerized test."""
    try:
        from models import ContainerizedTest
        
        test = ContainerizedTest.query.get_or_404(test_id)
        
        # Try to get updated status from the service
        # This could be enhanced to actually query the containerized service
        status_info = {
            'status': test.status.value,
            'submitted_at': test.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if test.submitted_at else None,
            'started_at': test.started_at.strftime('%Y-%m-%d %H:%M:%S') if test.started_at else None,
            'completed_at': test.completed_at.strftime('%Y-%m-%d %H:%M:%S') if test.completed_at else None,
            'execution_duration': test.execution_duration
        }
        
        return render_template("partials/test_status_info.html", status=status_info, test=test)
    except Exception as e:
        logger.error(f"Error getting containerized test status: {e}")
        return f"<span class='text-danger'>Error: {e}</span>"


@testing_bp.route("/api/containerized-test/<int:test_id>/results")
def get_containerized_test_results(test_id):
    """Get results of a containerized test."""
    try:
        from models import ContainerizedTest
        
        test = ContainerizedTest.query.get_or_404(test_id)
        
        results = test.get_result_data()
        
        return render_template("partials/containerized_test_results_modal.html", test=test, results=results)
    except Exception as e:
        logger.error(f"Error getting containerized test results: {e}")
        return render_template("partials/error_modal.html", error=str(e))

