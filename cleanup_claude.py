import base64
import os
import sys

import httpx

REPO = "agwuh1234-bot/AtlasCore"
MARKER = 'async def claude_ask(prompt):'


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    branch = os.environ.get("GITHUB_BRANCH", "main")
    url = f"https://api.github.com/repos/{REPO}/contents/main.py"
    headers = github_headers(token)

    with httpx.Client(timeout=30.0) as client:
        current = client.get(url, headers=headers, params={"ref": branch})
        current.raise_for_status()
        data = current.json()

        content = base64.b64decode(data["content"]).decode("utf-8")
        positions = []
        idx = 0
        while True:
            idx = content.find(MARKER, idx)
            if idx == -1:
                break
            positions.append(idx)
            idx += 1

        if len(positions) != 4:
            raise RuntimeError("unexpected_claude_count")

        first = positions[0]
        last = positions[-1]
        new_content = content[:first] + content[last:]

        if new_content.count(MARKER) != 1:
            raise RuntimeError("unexpected_claude_count")
        if 'async def run_atlas' not in new_content:
            raise RuntimeError("missing_run_atlas")
        if '@api.post("/bridge")' not in new_content:
            raise RuntimeError("missing_bridge")
        if '@api.post("/app-jobs")' not in new_content:
            raise RuntimeError("missing_app_jobs")
        if len(new_content.splitlines()) <= 1300:
            raise RuntimeError("unexpected_line_count")

        payload = {
            "message": "Remove duplicate Claude functions",
            "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
            "branch": branch,
            "sha": data["sha"],
        }
        updated = client.put(url, headers=headers, json=payload)
        updated.raise_for_status()
        result = updated.json()

    print(result.get("commit", {}).get("sha", ""))
    print("CLEANUP_OK")


if __name__ == "__main__":
    main()
