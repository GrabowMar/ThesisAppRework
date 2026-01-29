import json
import glob
import os

def verify():
    path = "generated/raw/responses/qwen_qwen3-coder-30b-a3b-instruct/app17/*.json"
    files = glob.glob(path)
    if not files:
        print(f"No files found in {path}")
        return

    for f in files:
        print(f"\n--- File: {f} ---")
        try:
            with open(f, 'r', encoding='utf-8') as j:
                data = json.load(j)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"Length: {len(content)} characters")
                print("First 200 chars:")
                print(content[:200])
                print("\nLast 200 chars:")
                print(content[-200:])
                
                # Check for specific variety markers
                if "IMPORTANT" in content:
                    print("Found 'IMPORTANT' marker (indicates new prompt used)")
                if "Unique Visual Identity" in content:
                    print("Found 'Unique Visual Identity' marker")
                
        except Exception as e:
            print(f"Error reading {f}: {e}")

if __name__ == "__main__":
    verify()
