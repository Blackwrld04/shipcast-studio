"""Sandbox command and markdown code-snippet verifier for ShipCast (@verifier)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

FORBIDDEN_PATTERNS = (
    r"\brm\s+-rf\s+/",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{",
    r"\bshutdown\b",
    r"\breboot\b",
)


@dataclass
class SnippetCheckResult:
    index: int
    language: str
    command: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    receipt_sha256: str


@dataclass
class VerificationReceipt:
    repo_path: str
    version_tag: str
    verified_at: str
    all_passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    overall_receipt_sha256: str
    results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_fenced_commands(markdown_text: str) -> list[tuple[str, str]]:
    """Extract runnable bash/sh/python blocks from markdown text."""
    pattern = re.compile(r"```(bash|sh|python)\s*\n(.*?)```", re.DOTALL)
    extracted: list[tuple[str, str]] = []
    for match in pattern.finditer(markdown_text):
        lang = match.group(1).strip().lower()
        code = match.group(2).strip()
        if code:
            extracted.append((lang, code))
    return extracted


def _is_safe_command(code: str) -> tuple[bool, str]:
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, code):
            return False, f"Blocked by safety policy matching pattern: {pat}"
    return True, ""


def verify_commands(
    commands: list[tuple[str, str]],
    working_dir: Path,
    version_tag: str = "v0.2.0",
    timeout_seconds: float = 15.0,
) -> VerificationReceipt:
    """Run each command or snippet in a controlled subprocess and generate a SHA-256 receipt."""
    working_dir = working_dir.resolve()
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{working_dir}:{existing_pythonpath}" if existing_pythonpath else str(working_dir)
    )

    results: list[SnippetCheckResult] = []
    hasher = hashlib.sha256()

    for idx, (lang, code) in enumerate(commands, start=1):
        safe, reason = _is_safe_command(code)
        if not safe:
            digest = hashlib.sha256(f"{idx}:{lang}:{code}:BLOCKED".encode()).hexdigest()
            results.append(
                SnippetCheckResult(
                    index=idx,
                    language=lang,
                    command=code,
                    passed=False,
                    exit_code=126,
                    stdout="",
                    stderr=reason,
                    duration_ms=0,
                    receipt_sha256=digest,
                )
            )
            hasher.update(digest.encode())
            continue

        start = time.monotonic()
        try:
            if lang == "python":
                cmd_args = ["python3", "-c", code]
            else:
                cmd_args = ["bash", "-e", "-c", code]

            proc = subprocess.run(
                cmd_args,
                cwd=str(working_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout_trimmed = proc.stdout.strip()[:2000]
            stderr_trimmed = proc.stderr.strip()[:2000]
            passed = proc.returncode == 0
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout_trimmed = ""
            stderr_trimmed = f"Command timed out after {timeout_seconds}s"
            passed = False
            exit_code = 124

        payload = f"{idx}|{lang}|{code}|{exit_code}|{stdout_trimmed}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        hasher.update(digest.encode("utf-8"))

        results.append(
            SnippetCheckResult(
                index=idx,
                language=lang,
                command=code,
                passed=passed,
                exit_code=exit_code,
                stdout=stdout_trimmed,
                stderr=stderr_trimmed,
                duration_ms=duration_ms,
                receipt_sha256=digest,
            )
        )

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    all_passed = len(results) > 0 and failed_count == 0

    return VerificationReceipt(
        repo_path=str(working_dir),
        version_tag=version_tag,
        verified_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        all_passed=all_passed,
        total_checks=len(results),
        passed_checks=passed_count,
        failed_checks=failed_count,
        overall_receipt_sha256=hasher.hexdigest(),
        results=[asdict(r) for r in results],
    )

