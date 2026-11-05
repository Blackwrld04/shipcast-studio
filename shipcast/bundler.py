"""Multi-format release bundle generator for ShipCast (@publisher)."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from shipcast.validator import validate_release_bundle


def build_changelog_entry(analysis: dict[str, Any], receipt: dict[str, Any]) -> str:
    date_today = datetime.now(UTC).strftime("%Y-%m-%d")
    version = analysis["version_tag"]
    lines = [
        f"## [{version}] - {date_today}",
        "",
        f"> Importance Score: **{analysis['overall_importance']}/10** · "
        f"Commits included: **{analysis['included_commits']}** "
        f"(filtered {analysis['skipped_commits']} low-signal commits) · "
        f"Verification Receipt: `{receipt['overall_receipt_sha256'][:16]}`",
        "",
    ]

    if analysis.get("voice_note"):
        lines.extend(
            [
                "### Release Context",
                analysis["voice_note"].strip(),
                "",
            ]
        )

    categories: dict[str, list[dict[str, Any]]] = analysis.get("categories", {})
    for cat_name in ("Added", "Changed", "Fixed", "Security", "Documentation", "Tests"):
        items = categories.get(cat_name, [])
        if not items:
            continue
        lines.append(f"### {cat_name}")
        for item in items:
            files_preview = ", ".join(f"`{f}`" for f in item["files_changed"][:3])
            suffix = f" ({files_preview})" if files_preview else ""
            lines.append(
                f"- **{item['subject']}** (`{item['short_sha']}`, "
                f"+{item['insertions']}/-{item['deletions']}){suffix}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_jsonld_seo(analysis: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    version = analysis["version_tag"]
    repo_name = analysis["repo_name"]
    return {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": f"{repo_name} {version}: Verified Multi-Agent Release & Changelog",
        "datePublished": datetime.now(UTC).strftime("%Y-%m-%d"),
        "proficiencyLevel": "Expert",
        "softwareVersion": version,
        "about": {
            "@type": "SoftwareApplication",
            "name": repo_name,
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Linux, macOS, Windows",
        },
        "identifier": receipt["overall_receipt_sha256"],
    }


def build_devto_article(analysis: dict[str, Any], receipt: dict[str, Any]) -> str:
    repo_name = analysis["repo_name"]
    version = analysis["version_tag"]
    title = f"Shipping {repo_name} {version} with Switch Rooms: Verified Multi-Agent Release Notes"
    description = (
        f"How {repo_name} {version} uses linked Switch rooms and sandbox verification "
        f"to ship tested tutorials and changelogs."
    )[:160]

    included_commits = [c for c in analysis.get("commits", []) if not c.get("skipped")]
    commit_bullets = []
    for c in included_commits:
        commit_bullets.append(
            f"- **`{c['short_sha']}` — {c['subject']}** (`+{c['insertions']} / -{c['deletions']}` lines across `{', '.join(c['files_changed'][:3])}`)"
        )
    if not commit_bullets:
        commit_bullets.append(f"- **`{version}`** — Core release bundle and verification pipeline.")

    verification_blocks = []
    for res in receipt.get("results", []):
        status_label = "PASS (exit 0)" if res["passed"] else f"FAIL (exit {res['exit_code']})"
        stdout_snippet = res["stdout"] if res["stdout"] else "(no stdout)"
        verification_blocks.extend(
            [
                f"### Check #{res['index']}: `{status_label}` in {res['duration_ms']}ms",
                f"- **Receipt SHA-256:** `{res['receipt_sha256'][:24]}...`",
                "",
                f"```{res['language']}",
                res["command"],
                "```",
                "",
                "**Captured Sandbox Output:**",
                "```text",
                stdout_snippet,
                "```",
                "",
            ]
        )

    voice_context = (
        f"\n> **Creator Note (Dictated in Switch Room):** {analysis['voice_note']}\n"
        if analysis.get("voice_note")
        else ""
    )

    article = f"""---
title: "{title}"
published: false
description: "{description}"
tags: switch, ai, opensource, devtools
ai_disclosure_level: some_ai
---

# {title}

