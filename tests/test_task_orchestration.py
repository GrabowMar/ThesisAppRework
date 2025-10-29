"""
Test Task Orchestration End-to-End
===================================

Tests the complete task creation and dispatch flow with the fixed architecture.
"""

import pytest
import time
from app.services.task_service import AnalysisTaskService
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db


@pytest.mark.integration
def test_single_task_creation(app):
    """Test creation of a single analysis task (no subtasks)."""
    with app.app_context():
        # Create task with single tool
        task = AnalysisTaskService.create_task(
            model_slug="test_model",
            app_number=1,
            tools=["bandit"],
            priority="normal",
            custom_options={'test': 'single_task'},
            dispatch=False  # Don't dispatch to Celery for this test
        )
        
        assert task is not None
        assert task.task_id is not None
        assert task.target_model == "test_model"
        assert task.target_app_number == 1
        assert task.status == AnalysisStatus.PENDING
        assert task.is_main_task is None or task.is_main_task is False
        
        # Verify metadata contains tools
        metadata = task.get_metadata()
        assert 'custom_options' in metadata
        assert 'tools' in metadata['custom_options']
        assert metadata['custom_options']['tools'] == ["bandit"]
        
        print(f"✓ Single task created successfully: {task.task_id}")


@pytest.mark.integration
def test_multi_service_task_creation(app):
    """Test creation of main task with multiple subtasks (unified analysis)."""
    with app.app_context():
        # Create task with tools from multiple services
        tools = ["bandit", "safety", "eslint"]  # static-analyzer tools
        
        task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug="test_model",
            app_number=2,
            tools=tools,
            priority="normal",
            custom_options={'test': 'multi_service_task'}
        )
        
        assert task is not None
        assert task.task_id is not None
        assert task.is_main_task is True
        assert task.target_model == "test_model"
        assert task.target_app_number == 2
        assert task.status == AnalysisStatus.PENDING
        
        # Verify metadata
        metadata = task.get_metadata()
        assert 'custom_options' in metadata
        assert metadata['custom_options']['unified_analysis'] is True
        assert 'tools_by_service' in metadata['custom_options']
        
        # Verify subtasks were created
        db.session.refresh(task)
        subtasks = task.subtasks
        assert len(subtasks) > 0
        
        print(f"✓ Main task created with {len(subtasks)} subtask(s): {task.task_id}")
        
        # Verify each subtask
        for subtask in subtasks:
            assert subtask.parent_task_id == task.task_id
            assert subtask.is_main_task is False
            assert subtask.service_name is not None
            assert subtask.status == AnalysisStatus.PENDING
            
            # Verify subtask metadata has tool names (not IDs)
            sub_metadata = subtask.get_metadata()
            assert 'custom_options' in sub_metadata
            assert 'tool_names' in sub_metadata['custom_options']
            assert isinstance(sub_metadata['custom_options']['tool_names'], list)
            assert all(isinstance(tool, str) for tool in sub_metadata['custom_options']['tool_names'])
            
            print(f"  ✓ Subtask {subtask.task_id} for service '{subtask.service_name}' with tools: {sub_metadata['custom_options']['tool_names']}")


@pytest.mark.integration  
def test_tools_by_service_grouping(app):
    """Test that tools are correctly grouped by their service containers."""
    with app.app_context():
        from app.engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        
        # Get tools from different services
        all_tools = registry.get_all_tools()
        
        # Find tools from different services
        static_tools = []
        dynamic_tools = []
        perf_tools = []
        
        for tool_name, tool_obj in all_tools.items():
            if tool_obj.available:
                service = tool_obj.container.value if tool_obj.container else None
                if service == 'static-analyzer' and len(static_tools) < 2:
                    static_tools.append(tool_name)
                elif service == 'dynamic-analyzer' and len(dynamic_tools) < 1:
                    dynamic_tools.append(tool_name)
                elif service == 'performance-tester' and len(perf_tools) < 1:
                    perf_tools.append(tool_name)
        
        # Mix tools from different services
        mixed_tools = static_tools + dynamic_tools + perf_tools
        
        if len(mixed_tools) < 2:
            pytest.skip("Not enough tools available from different services")
        
        task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug="test_model",
            app_number=3,
            tools=mixed_tools,
            priority="normal"
        )
        
        # Verify grouping
        metadata = task.get_metadata()
        tools_by_service = metadata['custom_options']['tools_by_service']
        
        # Check that tools are grouped by service
        assert isinstance(tools_by_service, dict)
        assert len(tools_by_service) > 0
        
        # Verify each service has tool names (not IDs)
        for service_name, tool_list in tools_by_service.items():
            assert isinstance(tool_list, list)
            assert all(isinstance(tool, str) for tool in tool_list)
            print(f"  ✓ Service '{service_name}' has tools: {tool_list}")
        
        print(f"✓ Tools correctly grouped by service: {list(tools_by_service.keys())}")


@pytest.mark.integration
def test_task_metadata_stores_tool_names(app):
    """Test that tool names (not IDs) are stored in task metadata."""
    with app.app_context():
        tools = ["bandit", "safety"]
        
        task = AnalysisTaskService.create_task(
            model_slug="test_model",
            app_number=4,
            tools=tools,
            dispatch=False
        )
        
        metadata = task.get_metadata()
        stored_tools = metadata['custom_options']['tools']
        
        # Verify tools are stored as strings (names), not integers (IDs)
        assert isinstance(stored_tools, list)
        assert all(isinstance(tool, str) for tool in stored_tools)
        assert stored_tools == tools
        
        print(f"✓ Tools stored as names in metadata: {stored_tools}")


@pytest.mark.integration
def test_no_tool_id_in_subtask_metadata(app):
    """Test that subtask metadata does NOT contain tool_ids."""
    with app.app_context():
        tools = ["bandit", "safety", "eslint"]
        
        task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug="test_model",
            app_number=5,
            tools=tools
        )
        
        db.session.refresh(task)
        for subtask in task.subtasks:
            metadata = subtask.get_metadata()
            
            # Verify tool_ids field does NOT exist (should be tool_names)
            assert 'tool_ids' not in metadata.get('custom_options', {})
            assert 'tool_names' in metadata.get('custom_options', {})
            
            tool_names = metadata['custom_options']['tool_names']
            assert isinstance(tool_names, list)
            assert all(isinstance(tool, str) for tool in tool_names)
            
        print(f"✓ Subtasks use tool_names (not tool_ids) in metadata")


if __name__ == '__main__':
    # Allow running directly for quick testing
    pytest.main([__file__, '-v', '-s'])
