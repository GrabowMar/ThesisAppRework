import json

from app.services.unified_result_service import UnifiedResultService


def test_unified_result_service_remaps_ruff_sarif_severity(tmp_path):
    service = UnifiedResultService()

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

    payload = {
        "services": {
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
    }

    # Act: extract SARIF to file; should remap before writing
    service._extract_sarif_to_files(payload, tmp_path)

    sarif_file = tmp_path / "sarif" / "ruff.sarif.json"
    assert sarif_file.exists()

    written = json.loads(sarif_file.read_text(encoding="utf-8"))
    results = written["runs"][0]["results"]

    w291 = next(r for r in results if r.get("ruleId") == "W291")
    assert w291["level"] == "note"
    assert w291.get("properties", {}).get("problem.severity") == "low"

    e402 = next(r for r in results if r.get("ruleId") == "E402")
    assert e402["level"] == "warning"
    assert e402.get("properties", {}).get("problem.severity") == "medium"

    # Payload should now reference the extracted SARIF file
    tool_entry = payload["services"]["static-analyzer"]["analysis"]["results"]["python"]["ruff"]
    assert tool_entry["sarif"].get("sarif_file") == "sarif/ruff.sarif.json"
