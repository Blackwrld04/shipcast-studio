"""End-to-end unit and integration tests for ShipCast Studio."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from shipcast.analyzer import analyze_repository, categorize_commit, score_commit
from shipcast.bundler import create_release_bundle
from shipcast.publisher import publish_release_bundle, update_changelog_file
from shipcast.validator import validate_release_bundle
from shipcast.verifier import extract_fenced_commands, verify_commands


def test_commit_scoring_filters_noise_and_skip_markers() -> None:
    cat = categorize_commit("feat: add two-room Switch link handoff", ["shipcast/cli.py"])
    assert cat == "Added"
    score, skipped, _ = score_commit(
        "feat: add two-room Switch link handoff",
        cat,
        ["shipcast/cli.py", "shipcast/verifier.py", "shipcast.template.yaml"],
        140,
        10,
    )
    assert not skipped
    assert score >= 8

    # Lockfile-only commit should be skipped
    _, skipped_lock, reason_lock = score_commit(
        "chore: update lockfile",
        "Chore",
        ["uv.lock", "package-lock.json"],
        500,
        400,
    )
    assert skipped_lock
    assert "lockfile" in reason_lock.lower()

    # [skip-post] commit should be skipped
    _, skipped_marker, _ = score_commit(
        "feat: internal experiment [skip-post]",
        "Added",
        ["shipcast/cli.py"],
        50,
        5,
    )
    assert skipped_marker


def test_sandbox_verifier_executes_and_blocks_unsafe_commands(tmp_path: Path) -> None:
    md = """
Here is a valid snippet:
```python
print("verified-from-sandbox", 2 + 2)
```
"""
    cmds = extract_fenced_commands(md)
    assert len(cmds) == 1
    receipt = verify_commands(cmds, working_dir=tmp_path, version_tag="v0.2.0")
    assert receipt.all_passed is True
    assert receipt.passed_checks == 1
    assert "verified-from-sandbox 4" in receipt.results[0]["stdout"]
    assert len(receipt.overall_receipt_sha256) == 64

    # Unsafe command must be blocked without running
    blocked_receipt = verify_commands(
        [("bash", "sudo rm -rf /")],
        working_dir=tmp_path,
        version_tag="v0.2.0",
    )
    assert blocked_receipt.all_passed is False
    assert blocked_receipt.results[0]["exit_code"] == 126
    assert "Blocked by safety policy" in blocked_receipt.results[0]["stderr"]


def test_editorial_contract_validator_enforces_all_seven_rules(tmp_path: Path) -> None:
    receipt = verify_commands(
        [("python", "print('ok')")],
        working_dir=tmp_path,
        version_tag="v0.2.0",
    ).to_dict()

    good_article = """---
title: "Shipping ShipCast v0.2.0 with Switch Rooms"
published: false
description: "How ShipCast uses two linked Switch rooms and sandbox verification to ship tested release notes."
tags: switch, ai, opensource, devtools
ai_disclosure_level: some_ai
---

# Shipping ShipCast v0.2.0 with Switch Rooms

Concrete body text with zero filler words.
"""
    good_summary = (
        "**ShipCast Release Ready**\n"
        "• **Role Held:** `release-captain`\n"
        "• **Sandbox Verification:** 1/1 passed"
    )

    report = validate_release_bundle(good_article, good_summary, receipt)
    assert report.valid is True
    assert report.passed_count == 7
    assert report.failed_count == 0

    # Test rejection when Markdown table or accidental @agent mention is present in room summary
    bad_summary = "| Col | Val |\n|---|---|\nPing @verifier in summary"
    bad_report = validate_release_bundle(good_article, bad_summary, receipt)
    assert bad_report.valid is False
    failed_ids = {f["rule_id"] for f in bad_report.findings if not f["passed"]}
    assert "switch.slack_telegram_safe_summary" in failed_ids
    assert "switch.no_accidental_agent_mentions" in failed_ids


def test_end_to_end_git_repo_pipeline_and_human_approval_gate(tmp_path: Path) -> None:
    repo = tmp_path / "demo-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Demo Builder"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=repo, check=True)

    (repo / "app.py").write_text("print('hello v0.1.0')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "feat: initial release engine"], cwd=repo, check=True)

    (repo / "app.py").write_text("print('hello v0.2.0')\n", encoding="utf-8")
    (repo / "verifier.py").write_text("def check():\n    return True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add linked room verification and SHA-256 receipts"],
        cwd=repo,
        check=True,
    )

    analysis = analyze_repository(
        repo_path=repo,
        commit_range="HEAD~1..HEAD",
        version_tag="v0.2.0",
        voice_note="Dictated via Wispr Flow: Emphasize the backstage verification room.",
    )
    assert analysis.included_commits == 1
    assert analysis.overall_importance >= 7

    receipt = verify_commands(
        [("python", "print('sandbox check ok')")],
        working_dir=repo,
        version_tag="v0.2.0",
    )
    assert receipt.all_passed is True

    bundle_dir = repo / "dist" / "v0.2.0"
    bundle = create_release_bundle(analysis.to_dict(), receipt.to_dict(), bundle_dir)
    assert bundle["validation_report"]["valid"] is True

    # Publishing must refuse without valid approval keyword
    with pytest.raises(PermissionError):
        publish_release_bundle(
            bundle_dir=bundle_dir,
            repo_path=repo,
            approved_by="creator",
            approval_message="Hold on, do not publish yet",
        )

    pub_receipt = publish_release_bundle(
        bundle_dir=bundle_dir,
        repo_path=repo,
        approved_by="creator",
        approval_message="Approved. Ship it!",
    )
    assert pub_receipt["changelog_updated"] is True
    assert (repo / "CHANGELOG.md").exists()
    assert "## [v0.2.0]" in (repo / "CHANGELOG.md").read_text(encoding="utf-8")

    # Second call for same version must be idempotent
    assert update_changelog_file(repo / "CHANGELOG.md", "## [v0.2.0]\n", "v0.2.0") is False


def test_switch_templates_contain_required_primitives() -> None:
    root = Path(__file__).resolve().parent.parent
    v1_text = (root / "shipcast.template.yaml").read_text(encoding="utf-8")
    assert "version: 1" in v1_text
    assert "release-captain" in v1_text
    assert "snippet-auditor" in v1_text
    assert "shipcast-editorial-contract" in v1_text
    assert "verification-and-drafting" in v1_text
    assert "addressing: owner-agents" in v1_text
    assert "allow_existing: true" in v1_text
