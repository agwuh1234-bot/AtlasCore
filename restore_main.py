import os
import base64
import httpx

REPO = "agwuh1234-bot/AtlasCore"
TARGET_PATH = "main.py"
SOURCE_REF = "a6fe2aab0aed209c1bd523d80b23eb3bf289407b"
MESSAGE = "Restore main.py from known good commit"


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _check_status(response: httpx.Response, ok_statuses: tuple[int, ...]) -> None:
    if response.status_code not in ok_statuses:
        raise RuntimeError(f"HTTP {response.status_code}")


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    branch = os.environ.get("GITHUB_BRANCH", "main")

    client = httpx.Client(timeout=30.0)
    headers = _auth_headers(token)

    source_url = f"https://api.github.com/repos/{REPO}/contents/{TARGET_PATH}?ref={SOURCE_REF}"
    source_resp = client.get(source_url, headers=headers)
    _check_status(source_resp, (200,))
    source_data = source_resp.json()
    source_content = source_data["content"].replace("\n", "")
    restored_bytes = base64.b64decode(source_content)
    restored_content = restored_bytes.decode("utf-8")

    current_url = f"https://api.github.com/repos/{REPO}/contents/{TARGET_PATH}?ref={branch}"
    current_resp = client.get(current_url, headers=headers)
    _check_status(current_resp, (200,))
    current_data = current_resp.json()
    current_sha = current_data["sha"]

    put_url = f"https://api.github.com/repos/{REPO}/contents/{TARGET_PATH}"
    put_payload = {
        "message": MESSAGE,
        "content": base64.b64encode(restored_content.encode("utf-8")).decode("ascii"),
        "branch": branch,
        "sha": current_sha,
    }
    put_resp = client.put(put_url, headers=headers, json=put_payload)
    _check_status(put_resp, (200, 201))

    print("RESTORE_OK")


if __name__ == "__main__":
    main()
