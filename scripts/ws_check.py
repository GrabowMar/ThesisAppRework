import json
import sys
import time
from urllib import request, error

BASE = "http://127.0.0.1:5000/api/websocket"

def get_json(url: str):
    with request.urlopen(url) as r:
        return json.loads(r.read().decode())


def post_json(url: str, data: dict):
    body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with request.urlopen(req) as r:
        return json.loads(r.read().decode())


def main() -> int:
    try:
        status = get_json(f"{BASE}/status")
        print("STATUS:", json.dumps(status, indent=2))
    except Exception as e:
        print("STATUS_ERR:", e)
        return 2

    try:
        cleared = post_json(f"{BASE}/events/clear", {})
        print("CLEARED:", json.dumps(cleared, indent=2))
    except Exception as e:
        print("CLEAR_ERR:", e)
        return 2

    payload = {
        "analysis_type": "security",
        "model_slug": "anthropic_claude-3.7-sonnet",
        "app_number": 1,
    }
    try:
        start = post_json(f"{BASE}/analysis/start", payload)
        print("START:", json.dumps(start, indent=2))
    except Exception as e:
        print("START_ERR:", e)
        return 2

    # Poll events for up to 90 seconds
    deadline = time.time() + 90
    last_types = []
    while time.time() < deadline:
        try:
            resp = get_json(f"{BASE}/events")
            # API returns { status, events: [...] }
            events = []
            if isinstance(resp, dict):
                events = resp.get("events", []) or []
            elif isinstance(resp, list):
                # Back-compat if endpoint ever returned a list directly
                events = resp
            # Each event entry uses key 'event' for the name/type
            types = [ (e.get("event") if isinstance(e, dict) else None) for e in events ]
            last_types = types
            tail = types[-5:] if len(types) > 5 else types
            print("EVENT_TYPES:", ", ".join([str(t) for t in tail]))
            if "analysis_completed" in types or "analysis_failed" in types:
                break
        except error.HTTPError as he:
            print("EVENTS_HTTP_ERR:", he.code)
        except Exception as e:
            print("EVENTS_ERR:", e)
        time.sleep(3)

    print("FINAL_TYPES:", json.dumps(last_types, indent=2))

    try:
        analyses = get_json(f"{BASE}/analyses")
        print("ANALYSES:", json.dumps(analyses, indent=2))
    except Exception as e:
        print("ANALYSES_ERR:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
