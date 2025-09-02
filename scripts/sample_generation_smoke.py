"""Smoke test for SampleGenerationService mock generation.

Run with (PowerShell):
  python scripts/sample_generation_smoke.py

It will:
 1. Upsert a single template (app_num=1)
 2. Invoke mock generation (model='mock/test-model')
 3. Print result metadata
 4. Print resulting project structure
"""
from __future__ import annotations

import asyncio
from pprint import pprint
import sys
from pathlib import Path

# Ensure src/ is on path when running as a script
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.services.sample_generation_service import get_sample_generation_service  # noqa: E402


def main():
    svc = get_sample_generation_service()
    # Upsert a simple template
    svc.upsert_templates([
        {
            "app_num": 1,
            "name": "hello_world_api",
            "content": "Simple Hello World API with a /health endpoint",
            "requirements": ["Flask"],
        }
    ])
    print("Templates:")
    pprint(svc.list_templates())

    async def run():
        rid, result = await svc.generate_async("1", "mock/test-model")
        return rid, result

    rid, result = asyncio.run(run())

    print("\nResult ID:", rid)
    print("Result (metadata):")
    pprint(result.to_dict(include_content=False))

    print("\nProject Structure:")
    pprint(svc.project_structure())

    print("\nDone. Check the 'generated/' directory for files.")


if __name__ == "__main__":
    main()
