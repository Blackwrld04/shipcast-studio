"""Human-gated release publisher for ShipCast."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


def update_changelog_file(changelog_path: Path, entry_markdown: str, version_tag: str) -> bool:
    """Idempotently prepend a release entry to CHANGELOG.md (returns False if already present)."""
    header = "# Changelog\n\nAll notable changes to this project are documented in this file.\n\n"
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        if f"## [{version_tag}]" in existing:
            return False
        if existing.startswith("# Changelog"):
            parts = existing.split("\n\n", 2)
            if len(parts) >= 2:
                prefix = "\n\n".join(parts[:2]) + "\n\n"
                rest = parts[2] if len(parts) > 2 else ""
                changelog_path.write_text(
                    prefix + entry_markdown.strip() + "\n\n" + rest,
                    encoding="utf-8",
                )
                return True
        changelog_path.write_text(
            header + entry_markdown.strip() + "\n\n" + existing,
            encoding="utf-8",
        )
        return True

    changelog_path.write_text(header + entry_markdown.strip() + "\n", encoding="utf-8")
    return True


def publish_release_bundle(
    bundle_dir: Path,
    repo_path: Path,
    approved_by: str,
    approval_message: str = "Approve publish",
    publish_devto: bool = False,
) -> dict[str, Any]:
    """Execute the human-approved release publication after verifying contract & receipt."""
    if not approved_by or not approved_by.strip():
        raise PermissionError(
            "Refusing to publish without an explicit human approver (--approved-by)."
        )

    normalized_msg = approval_message.strip().lower()
    if not any(word in normalized_msg for word in ("approve", "approved", "ship", "lgtm", "yes")):
        raise PermissionError(
            f"Approval message {approval_message!r} does not contain an explicit approval keyword."
        )

    bundle_json_path = bundle_dir / "bundle-data.json"
    if not bundle_json_path.exists():
        raise FileNotFoundError(f"Missing bundle-data.json in {bundle_dir}")

    bundle_data = json.loads(bundle_json_path.read_text(encoding="utf-8"))
    validation = bundle_data.get("validation_report", {})
    if not validation.get("valid"):
        raise RuntimeError(
            f"Refusing to publish invalid bundle: {validation.get('retry_prompt_feedback')}"
        )

    receipt = bundle_data.get("verification_receipt", {})
    if not receipt.get("all_passed"):
        raise RuntimeError("Refusing to publish bundle with failing sandbox verification checks.")

    version_tag = bundle_data["analysis"]["version_tag"]
    changelog_entry = (bundle_dir / "changelog-entry.md").read_text(encoding="utf-8")
    changelog_path = repo_path.resolve() / "CHANGELOG.md"
    changelog_updated = update_changelog_file(changelog_path, changelog_entry, version_tag)

    devto_result: dict[str, Any] = {"status": "staged_locally"}
    api_key = os.environ.get("DEVTO_API_KEY", "").strip()
    if publish_devto and api_key:
        article_md = (bundle_dir / "devto-article.md").read_text(encoding="utf-8")
        payload = json.dumps({"article": {"body_markdown": article_md}}).encode("utf-8")
        req = urllib.request.Request(
            "https://dev.to/api/articles",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "api-key": api_key,
                "User-Agent": "ShipCast-SwitchRooms/0.2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
                devto_result = {
                    "status": "published_draft",
                    "id": resp_body.get("id"),
                    "url": resp_body.get("url"),
                }
        except urllib.error.URLError as exc:
            devto_result = {"status": "error", "detail": str(exc)}

    approval_sig = hashlib.sha256(
        f"{version_tag}|{approved_by.strip()}|{approval_message.strip()}|{receipt['overall_receipt_sha256']}".encode()
    ).hexdigest()

    pub_receipt = {
        "published_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version_tag": version_tag,
        "approved_by": approved_by.strip(),
        "approval_message": approval_message.strip(),
        "approval_signature_sha256": approval_sig,
        "verification_receipt_sha256": receipt["overall_receipt_sha256"],
        "changelog_path": str(changelog_path),
        "changelog_updated": changelog_updated,
        "devto": devto_result,
    }
    (bundle_dir / "publication-receipt.json").write_text(
        json.dumps(pub_receipt, indent=2), encoding="utf-8"
    )
    return pub_receipt
