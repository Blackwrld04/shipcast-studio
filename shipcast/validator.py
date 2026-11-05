"""Deterministic editorial & Switch room contract validator for ShipCast."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

BANNED_BUZZWORDS = (
    "unleash",
    "supercharge",
    "revolutionize",
    "next-generation",
    "all-in-one",
    "game-changing",
    "seamlessly",
)


@dataclass
class ContractFinding:
    rule_id: str
    passed: bool
    message: str


@dataclass
class ContractValidationReport:
    valid: bool
    passed_count: int
    failed_count: int
    findings: list[dict[str, Any]]
    retry_prompt_feedback: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_frontmatter(markdown_text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", markdown_text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            fields[key.strip()] = val.strip().strip('"').strip("'")
    return fields


def validate_release_bundle(
    article_markdown: str,
    room_summary_text: str,
    verification_receipt: dict[str, Any],
) -> ContractValidationReport:
    """Validate article markdown, room summary, and verification receipt against strict contract."""
    findings: list[ContractFinding] = []
    fm = _parse_frontmatter(article_markdown)

    # Rule 1: Required frontmatter fields
    has_required_fm = bool(fm.get("title") and fm.get("description") and fm.get("tags"))
    findings.append(
        ContractFinding(
            rule_id="frontmatter.required_fields",
            passed=has_required_fm,
            message=(
                "Frontmatter includes title, description, and tags."
                if has_required_fm
                else "Missing required frontmatter fields (title, description, tags)."
            ),
        )
    )

    # Rule 2: Summary / description <= 160 characters
    desc = fm.get("description", "")
    desc_ok = 10 <= len(desc) <= 160
    findings.append(
        ContractFinding(
            rule_id="frontmatter.description_length",
            passed=desc_ok,
            message=(
                f"Description length is {len(desc)}/160 chars."
                if desc_ok
                else f"Description length ({len(desc)}) must be between 10 and 160 characters."
            ),
        )
    )

    # Rule 3: Title matches first H1 heading in body
    body_after_fm = re.sub(r"^---\n.*?\n---\n", "", article_markdown, flags=re.DOTALL).strip()
    h1_match = re.search(r"^#\s+(.+)$", body_after_fm, re.MULTILINE)
    first_h1 = h1_match.group(1).strip() if h1_match else ""
    title_matches = bool(fm.get("title") and first_h1 == fm.get("title"))
    findings.append(
        ContractFinding(
            rule_id="markdown.title_matches_h1",
            passed=title_matches,
            message=(
                "Frontmatter title matches first '# ' heading."
                if title_matches
                else f"Frontmatter title ({fm.get('title')!r}) does not match first H1 ({first_h1!r})."
            ),
        )
    )

    # Rule 4: Verification receipt passed all checks
    receipt_ok = bool(
        verification_receipt.get("all_passed") is True
        and int(verification_receipt.get("total_checks", 0)) >= 1
        and verification_receipt.get("overall_receipt_sha256")
    )
    findings.append(
        ContractFinding(
            rule_id="verification.all_snippets_passed",
            passed=receipt_ok,
            message=(
                f"All {verification_receipt.get('total_checks', 0)} sandbox checks passed "
                f"(SHA-256: {str(verification_receipt.get('overall_receipt_sha256', ''))[:12]}...)."
                if receipt_ok
                else "Verification receipt is missing or has failing command checks."
            ),
        )
    )

    # Rule 5: Anti-slop copy check
    lower_body = body_after_fm.lower()
    found_buzzwords = [w for w in BANNED_BUZZWORDS if re.search(rf"\b{re.escape(w)}\b", lower_body)]
    no_slop = len(found_buzzwords) == 0
    findings.append(
        ContractFinding(
            rule_id="editorial.no_banned_buzzwords",
            passed=no_slop,
            message=(
                "Zero banned marketing buzzwords detected."
                if no_slop
                else f"Draft contains banned filler words: {', '.join(found_buzzwords)}."
            ),
        )
    )

    # Rule 6: Switch GOTCHAS.md compliance — no Markdown tables in Slack/Telegram room summary
    has_raw_table = bool(re.search(r"^\s*\|.*\|\s*$", room_summary_text, re.MULTILINE))
    findings.append(
        ContractFinding(
            rule_id="switch.slack_telegram_safe_summary",
            passed=not has_raw_table,
            message=(
                "Switch room summary uses Slack/Telegram-safe bolded bullet lines (no raw tables)."
                if not has_raw_table
                else "Switch room summary contains raw Markdown table pipes ('|'), which break in Slack and Telegram."
            ),
        )
    )

    # Rule 7: Switch GOTCHAS.md compliance — no accidental @agent mentions inside summary body
    stray_mentions = re.findall(r"@(?!creator\b)[a-zA-Z0-9_-]+", room_summary_text)
    no_stray_mentions = len(stray_mentions) == 0
    findings.append(
        ContractFinding(
            rule_id="switch.no_accidental_agent_mentions",
            passed=no_stray_mentions,
            message=(
                "No accidental '@agent' mentions inside free-text summary body."
                if no_stray_mentions
                else f"Summary contains literal mentions {stray_mentions} that will wake unintended sessions."
            ),
        )
    )

    failed = [f for f in findings if not f.passed]
    passed = [f for f in findings if f.passed]
    feedback = (
        ""
        if not failed
        else "Your draft was rejected by shipcast-editorial-contract for: "
        + "; ".join(f"[{f.rule_id}] {f.message}" for f in failed)
    )

    return ContractValidationReport(
        valid=len(failed) == 0,
        passed_count=len(passed),
        failed_count=len(failed),
        findings=[asdict(f) for f in findings],
        retry_prompt_feedback=feedback,
    )

