"""Command-line interface and live Studio HTTP API server for ShipCast."""

from __future__ import annotations

import argparse
import http.server
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from shipcast.analyzer import analyze_repository
from shipcast.bundler import create_release_bundle
from shipcast.publisher import publish_release_bundle
from shipcast.validator import validate_release_bundle
from shipcast.verifier import extract_fenced_commands, verify_commands


def execute_pipeline(
    repo_path: Path,
    commit_range: str,
    version_tag: str,
    voice_note: str,
    min_importance: int,
    extra_commands: list[str],
    output_dir: Path,
) -> dict[str, Any]:
    repo_path = repo_path.resolve()
    output_dir = output_dir.resolve()

    analysis = analyze_repository(
        repo_path=repo_path,
        commit_range=commit_range,
        version_tag=version_tag,
        voice_note=voice_note,
        min_importance=min_importance,
    )

    commands: list[tuple[str, str]] = [("bash", cmd) for cmd in analysis.extracted_commands]
    for extra in extra_commands:
        if extra and ("bash", extra) not in commands:
            commands.append(("bash", extra))

    receipt = verify_commands(
        commands=commands,
        working_dir=repo_path,
        version_tag=version_tag,
    )

    bundle = create_release_bundle(
        analysis=analysis.to_dict(),
        receipt=receipt.to_dict(),
        output_dir=output_dir,
    )

    studio_dir = repo_path / "studio-ui"
    if studio_dir.exists():
        shutil.copyfile(output_dir / "bundle-data.json", studio_dir / "bundle-data.json")

    return bundle


def cmd_analyze(args: argparse.Namespace) -> int:
    analysis = analyze_repository(
        repo_path=Path(args.repo),
        commit_range=args.range,
        version_tag=args.version,
        voice_note=args.voice_note,
        min_importance=args.min_importance,
    )
    out_json = json.dumps(analysis.to_dict(), indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_json, encoding="utf-8")
    print(out_json)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    repo_path = Path(args.repo).resolve()
    commands: list[tuple[str, str]] = []
    for c in args.command or []:
        commands.append(("bash", c))
    if args.markdown:
        md_text = Path(args.markdown).read_text(encoding="utf-8")
        commands.extend(extract_fenced_commands(md_text))
    if not commands:
        commands = [
            ("bash", "python3 -m shipcast.cli --help"),
            ("python", "import shipcast; print('ShipCast version:', shipcast.__version__)"),
        ]
    receipt = verify_commands(
        commands=commands,
        working_dir=repo_path,
        version_tag=args.version,
        timeout_seconds=args.timeout,
    )
    out_json = json.dumps(receipt.to_dict(), indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_json, encoding="utf-8")
    print(out_json)
    return 0 if receipt.all_passed else 1


def cmd_run_pipeline(args: argparse.Namespace) -> int:
    bundle = execute_pipeline(
        repo_path=Path(args.repo),
        commit_range=args.range,
        version_tag=args.version,
        voice_note=args.voice_note,
        min_importance=args.min_importance,
        extra_commands=args.command or [],
        output_dir=Path(args.output_dir),
    )
    print(bundle["preview"]["room_summary"])
    print(f"\n[Bundle written to: {Path(args.output_dir).resolve()}]")
    return 0 if bundle["validation_report"]["valid"] else 1


def cmd_validate(args: argparse.Namespace) -> int:
    bundle_dir = Path(args.bundle_dir).resolve()
    article_md = (bundle_dir / "devto-article.md").read_text(encoding="utf-8")
    room_summary = (bundle_dir / "switch-room-summary.txt").read_text(encoding="utf-8")
    receipt = json.loads((bundle_dir / "verification-receipt.json").read_text(encoding="utf-8"))
    report = validate_release_bundle(article_md, room_summary, receipt)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.valid else 1


def cmd_publish(args: argparse.Namespace) -> int:
    pub = publish_release_bundle(
        bundle_dir=Path(args.bundle_dir).resolve(),
        repo_path=Path(args.repo).resolve(),
        approved_by=args.approved_by,
        approval_message=args.approval_message,
        publish_devto=args.devto,
    )
    print(json.dumps(pub, indent=2))
    return 0