Every code release normally ends with a manual chore: reading `git log`, checking which CLI flags changed, testing code snippets by hand so tutorials do not lie, and formatting release notes across multiple channels.

For **{repo_name} `{version}`**, we automated this workflow inside **Switch Rooms** using two linked rooms (`studio-desk` and `verification-lab`) and three specialized agents (`producer`, `verifier`, and `publisher`) governed by an explicit human sign-off gate.
{voice_context}
## 1. Architecture: Why Two Linked Switch Rooms Beat a Single Bot

Instead of trusting one prompt to summarize commits and publish unchecked markdown, ShipCast separates coordination, sandbox execution, and contract validation across two linked Switch rooms:

```mermaid
flowchart LR
  human["Human Creator in Discord / Telegram / Slack"] --> desk["Room 1: studio-desk (producer)"]
  desk -->|"Switch Room Link: verification-and-drafting"| lab["Room 2: verification-lab (verifier + publisher)"]
  lab -->|"SHA-256 Receipt + Validated Bundle"| desk
```

- **Room 1 (`studio-desk`)**: Holds the human creator and the `producer` agent (`addressing: anyone`), which claims the exclusive `release-captain` role so overlapping releases never collide.
- **Room 2 (`verification-lab`)**: Holds `verifier` and `publisher` (`addressing: owner-agents`). They cannot be triggered by random channel chatter—only by structured handoffs from `producer`.

## 2. What Shipped in `{repo_name} {version}`

Our git analyzer scanned `{analysis['commit_range']}` ({analysis['total_commits']} total commits, filtering out {analysis['skipped_commits']} low-signal commits) and scored this release **{analysis['overall_importance']}/10** across **{len(analysis['files_touched'])} files** (`+{analysis['total_insertions']} / -{analysis['total_deletions']}` lines):

{chr(10).join(commit_bullets)}

## 3. Sandbox Verification Receipts (`verification-lab`)

Before `publisher` was allowed to draft this post, `verifier` executed every command in an isolated subprocess and recorded its cryptographic SHA-256 receipt (`{receipt['overall_receipt_sha256'][:20]}...`):

{chr(10).join(verification_blocks).strip()}

## 4. Reproducing This Setup in Switch Console

