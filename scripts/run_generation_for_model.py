"""Utility script to generate multiple sample apps for a given model slug."""
import argparse
import asyncio
import sys
from typing import Iterable, Tuple

sys.path.insert(0, 'src')

from app import create_app  # type: ignore  # noqa: E402
from app.services.generation import get_generation_service  # type: ignore  # noqa: E402


async def generate_apps(model_slug: str, entries: Iterable[Tuple[int, int]]) -> None:
    app = create_app()
    with app.app_context():
        service = get_generation_service()
        for app_num, template_id in entries:
            print(f"\n=== Generating {model_slug}/app{app_num} (template {template_id}) ===")
            result = await service.generate_full_app(
                model_slug=model_slug,
                app_num=app_num,
                template_id=template_id,
                generate_frontend=True,
                generate_backend=True,
            )
            print(result)


def parse_entries(raw: str) -> Iterable[Tuple[int, int]]:
    parts = []
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        if ':' in item:
            app_part, template_part = item.split(':', 1)
            parts.append((int(app_part), int(template_part)))
        else:
            num = int(item)
            parts.append((num, num))
    return parts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample apps for a model")
    parser.add_argument('--model', required=True, help='Canonical model slug, e.g. x-ai_grok-code-fast-1')
    parser.add_argument('--entries', default='1:1,2:2,3:3', help='Comma-separated app_num:template_id pairs')
    args = parser.parse_args()

    entries = list(parse_entries(args.entries))
    asyncio.run(generate_apps(args.model, entries))


if __name__ == '__main__':
    main()
