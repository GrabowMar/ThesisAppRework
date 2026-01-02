import json

from app.utils.sarif_utils import extract_sarif_to_files


def test_unified_result_service_remaps_ruff_sarif_severity(tmp_path):
    """Test that SARIF extraction remaps Ruff severity levels correctly.
    
    This test verifies the shared sarif_utils.extract_sarif_to_files function
    which is used by UnifiedResultService, TaskExecutionService, and AnalyzerManager.
    """
    # Minimal Ruff SARIF (Ruff commonly emits everything as "error")
    ruff_sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "ruff"}},
                "results": [
                    {
                        "ruleId": "W291",
                        "level": "error",
                        "message": {"text": "Trailing whitespace"},
                        "locations": [],
                    },
                    {
                        "ruleId": "E402",
                        "level": "error",
                        "message": {"text": "Module level import not at top of file"},
                        "locations": [],
                    },
                ],
            }
        ],
    }

    services = {
        "static-analyzer": {
            "analysis": {
                "results": {
                    "python": {
                        "ruff": {
                            "status": "success",
                            "executed": True,
                            "sarif": ruff_sarif,
                        }
                    }
                }
            }
        }
    }

    # Act: extract SARIF to file using the shared utility
    sarif_dir = tmp_path / "sarif"
    sarif_dir.mkdir(exist_ok=True)
    extracted_services = extract_sarif_to_files(services, sarif_dir)

    # The filename includes service_name_category prefix: static-analyzer_python_ruff.sarif.json
    sarif_file = sarif_dir / "static-analyzer_python_ruff.sarif.json"
    assert sarif_file.exists(), f"Expected {sarif_file}, got files: {list(sarif_dir.iterdir())}"

    written = json.loads(sarif_file.read_text(encoding="utf-8"))
    results = written["runs"][0]["results"]

    w291 = next(r for r in results if r.get("ruleId") == "W291")
    assert w291["level"] == "note"
    assert w291.get("properties", {}).get("problem.severity") == "low"

    e402 = next(r for r in results if r.get("ruleId") == "E402")
    assert e402["level"] == "warning"
    assert e402.get("properties", {}).get("problem.severity") == "medium"

    # Services should now reference the extracted SARIF file
    tool_entry = extracted_services["static-analyzer"]["analysis"]["results"]["python"]["ruff"]
    assert tool_entry["sarif"].get("sarif_file") == "sarif/static-analyzer_python_ruff.sarif.json"