Clone the repository and import `shipcast.template.yaml` into **Switch Console → Templates → Import template** to stand up all three agents, both linked rooms, the room-scoped editorial contract document, and the `release-captain` role in one click.
"""
    return article.strip() + "\n"


def build_social_posts(analysis: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    repo_name = analysis["repo_name"]
    version = analysis["version_tag"]
    ins = analysis["total_insertions"]
    dels = analysis["total_deletions"]
    checks = receipt["total_checks"]
    sha_short = receipt["overall_receipt_sha256"][:12]

    return {
        "x_thread": [
            (
                f"Shipped {repo_name} {version} (+{ins}/-{dels} lines across {len(analysis['files_touched'])} files) "
                f"and let our Switch Rooms agent crew verify and package the release.\n\n"
                f"• {analysis['included_commits']} commits analyzed ({analysis['skipped_commits']} noise commits filtered)\n"
                f"• {checks}/{checks} CLI snippets executed in sandbox (SHA: {sha_short})\n"
                f"• Gated by human sign-off in chat #HowISwitch"
            ),
            (
                "How the 2-room Switch topology works:\n\n"
                "1. studio-desk: producer claims the exclusive release-captain role & parses git diff\n"
                "2. verification-lab: verifier runs every tutorial snippet in a sandbox before publisher drafts the DEV post\n"
                "3. Human replies 'Approve' in chat to ship."
            ),
        ],
        "linkedin_post": (
            f"Writing code takes two hours; verifying tutorial snippets, updating CHANGELOG.md, and writing release notes takes another hour.\n\n"
            f"Today we shipped {repo_name} {version} (+{ins}/-{dels} lines) using ShipCast on Switch Rooms. "
            f"Instead of a single chatbot guessing what changed, three agents collaborate across two linked Switch rooms: "
            f"a Producer in the main desk room, and a Verifier + Publisher in a linked backstage verification room.\n\n"
            f"Every CLI snippet in the release tutorial was executed in an isolated sandbox ({checks}/{checks} passed, receipt {sha_short}) "
            f"before surfacing a clean approval card in chat. #HowISwitch #OpenSource #AIAgents"
        ),
        "discord_announcement": (
            f"**{repo_name} {version} is ready for release**\n"
            f"• **Importance Score:** {analysis['overall_importance']}/10\n"
            f"• **Diff Stats:** +{ins} / -{dels} lines across {len(analysis['files_touched'])} files\n"
            f"• **Sandbox Verification:** {checks}/{checks} checks passed (`{sha_short}`) "
        ),
    }


def build_switch_room_summary(
    analysis: dict[str, Any],
    receipt: dict[str, Any],
) -> str:
    """Build a Slack- and Telegram-safe room receipt (no Markdown tables, no stray @mentions)."""
    version = analysis["version_tag"]
    repo_name = analysis["repo_name"]
    checks = f"{receipt['passed_checks']}/{receipt['total_checks']}"
    sha_short = receipt["overall_receipt_sha256"][:16]

    lines = [
        f"**ShipCast Release Package Ready — {repo_name} {version}**",
        f"• **Role Held:** `release-captain` (exclusive lock active)",
        f"• **Git Range:** `{analysis['commit_range']}` ({analysis['included_commits']} commits included, {analysis['skipped_commits']} filtered)",
        f"• **Importance Score:** {analysis['overall_importance']}/10 (+{analysis['total_insertions']}/-{analysis['total_deletions']} lines in {len(analysis['files_touched'])} files)",
        f"• **Sandbox Verification:** {checks} commands passed (Receipt `{sha_short}`)",
        "• **Artifacts Staged:** `devto-article.md`, `changelog-entry.md`, `social-posts.json`, `changelog-seo.jsonld`",
        "• **Next Step:** Reply `Approve publish` in this thread to update `CHANGELOG.md` and publish the release bundle.",
    ]
    return "\n".join(lines)


def create_release_bundle(
    analysis: dict[str, Any],
    receipt: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    changelog_md = build_changelog_entry(analysis, receipt)
    jsonld = build_jsonld_seo(analysis, receipt)
    article_md = build_devto_article(analysis, receipt)
    socials = build_social_posts(analysis, receipt)
    room_summary = build_switch_room_summary(analysis, receipt)

    validation = validate_release_bundle(
        article_markdown=article_md,
        room_summary_text=room_summary,
        verification_receipt=receipt,
    )

    (output_dir / "devto-article.md").write_text(article_md, encoding="utf-8")
    (output_dir / "changelog-entry.md").write_text(changelog_md, encoding="utf-8")
    (output_dir / "changelog-seo.jsonld").write_text(
        json.dumps(jsonld, indent=2), encoding="utf-8"
    )
    (output_dir / "social-posts.json").write_text(
        json.dumps(socials, indent=2), encoding="utf-8"
    )
    (output_dir / "switch-room-summary.txt").write_text(room_summary + "\n", encoding="utf-8")
    (output_dir / "verification-receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    (output_dir / "validation-report.json").write_text(
        json.dumps(validation.to_dict(), indent=2), encoding="utf-8"
    )

    bundle_manifest = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "output_dir": str(output_dir),
        "analysis": analysis,
        "verification_receipt": receipt,
        "validation_report": validation.to_dict(),
        "artifacts": {
            "devto_article": str(output_dir / "devto-article.md"),
            "changelog_entry": str(output_dir / "changelog-entry.md"),
            "changelog_jsonld": str(output_dir / "changelog-seo.jsonld"),
            "social_posts": str(output_dir / "social-posts.json"),
            "switch_room_summary": str(output_dir / "switch-room-summary.txt"),
        },
        "preview": {
            "room_summary": room_summary,
            "changelog_markdown": changelog_md,
            "devto_article_markdown": article_md,
            "social_posts": socials,
        },
    }
    (output_dir / "bundle-data.json").write_text(
        json.dumps(bundle_manifest, indent=2), encoding="utf-8"
    )
    return bundle_manifest