class StudioRequestHandler(http.server.SimpleHTTPRequestHandler):
    repo_root: Path = Path(".")

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.startswith("/api/state"):
            dist_dir = self.repo_root / "dist" / "latest"
            state: dict[str, Any] = {"ok": True}
            for key, rel in [
                ("bundle", dist_dir / "bundle-data.json"),
                ("transcript", dist_dir / "switch-live-transcript.json"),
                ("publication_receipt", dist_dir / "publication-receipt.json"),
            ]:
                if rel.exists():
                    try:
                        state[key] = json.loads(rel.read_text(encoding="utf-8"))
                    except Exception:
                        state[key] = None
            for key, yaml_path in [
                ("template_v1", self.repo_root / "shipcast.template.yaml"),
                ("template_v2", self.repo_root / "shipcast.v2.template.yaml"),
            ]:
                if yaml_path.exists():
                    state[key] = yaml_path.read_text(encoding="utf-8")
            self._send_json(200, state)
            return
        super().do_GET()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body_raw)
        except json.JSONDecodeError:
            payload = {}

        if self.path == "/api/run-pipeline":
            try:
                bundle = execute_pipeline(
                    repo_path=self.repo_root,
                    commit_range=payload.get("range", "HEAD~3..HEAD"),
                    version_tag=payload.get("version", "v0.2.0"),
                    voice_note=payload.get("voice_note", ""),
                    min_importance=int(payload.get("min_importance", 4)),
                    extra_commands=payload.get("commands", ["pytest -q"]),
                    output_dir=self.repo_root / "dist" / "latest",
                )
                self._send_json(200, {"ok": True, "bundle": bundle})
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/publish":
            try:
                pub = publish_release_bundle(
                    bundle_dir=self.repo_root / "dist" / "latest",
                    repo_path=self.repo_root,
                    approved_by=payload.get("approved_by", "blackwrld04"),
                    approval_message=payload.get("approval_message", "Approved. Publish it!"),
                    publish_devto=bool(payload.get("devto", False)),
                )
                self._send_json(200, {"ok": True, "publication_receipt": pub})
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            return

        self._send_json(404, {"ok": False, "error": f"Unknown endpoint: {self.path}"})


def cmd_serve_studio(args: argparse.Namespace) -> int:
    studio_dir = Path(args.dir).resolve()
    repo_root = studio_dir.parent

    class BoundHandler(StudioRequestHandler):
        def __init__(self, *h_args: Any, **h_kwargs: Any) -> None:
            self.repo_root = repo_root
            super().__init__(*h_args, directory=str(studio_dir), **h_kwargs)

    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), BoundHandler) as httpd:
        print(f"ShipCast Studio UI + Live API serving at http://127.0.0.1:{args.port}", flush=True)
        httpd.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shipcast",
        description="ShipCast: Autonomous Code-to-Content & Verified Release Studio for Switch Rooms",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_analyze = sub.add_parser("analyze", help="Analyze a git commit range and score importance")
    p_analyze.add_argument("--repo", default=".", help="Path to git repository")
    p_analyze.add_argument("--range", default="HEAD~5..HEAD", help="Git commit range")
    p_analyze.add_argument("--version", default="v0.2.0", help="Release version tag")
    p_analyze.add_argument("--voice-note", default="", help="Optional voice-dictated context note")
    p_analyze.add_argument("--min-importance", type=int, default=4, help="Minimum score (1-10)")
    p_analyze.add_argument("--output", default="", help="Optional JSON file output path")
    p_analyze.set_defaults(func=cmd_analyze)

    p_verify = sub.add_parser("verify", help="Execute commands/snippets in sandbox & sign receipt")
    p_verify.add_argument("--repo", default=".", help="Working directory for execution")
    p_verify.add_argument("--version", default="v0.2.0", help="Release version tag")
    p_verify.add_argument("--command", action="append", help="Command to execute in sandbox")
    p_verify.add_argument("--markdown", default="", help="Markdown file with fenced blocks to run")
    p_verify.add_argument("--timeout", type=float, default=15.0, help="Per-command timeout (s)")
    p_verify.add_argument("--output", default="", help="Optional JSON file output path")
    p_verify.set_defaults(func=cmd_verify)

    p_pipe = sub.add_parser(
        "run-pipeline",
        help="Run full analyze -> verify -> bundle -> validate pipeline and print Switch receipt",
    )
    p_pipe.add_argument("--repo", default=".", help="Path to git repository")
    p_pipe.add_argument("--range", default="HEAD~5..HEAD", help="Git commit range")
    p_pipe.add_argument("--version", default="v0.2.0", help="Release version tag")
    p_pipe.add_argument("--voice-note", default="", help="Optional voice-dictated context note")
    p_pipe.add_argument("--min-importance", type=int, default=4, help="Minimum score (1-10)")
    p_pipe.add_argument("--command", action="append", help="Additional verification command")
    p_pipe.add_argument("--output-dir", default="dist/latest", help="Output bundle directory")
    p_pipe.set_defaults(func=cmd_run_pipeline)

    p_val = sub.add_parser("validate", help="Validate a generated release bundle against contract")
    p_val.add_argument("--bundle-dir", default="dist/latest", help="Bundle directory")
    p_val.set_defaults(func=cmd_validate)

    p_pub = sub.add_parser("publish", help="Publish a validated bundle after human approval")
    p_pub.add_argument("--bundle-dir", default="dist/latest", help="Bundle directory")
    p_pub.add_argument("--repo", default=".", help="Repository root for CHANGELOG.md update")
    p_pub.add_argument("--approved-by", required=True, help="Username of human approver in Switch")
    p_pub.add_argument(
        "--approval-message", default="Approve publish", help="Exact approval message from room"
    )
    p_pub.add_argument("--devto", action="store_true", help="Publish draft to DEV.to if key set")
    p_pub.set_defaults(func=cmd_publish)

    p_serve = sub.add_parser("serve-studio", help="Serve the local ShipCast Studio web UI")
    p_serve.add_argument("--dir", default="studio-ui", help="Studio UI directory")
    p_serve.add_argument("--port", type=int, default=8765, help="Port number")
    p_serve.set_defaults(func=cmd_serve_studio)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
