from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def generate_vapid_config() -> dict[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    numbers = private_key.public_key().public_numbers()
    public_bytes = (
        b"\x04"
        + numbers.x.to_bytes(32, "big")
        + numbers.y.to_bytes(32, "big")
    )
    return {
        "private_key": _b64url(private_der),
        "public_key": _b64url(public_bytes),
    }


class PushService:
    def __init__(self, store: Any) -> None:
        self.store = store
        self._config: dict[str, str] | None = None

    def ensure_config(self) -> dict[str, str]:
        if self._config:
            return self._config
        generated = json.dumps(generate_vapid_config(), separators=(",", ":"))
        stored = self.store.get_or_create_secret("web-push-vapid-v1", generated)
        data = json.loads(stored)
        if not data.get("private_key") or not data.get("public_key"):
            raise RuntimeError("Invalid VAPID configuration")
        self._config = {
            "private_key": str(data["private_key"]),
            "public_key": str(data["public_key"]),
        }
        return self._config

    def public_status(self) -> dict[str, Any]:
        config = self.ensure_config()
        return {
            "enabled": True,
            "public_key": config["public_key"],
            "subscriptions": self.store.push_subscription_count(),
        }

    def subscribe(
        self,
        subscription: dict[str, Any],
        user_agent: str = "",
    ) -> dict[str, Any]:
        endpoint = str(subscription.get("endpoint") or "")
        keys = subscription.get("keys") or {}
        return self.store.upsert_push_subscription(
            endpoint=endpoint,
            p256dh=str(keys.get("p256dh") or ""),
            auth=str(keys.get("auth") or ""),
            user_agent=user_agent,
        )

    def unsubscribe(self, endpoint: str) -> bool:
        return self.store.delete_push_subscription(endpoint)

    def send_completion(
        self,
        *,
        job_id: str,
        project_id: str,
        title: str = "Atlas",
        body: str = "Задача выполнена",
    ) -> dict[str, int]:
        config = self.ensure_config()
        payload = json.dumps(
            {
                "title": title,
                "body": body[:180],
                "tag": "atlas-job-" + job_id,
                "url": "/?job=" + job_id,
                "project_id": project_id,
            },
            ensure_ascii=False,
        )
        subject = os.environ.get(
            "ATLAS_VAPID_SUBJECT",
            "https://atlascore-production.up.railway.app",
        )
        sent = 0
        failed = 0
        disabled = 0
        for subscription in self.store.list_push_subscriptions():
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription["endpoint"],
                        "keys": {
                            "p256dh": subscription["p256dh"],
                            "auth": subscription["auth"],
                        },
                    },
                    data=payload,
                    vapid_private_key=config["private_key"],
                    vapid_claims={"sub": subject},
                    ttl=24 * 3600,
                    timeout=15,
                )
                sent += 1
            except WebPushException as exc:
                failed += 1
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in {404, 410}:
                    self.store.disable_push_subscription(
                        subscription["id"], f"expired:{status}"
                    )
                    disabled += 1
            except Exception:
                failed += 1
        return {"sent": sent, "failed": failed, "disabled": disabled}
