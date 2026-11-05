"""Git repository commit range analyzer and importance scorer for ShipCast."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import subprocess
from typing import Any

NOISE_FILES = {
    "uv.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Cargo.lock",
    ".DS_Store",
}

SKIP_MARKERS = ("[skip-post]", "[skip shipcast]", "[skip ci]")


@dataclass
class CommitRecord:
    sha: str
    short_sha: str
    subject: str
    body: str
    author: str
    date: str
    category: str
    files_changed: list[str]
    insertions: int
    deletions: int
    importance_score: int
    skipped: bool
    skip_reason: str = ""


@dataclass
class ReleaseAnalysis:
    repo_path: str
    repo_name: str
    commit_range: str
    version_tag: str
    voice_note: str
    total_commits: int
    included_commits: int
    skipped_commits: int
    overall_importance: int
    files_touched: list[str]
    total_insertions: int
    total_deletions: int
    categories: dict[str, list[dict[str, Any]]]
    commits: list[dict[str, Any]]
    extracted_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run_git(repo_path: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {repo_path}: {result.stderr.strip()}"
        )
    return result.stdout


def categorize_commit(subject: str, files: list[str]) -> str:
    lower = subject.lower().strip()
    if lower.startswith(("feat", "add", "ship", "implement", "introduce")):
        return "Added"
    if lower.startswith(("fix", "bug", "resolve", "patch", "hotfix")):
        return "Fixed"
    if lower.startswith(("sec", "vuln", "auth", "guardrail")):
        return "Security"
    if lower.startswith(("chore", "ci", "build", "bump", "style", "fmt")):
        return "Chore"
    if lower.startswith(("docs", "readme", "comment")):
        return "Documentation"
    if any(f.startswith("tests/") or f.endswith("_test.py") for f in files) and len(files) == 1:
        return "Tests"
    return "Changed"


def score_commit(
    subject: str,
    category: str,
    files: list[str],
    insertions: int,
    deletions: int,
) -> tuple[int, bool, str]:
    lower = subject.lower()
    for marker in SKIP_MARKERS:
        if marker in lower:
            return 1, True, f"Contains {marker}"

    non_noise = [f for f in files if Path(f).name not in NOISE_FILES]
    if files and not non_noise:
        return 1, True, "Only lockfiles or noise files modified"

    if category == "Chore" and insertions + deletions < 30:
        return 2, True, "Minor chore/maintenance commit"

    score = 4
    if category == "Added":
        score += 3
    elif category in ("Fixed", "Security"):
        score += 2
    elif category == "Changed":
        score += 1

    code_files = [
        f
        for f in non_noise
        if f.endswith((".py", ".ts", ".tsx", ".js", ".rs", ".go", ".yaml", ".yml", ".html"))
    ]
    if len(code_files) >= 3:
        score += 2
    elif len(code_files) >= 1:
        score += 1

    if insertions + deletions >= 100:
        score += 1

    score = max(1, min(10, score))
    return score, False, ""


def analyze_repository(
    repo_path: Path,
    commit_range: str = "HEAD~5..HEAD",
    version_tag: str = "v0.2.0",
    voice_note: str = "",
    min_importance: int = 4,
) -> ReleaseAnalysis:
    repo_path = repo_path.resolve()
    if not (repo_path / ".git").exists():
        raise ValueError(f"Not a git repository: {repo_path}")

    # Determine valid commit range; fallback to all commits if repo has fewer commits than requested
    check_range = subprocess.run(
        ["git", "-C", str(repo_path), "rev-list", "--count", commit_range],
        capture_output=True,
        text=True,
        check=False,
    )
    effective_range = commit_range if check_range.returncode == 0 else "HEAD"

    log_raw = _run_git(
        repo_path,
        [
            "log",
            effective_range,
            "--pretty=format:%H%x1f%h%x1f%s%x1f%b%x1f%an%x1f%ad",
            "--date=short",
        ],
    )

    records: list[CommitRecord] = []
    all_files: set[str] = set()
    total_ins = 0
    total_del = 0

    for entry in [e for e in log_raw.split("\n") if "\x1f" in e]:
        parts = entry.split("\x1f")
        if len(parts) < 6:
            continue
        sha, short_sha, subject, body, author, date_str = (
            parts[0].strip(),
            parts[1].strip(),
            parts[2].strip(),
            parts[3].strip(),
            parts[4].strip(),
            parts[5].strip(),
        )
        numstat = _run_git(repo_path, ["show", "--numstat", "--format=", sha])
        files: list[str] = []
        ins = 0
        dels = 0
        for line in numstat.strip().splitlines():
            cols = line.split("\t")
            if len(cols) == 3:
                a_str, d_str, fname = cols
                files.append(fname.strip())
                if a_str.isdigit():
                    ins += int(a_str)
                if d_str.isdigit():
                    dels += int(d_str)

        category = categorize_commit(subject, files)
        score, skipped, reason = score_commit(subject, category, files, ins, dels)
        if not skipped and score < min_importance:
            skipped = True
            reason = f"Score {score} below threshold {min_importance}"

        if not skipped:
            all_files.update(files)
            total_ins += ins
            total_del += dels

        records.append(
            CommitRecord(
                sha=sha,
                short_sha=short_sha,
                subject=subject,
                body=body,
                author=author,
                date=date_str,
                category=category,
                files_changed=files,
                insertions=ins,
                deletions=dels,
                importance_score=score,
                skipped=skipped,
                skip_reason=reason,
            )
        )

    included = [r for r in records if not r.skipped]
    categories: dict[str, list[dict[str, Any]]] = {}
    for rec in included:
        categories.setdefault(rec.category, []).append(asdict(rec))

    overall_importance = (
        max((r.importance_score for r in included), default=5)
        if included
        else 3
    )
    if len(included) >= 3:
        overall_importance = min(10, overall_importance + 1)

    # Extract any backtick CLI commands mentioned in commit bodies or voice note
    combined_notes = "\n".join([voice_note] + [f"{r.subject}\n{r.body}" for r in included])
    cmd_matches = re.findall(r"`((?:shipcast|python3\s+-m\s+shipcast|pytest)[^`\n]*)`", combined_notes)
    extracted_commands = list(dict.fromkeys(cmd_matches))
    if not extracted_commands:
        extracted_commands = [
            "python3 -m shipcast.cli --help",
        ]

    return ReleaseAnalysis(
        repo_path=str(repo_path),
        repo_name=repo_path.name,
        commit_range=effective_range,
        version_tag=version_tag,
        voice_note=voice_note,
        total_commits=len(records),
        included_commits=len(included),
        skipped_commits=len(records) - len(included),
        overall_importance=overall_importance,
        files_touched=sorted(all_files),
        total_insertions=total_ins,
        total_deletions=total_del,
        categories=categories,
        commits=[asdict(r) for r in records],
        extracted_commands=extracted_commands,
    )

