"""
Knowledge-base PDF downloader.

Reads every `sources*.json` manifest in this directory and downloads each listed
PDF into ./pdfs/ (idempotent). For each entry, records SHA-256, byte size, HTTP
status, and fetch timestamp in fetch_report.json plus a human-readable
manifest.md.

Design goals:
- Pure stdlib only (no third-party deps required; uses `certifi` if available).
- Idempotent: an existing file is hashed and skipped.
- Traceable: every downloaded file is bound to a source-manifest entry whose
  URL, publisher, year and 'why_relevant' are preserved.
- Polite: a realistic User-Agent string, sequential downloads with a small
  delay so the corpus can be re-fetched by students without hammering origins.

Usage (from the knowledge_base/ directory):
    python fetch.py                       # download everything missing
    python fetch.py --force               # re-download everything
    python fetch.py --only A01            # ids starting with this prefix
    python fetch.py --manifest sources.json     # restrict to one manifest
    python fetch.py --manifest sources_rs.json  # only R&S vendor material
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "pdfs"
REPORT_FILE = HERE / "fetch_report.json"
MANIFEST_MD = HERE / "manifest.md"
MANUAL_MD = HERE / "manual_downloads.md"


def discover_manifests(restrict: str | None = None) -> list[Path]:
    """Return all sources*.json files (sorted), optionally restricted to one."""
    if restrict:
        p = HERE / restrict
        if not p.exists():
            raise FileNotFoundError(f"manifest not found: {p}")
        return [p]
    files = sorted(HERE.glob("sources*.json"))
    if not files:
        raise FileNotFoundError(f"no sources*.json files found in {HERE}")
    return files

# Some publisher sites (e.g. Ofcom) reject the default Python User-Agent with HTTP 403.
# We send a realistic browser UA. We are only requesting public PDFs that are linked
# from each publisher's own pages, so this is benign.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_S = 120
SLEEP_BETWEEN_REQUESTS_S = 1.0
MAX_RETRIES = 2
PDF_MAGIC = b"%PDF-"

# Prefer the certifi CA bundle if available (works around Windows Python installs
# whose default trust store does not chain to every public root).
try:
    import certifi  # type: ignore
    _CA_FILE = certifi.where()
except Exception:  # noqa: BLE001
    _CA_FILE = None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_ssl_context() -> ssl.SSLContext:
    if _CA_FILE:
        return ssl.create_default_context(cafile=_CA_FILE)
    return ssl.create_default_context()


def _download_once(url: str, dest: Path) -> tuple[int, str | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    ctx = _make_ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S, context=ctx) as resp:
            status = resp.status
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp.replace(dest)
            return status, None
    except urllib.error.HTTPError as e:
        return e.code, f"HTTPError: {e.reason}"
    except urllib.error.URLError as e:
        return 0, f"URLError: {e.reason}"
    except TimeoutError as e:
        return 0, f"Timeout: {e}"
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def download(url: str, dest: Path) -> tuple[int, str | None]:
    """Download with retries on transient errors. Returns (http_status, error_or_None)."""
    last_status, last_err = 0, "no attempt"
    for attempt in range(1, MAX_RETRIES + 2):  # initial + MAX_RETRIES retries
        last_status, last_err = _download_once(url, dest)
        if last_err is None:
            return last_status, None
        # Don't retry hard client errors (except 429).
        if 400 <= last_status < 500 and last_status not in (408, 425, 429):
            return last_status, last_err
        if attempt <= MAX_RETRIES:
            backoff = 2.0 * attempt
            print(f"   [retry {attempt}/{MAX_RETRIES}] {last_err} - sleeping {backoff:.0f}s")
            time.sleep(backoff)
    return last_status, last_err


def looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(5) == PDF_MAGIC
    except OSError:
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_all(
    force: bool = False,
    only: str | None = None,
    manifest: str | None = None,
) -> dict:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    manifest_files = discover_manifests(manifest)
    docs: list[tuple[Path, dict]] = []
    sources: list[dict] = []
    for mf in manifest_files:
        doc = json.loads(mf.read_text(encoding="utf-8"))
        docs.append((mf, doc))
        for s in doc["sources"]:
            s.setdefault("_manifest", mf.name)
            sources.append(s)

    entries = []
    for src in sources:
        sid = src["id"]
        if only and not sid.startswith(only):
            continue
        dest = PDF_DIR / src["filename"]
        entry = {
            "id": sid,
            "manifest": src.get("_manifest"),
            "filename": src["filename"],
            "url": src["url"],
            "category": src.get("category"),
            "publisher": src.get("publisher"),
            "year": src.get("year"),
            "title": src.get("title"),
            "fetched_at": None,
            "http_status": None,
            "size_bytes": None,
            "sha256": None,
            "is_pdf": None,
            "ok": False,
            "error": None,
            "skipped_existing": False,
            "manual_download": bool(src.get("manual_download", False)),
            "manual_reason": src.get("manual_reason"),
        }

        if entry["manual_download"] and not dest.exists():
            entry["error"] = "manual_download_required"
            entry["fetched_at"] = now_iso()
            print(f"[MANUAL] {sid:<55} -> {src['url']}")
            print(f"          reason: {entry['manual_reason']}")
            entries.append(entry)
            continue

        if dest.exists() and not force:
            entry["sha256"] = sha256_of(dest)
            entry["size_bytes"] = dest.stat().st_size
            entry["is_pdf"] = looks_like_pdf(dest)
            entry["ok"] = entry["is_pdf"]
            entry["skipped_existing"] = True
            entry["fetched_at"] = now_iso()
            print(f"[skip ] {sid:<55} (already present, {entry['size_bytes']:>10} B)")
            entries.append(entry)
            continue

        print(f"[fetch] {sid:<55} -> {src['url']}")
        status, err = download(src["url"], dest)
        entry["http_status"] = status
        entry["error"] = err
        entry["fetched_at"] = now_iso()
        if err is None and dest.exists():
            entry["size_bytes"] = dest.stat().st_size
            entry["sha256"] = sha256_of(dest)
            entry["is_pdf"] = looks_like_pdf(dest)
            entry["ok"] = entry["is_pdf"]
            tag = "ok  " if entry["ok"] else "BAD "
            print(
                f"   [{tag}] status={status} size={entry['size_bytes']} "
                f"pdf={entry['is_pdf']} sha256={entry['sha256'][:12]}..."
            )
        else:
            print(f"   [FAIL] status={status} error={err}")
        entries.append(entry)
        time.sleep(SLEEP_BETWEEN_REQUESTS_S)

    report = {
        "generated_at": now_iso(),
        "manifests": [
            {"file": mf.name, "field_of_interest": d.get("field_of_interest")}
            for mf, d in docs
        ],
        "total": len(entries),
        "ok": sum(1 for e in entries if e["ok"]),
        "manual_pending": sum(1 for e in entries if e.get("manual_download") and not e["ok"]),
        "failed": sum(1 for e in entries if not e["ok"] and not e.get("manual_download")),
        "entries": entries,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_manifest_md(report)
    write_manual_md(sources, entries)
    return report


def write_manifest_md(report: dict) -> None:
    lines = [
        "# Knowledge-base fetch manifest",
        "",
        f"Generated: {report['generated_at']}",
        "Manifests:",
    ]
    for m in report.get("manifests", []):
        lines.append(f"- `{m['file']}` - {m['field_of_interest']}")
    lines += [
        "",
        f"OK: {report['ok']} / {report['total']}  "
        f"(manual pending: {report.get('manual_pending', 0)}, failed: {report['failed']})",
        "",
        "| id | manifest | publisher | year | size (B) | pdf? | sha256 (12) | url |",
        "|---|---|---|---|---:|:---:|---|---|",
    ]
    for e in report["entries"]:
        sha = (e.get("sha256") or "")[:12]
        size = e.get("size_bytes") or 0
        if e["ok"]:
            pdf = "yes" if e.get("is_pdf") else "?"
        elif e.get("manual_download"):
            pdf = "manual"
        else:
            pdf = "no"
        lines.append(
            f"| `{e['id']}` | {e.get('manifest','')} | {e.get('publisher','')} | "
            f"{e.get('year','')} | {size} | {pdf} | `{sha}` | <{e['url']}> |"
        )
    MANIFEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manual_md(sources: "list[dict]", entries: "list[dict]") -> None:
    """Emit a human-readable checklist of files still needing a manual download."""
    src_by_id = {s["id"]: s for s in sources}
    pending = [e for e in entries if e.get("manual_download") and not e["ok"]]
    lines = [
        "# Manual downloads checklist",
        "",
        "The following PDFs cannot be retrieved by `fetch.py` (Cloudflare bot",
        "protection, non-validating TLS chains, etc.). Please open each URL in a",
        "normal web browser, save the file **using the exact target filename**, and",
        "place it inside `knowledge_base/pdfs/`. Then re-run `python fetch.py` - it",
        "will pick the new file up, compute the SHA-256, and mark it OK.",
        "",
        f"Total pending: **{len(pending)}**",
        "",
    ]
    if not pending:
        lines.append("_None - the corpus is complete._")
    else:
        for e in pending:
            s = src_by_id[e["id"]]
            lines.extend([
                f"## `{e['id']}` - {s.get('title','')}",
                "",
                f"- Publisher: {s.get('publisher','')} ({s.get('year','')})",
                f"- Direct PDF URL: <{s['url']}>",
            ])
            if s.get("landing_page"):
                lines.append(f"- Landing page (if direct link is blocked): <{s['landing_page']}>")
            lines.extend([
                f"- Save as: `pdfs/{s['filename']}`",
                f"- Why: {s.get('manual_reason','')}",
                "",
            ])
    MANUAL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="re-download even if file exists")
    p.add_argument("--only", help="only download ids starting with this prefix (e.g. A01, F, K)")
    p.add_argument(
        "--manifest",
        help="restrict to one manifest file (default: all sources*.json in this dir)",
    )
    args = p.parse_args()
    report = fetch_all(force=args.force, only=args.only, manifest=args.manifest)
    print()
    print(
        f"Done. {report['ok']}/{report['total']} files OK "
        f"(manual pending: {report.get('manual_pending', 0)}, failed: {report['failed']}). "
        f"Report -> {REPORT_FILE.name}, manifest -> {MANIFEST_MD.name}, "
        f"manual checklist -> {MANUAL_MD.name}."
    )
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
