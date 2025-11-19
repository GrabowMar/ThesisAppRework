import sys
from pathlib import Path
sys.path.append(str(Path.cwd()))
from analyzer.analyzer_manager import AnalyzerManager

manager = AnalyzerManager()
result = manager._normalize_and_validate_app('google_gemini-2.5-pro', 1)
print(f"Result: {result}")
