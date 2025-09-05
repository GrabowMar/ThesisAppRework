import pytest
import uuid
import asyncio
from app.models import db, AnalysisTask, AnalyzerConfiguration, AnalysisResult
from app.constants import AnalysisType, SeverityLevel, JobPriority as Priority
from app.services.analyzer_integration import analysis_executor


def test_store_findings_creates_analysis_results(app):
    """Ensure that _store_findings persists AnalysisResult rows with normalized fields."""
    with app.app_context():
        # Minimal valid configuration data
        config = AnalyzerConfiguration()
        config.name = "test-config"
        config.analyzer_type = AnalysisType.SECURITY_BACKEND
        config.is_active = True
        config.config_data = '{}'
        db.session.add(config)
        db.session.commit()

        task = AnalysisTask()
        task.task_id = str(uuid.uuid4())
        task.analyzer_config_id = config.id
        task.analysis_type = AnalysisType.SECURITY_BACKEND
        task.priority = Priority.NORMAL
        task.target_model = "dummy_model"
        task.target_app_number = 1
        task.task_name = "Result Storage Test"
        db.session.add(task)
        db.session.commit()

        findings = [
            {
                "tool_name": "bandit",
                "tool_version": "1.2.3",
                "type": "finding",
                "title": "Use of eval",
                "description": "Insecure use of eval() detected",
                "severity": "HIGH",
                "confidence": "high",
                "file_path": "app/module.py",
                "line_number": 42,
                "code_snippet": "eval(user_input)",
                "category": "security",
                "rule_id": "B101",
                "tags": ["injection", "security"],
                "recommendations": ["Avoid eval", "Use ast.literal_eval if needed"],
                "structured_data": {"cwe": "CWE-94", "owasp": "A03"},
                "impact_score": 8.5,
                "business_impact": "high",
                "remediation_effort": "medium"
            },
            {
                "tool_name": "custom-tool",
                "title": "Hardcoded secret",
                "severity": "critical",
                "file_path": "app/secret.py",
                "line_number": 10,
                "code_snippet": "API_KEY = 'abcd'",
                "category": "security",
                "rule_id": "SEC001",
                "recommendation": "Move secret to environment variable"
            }
        ]

        asyncio.run(analysis_executor._store_findings(task, findings))  # noqa: SLF001
        db.session.commit()

        stored = AnalysisResult.query.filter_by(task_id=task.task_id).all()
        assert len(stored) == 2, "Expected two stored findings"

        # Order isn't guaranteed; find by tool_name
        bandit = next(x for x in stored if x.tool_name == "bandit")
        assert bandit.severity in {SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM, SeverityLevel.LOW}
        assert set(bandit.get_tags()) == {"injection", "security"}
        assert bandit.get_structured_data().get("cwe") == "CWE-94"
        assert bandit.impact_score == pytest.approx(8.5)

        second = next(x for x in stored if x.tool_name == "custom-tool")
        assert second.title.lower().startswith("hardcoded")
        # recommendation string converted to list
        assert any("Move secret" in r for r in second.get_recommendations())
