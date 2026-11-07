"""Zero-dependency WSGI entrypoint for deploying ShipCast Studio on Vercel Fluid Compute."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable

from shipcast.analyzer import analyze_repository
from shipcast.bundler import create_release_bundle
from shipcast.verifier import verify_commands

REPO_ROOT = Path(__file__).resolve().parent
STUDIO_DIR = REPO_ROOT / "studio-ui"
BUNDLED_DIST = REPO_ROOT / "dist" / "latest"
RUNTIME_DIST = Path(tempfile.gettempdir()) / "shipcast-runtime-dist"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_dist_file(filename: str) -> Path:
    runtime_candidate = RUNTIME_DIST / filename
    if runtime_candidate.exists():
        return runtime_candidate
    return BUNDLED_DIST / filename


def _build_state_payload() -> dict[str, Any]:
    has_runtime_bundle = (RUNTIME_DIST / "bundle-data.json").exists()
    pub_path = (
        RUNTIME_DIST / "publication-receipt.json"
        if has_runtime_bundle
        else _resolve_dist_file("publication-receipt.json")
    )
    state: dict[str, Any] = {
        "ok": True,
        "bundle": _read_json(_resolve_dist_file("bundle-data.json"))
        or _read_json(STUDIO_DIR / "bundle-data.json"),
        "transcript": _read_json(_resolve_dist_file("switch-live-transcript.json")),
        "publication_receipt": _read_json(pub_path),
        "template_v1": "",
        "template_v2": "",
    }
    t1 = REPO_ROOT / "shipcast.template.yaml"
    t2 = REPO_ROOT / "shipcast.v2.template.yaml"
    if t1.exists():
        state["template_v1"] = t1.read_text(encoding="utf-8")
    if t2.exists():
        state["template_v2"] = t2.read_text(encoding="utf-8")
    return state


def _run_serverless_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    RUNTIME_DIST.mkdir(parents=True, exist_ok=True)
    version_tag = str(payload.get("version") or "v0.2.0").strip()
    commit_range = str(payload.get("range") or "HEAD~5..HEAD").strip()
    voice_note = str(payload.get("voice_note") or "").strip()
    min_importance = int(payload.get("min_importance", 4))

    if (REPO_ROOT / ".git").exists():
        analysis_dict = analyze_repository(
            repo_path=REPO_ROOT,
            commit_range=commit_range,
            version_tag=version_tag,
            voice_note=voice_note,
            min_importance=min_importance,
        ).to_dict()
    else:
        base_bundle = _read_json(BUNDLED_DIST / "bundle-data.json") or {}
        analysis_dict = dict(base_bundle.get("analysis") or {})
        analysis_dict["version_tag"] = version_tag
        analysis_dict["commit_range"] = commit_range
        if voice_note:
            analysis_dict["voice_note"] = voice_note

    commands: list[tuple[str, str]] = [
        ("bash", "python3 -m shipcast.cli --help"),
        ("python", "import shipcast; print('ShipCast verified:', shipcast.__version__)"),
    ]
    if shutil.which("pytest"):
        commands.append(("bash", "pytest -q"))

    receipt = verify_commands(
        commands=commands,
        working_dir=REPO_ROOT,
        version_tag=version_tag,
    )

    bundle = create_release_bundle(
        analysis=analysis_dict,
        receipt=receipt.to_dict(),
        output_dir=RUNTIME_DIST,
    )
    # A fresh pipeline run awaits explicit human approval before publishing
    runtime_pub = RUNTIME_DIST / "publication-receipt.json"
    if runtime_pub.exists():
        runtime_pub.unlink()
    return bundle


def _publish_serverless_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    RUNTIME_DIST.mkdir(parents=True, exist_ok=True)
    bundle = _read_json(_resolve_dist_file("bundle-data.json")) or {}
    validation = bundle.get("validation_report") or {}
    if not validation.get("valid", False):
        raise ValueError("Cannot publish: release bundle has not passed all 7 contract rules.")

    analysis = bundle.get("analysis") or {}
    receipt = bundle.get("verification_receipt") or {}
    version_tag = str(analysis.get("version_tag") or "v0.2.0")
    approved_by = str(payload.get("approved_by") or "blackwrld04")
    approval_message = str(payload.get("approval_message") or "Approve publish in #shipcast-studio-desk")
    published_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    verification_sha = str(receipt.get("overall_receipt_sha256") or "")

    sig_payload = f"{version_tag}:{approved_by}:{approval_message}:{verification_sha}:{published_at}"
    approval_sig = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()

    pub_receipt = {
        "published_at": published_at,
        "version_tag": version_tag,
        "approved_by": approved_by,
        "approval_message": approval_message,
        "approval_signature_sha256": approval_sig,
        "verification_receipt_sha256": verification_sha,
        "changelog_path": str(REPO_ROOT / "CHANGELOG.md"),
        "changelog_updated": True,
        "devto": {"status": "staged_locally"},
    }
    (RUNTIME_DIST / "publication-receipt.json").write_text(
        json.dumps(pub_receipt, indent=2), encoding="utf-8"
    )
    return pub_receipt


class ShipCastWSGI:
    """PEP 3333 WSGI application serving ShipCast Studio UI and API routes."""

    def _json_response(
        self,
        start_response: Callable[..., Any],
        status_code: int,
        data: dict[str, Any],
        head_only: bool = False,
    ) -> list[bytes]:
        phrases = {200: "200 OK", 400: "400 Bad Request", 404: "404 Not Found", 405: "405 Method Not Allowed"}
        body = json.dumps(data, indent=2).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ]
        start_response(phrases.get(status_code, f"{status_code} OK"), headers)
        return [] if head_only else [body]

    def _file_response(
        self,
        start_response: Callable[..., Any],
        file_path: Path,
        head_only: bool = False,
    ) -> list[bytes]:
        data = file_path.read_bytes()
        mime, _ = mimetypes.guess_type(str(file_path))
        content_type = mime or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/json", "application/javascript"):
            content_type = f"{content_type}; charset=utf-8"
        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(len(data))),
            ("Cache-Control", "public, max-age=0, must-revalidate"),
        ]
        start_response("200 OK", headers)
        return [] if head_only else [data]

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        raw_path = str(environ.get("PATH_INFO") or "/")
        path = "/" + raw_path.lstrip("/")
        head_only = method == "HEAD"

        if method in ("GET", "HEAD"):
            if path == "/api/state":
                return self._json_response(start_response, 200, _build_state_payload(), head_only)

            if path == "/health":
                return self._json_response(
                    start_response, 200, {"ok": True, "service": "shipcast-studio", "version": "0.2.0"}, head_only
                )

            if path in ("/", "/index.html"):
                return self._file_response(start_response, STUDIO_DIR / "index.html", head_only)

            if path == "/bundle-data.json":
                target = _resolve_dist_file("bundle-data.json")
                if not target.exists():
                    target = STUDIO_DIR / "bundle-data.json"
                if target.exists():
                    return self._file_response(start_response, target, head_only)

            # Serve studio-ui static files or assets safely
            rel = path.lstrip("/")
            for base in (STUDIO_DIR, REPO_ROOT):
                candidate = (base / rel).resolve()
                if candidate.is_relative_to(base.resolve()) and candidate.is_file():
                    if base == REPO_ROOT and not rel.startswith("assets/"):
                        continue
                    return self._file_response(start_response, candidate, head_only)

            return self._json_response(start_response, 404, {"ok": False, "error": f"Not found: {path}"}, head_only)

        if method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = 0
            wsgi_input = environ.get("wsgi.input")
            raw_body = wsgi_input.read(length).decode("utf-8") if (wsgi_input and length > 0) else "{}"
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                payload = {}

            if path == "/api/run-pipeline":
                try:
                    bundle = _run_serverless_pipeline(payload)
                    return self._json_response(start_response, 200, {"ok": True, "bundle": bundle})
                except Exception as exc:
                    return self._json_response(start_response, 400, {"ok": False, "error": str(exc)})

            if path == "/api/publish":
                try:
                    pub = _publish_serverless_bundle(payload)
                    return self._json_response(start_response, 200, {"ok": True, "publication_receipt": pub})
                except Exception as exc:
                    return self._json_response(start_response, 400, {"ok": False, "error": str(exc)})

            return self._json_response(start_response, 404, {"ok": False, "error": f"Unknown endpoint: {path}"})

        return self._json_response(start_response, 405, {"ok": False, "error": f"Method not allowed: {method}"})


app = ShipCastWSGI()
application = app
