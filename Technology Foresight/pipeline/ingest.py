"""Parse PDFs, patent JSON, and Semantic Scholar papers into a unified corpus."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader

SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SCHOLAR_FIELDS = "title,abstract,authors,year,externalIds,fieldsOfStudy,publicationDate"
SCHOLAR_HEADERS = {
    "User-Agent": "TechnologyForesight/1.0 (DI Lab; academic foresight tool)",
    "Accept": "application/json",
}
SCHOLAR_MAX_PER_PAGE = 100
SCHOLAR_HARD_CAP = 500
_SCHOLAR_CACHE: dict[tuple[str, int], tuple[float, list[dict[str, Any]], str]] = {}
_SCHOLAR_CACHE_TTL = 3600
_SCHOLAR_DISK_TTL = 86400
_SCHOLAR_DISK_CACHE_DIR = Path(__file__).resolve().parent.parent / "uploads" / ".scholar_cache"
_SCHOLAR_LOCK = threading.Lock()
_SCHOLAR_LAST_REQUEST_AT = 0.0
_SCHOLAR_MIN_INTERVAL = 1.2
_SCHOLAR_RATE_LIMITED_UNTIL = 0.0
_SCHOLAR_RETRY_WAITS = (5, 15, 30, 60)


class ScholarError(Exception):
    pass


def _sanitize_user_query(user_query: str) -> str:
    q = user_query.strip()
    q = re.sub(r"[\r\n\t]+", " ", q)
    q = re.sub(r"\s+", " ", q)
    return q


def _current_year() -> int:
    return time.localtime().tm_year


def _split_years_from_terms(terms: list[str]) -> tuple[list[str], list[str]]:
    years = [t for t in terms if re.fullmatch(r"(?:19|20)\d{2}", t)]
    content = [t for t in terms if t not in years]
    return content, years


def parse_foresight_query(user_query: str) -> dict[str, Any]:
    """Split user input into searchable topic terms and optional future horizon year."""
    q = _sanitize_user_query(user_query)
    if not q:
        return {
            "raw_query": "",
            "topic_label": "",
            "topic_terms": [],
            "horizon_year": None,
            "search_query": "",
        }

    terms = re.findall(r"[\w.\-]+", q)
    content_terms, years = _split_years_from_terms(terms)
    horizon_year = None
    for y in years:
        yi = int(y)
        if yi > _current_year():
            horizon_year = yi

    topic_label = " ".join(content_terms).strip() or q
    return {
        "raw_query": q,
        "topic_label": topic_label,
        "topic_terms": content_terms,
        "horizon_year": horizon_year,
        "search_query": build_scholar_search_query(q),
    }


def build_scholar_search_query(user_query: str) -> str:
    """Natural-language query for Semantic Scholar search."""
    q = _sanitize_user_query(user_query)
    if not q:
        return ""

    terms = re.findall(r"[\w.\-]+", q)
    content_terms, years = _split_years_from_terms(terms)
    if not content_terms:
        content_terms = [t for t in terms if not re.fullmatch(r"(?:19|20)\d{2}", t)] or terms

    search = " ".join(content_terms)
    if years and int(years[-1]) <= _current_year():
        search = f"{search} {years[-1]}".strip()
    return search or q


def _year_filter_from_query(user_query: str) -> int | None:
    years = re.findall(r"\b(?:19|20)\d{2}\b", user_query)
    if not years:
        return None
    y = int(years[-1])
    if y > _current_year():
        return None
    return y


def _cache_key(query: str, max_results: int) -> tuple[str, int]:
    return (_sanitize_user_query(query).lower(), max_results)


def _scholar_headers() -> dict[str, str]:
    headers = dict(SCHOLAR_HEADERS)
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _disk_cache_path(key: tuple[str, int]) -> Path:
    _SCHOLAR_DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{key[0]}|{key[1]}".encode()).hexdigest()[:20]
    return _SCHOLAR_DISK_CACHE_DIR / f"{digest}.json"


def _load_disk_cache(key: tuple[str, int], max_age: int = _SCHOLAR_DISK_TTL) -> tuple[list[dict[str, Any]], str] | None:
    path = _disk_cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) > max_age:
            return None
        papers = data.get("papers", [])
        if papers:
            return papers, data.get("api_query", "")
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _load_stale_disk_cache(key: tuple[str, int]) -> tuple[list[dict[str, Any]], str] | None:
    path = _disk_cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        papers = data.get("papers", [])
        if papers:
            return papers, data.get("api_query", "")
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _save_disk_cache(key: tuple[str, int], papers: list[dict], api_query: str) -> None:
    path = _disk_cache_path(key)
    try:
        path.write_text(
            json.dumps({"ts": time.time(), "papers": papers, "api_query": api_query}, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass


def get_cached_scholar(query: str, max_results: int = 20) -> tuple[list[dict[str, Any]], str] | None:
    key = _cache_key(query, max_results)
    cached = _SCHOLAR_CACHE.get(key)
    if cached and (time.time() - cached[0]) < _SCHOLAR_CACHE_TTL:
        return cached[1], cached[2]
    disk = _load_disk_cache(key)
    if disk:
        papers, api_query = disk
        _SCHOLAR_CACHE[key] = (time.time(), papers, api_query)
        return papers, api_query
    return None


def _store_cache(key: tuple[str, int], papers: list[dict], api_query: str) -> None:
    _SCHOLAR_CACHE[key] = (time.time(), papers, api_query)
    _save_disk_cache(key, papers, api_query)


def _scholar_rate_limited() -> bool:
    return time.time() < _SCHOLAR_RATE_LIMITED_UNTIL


def _mark_scholar_rate_limited(retry_after: int | None = None) -> None:
    global _SCHOLAR_RATE_LIMITED_UNTIL
    cooldown = max(60, retry_after or 120)
    _SCHOLAR_RATE_LIMITED_UNTIL = time.time() + cooldown


def _wait_for_scholar_slot_locked() -> None:
    global _SCHOLAR_LAST_REQUEST_AT
    elapsed = time.time() - _SCHOLAR_LAST_REQUEST_AT
    if elapsed < _SCHOLAR_MIN_INTERVAL:
        time.sleep(_SCHOLAR_MIN_INTERVAL - elapsed)
    _SCHOLAR_LAST_REQUEST_AT = time.time()


def _retry_after_seconds(resp: requests.Response) -> int | None:
    raw = resp.headers.get("Retry-After", "").strip()
    if not raw:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return None


def _stale_cache_fallback(cache_key: tuple[str, int]) -> tuple[list[dict[str, Any]], str] | None:
    stale = _load_stale_disk_cache(cache_key)
    if stale:
        papers, api_query = stale
        _SCHOLAR_CACHE[cache_key] = (time.time(), papers, api_query)
        return papers, api_query
    return None


def _parse_scholar_paper(item: dict[str, Any]) -> dict[str, Any] | None:
    title = (item.get("title") or "").strip()
    abstract = (item.get("abstract") or "").strip()
    if not title and not abstract:
        return None

    authors = [a.get("name", "").strip() for a in item.get("authors") or [] if a.get("name")]
    year = item.get("year")
    published = (item.get("publicationDate") or "")[:10]
    if not year and published and len(published) >= 4:
        year = int(published[:4])

    paper_id = item.get("paperId") or ""
    external = item.get("externalIds") or {}
    fields = item.get("fieldsOfStudy") or []
    category = ", ".join(fields[:3]) if fields else ""

    return {
        "title": title or f"Paper {paper_id[:8]}",
        "abstract": abstract,
        "authors": authors,
        "published": published,
        "year": int(year) if year else None,
        "paper_id": paper_id,
        "doi": external.get("DOI", ""),
        "category": category,
        "source": "scholar",
        "text": f"{title}\n\n{abstract}".strip(),
    }


def _fetch_scholar_page(search_query: str, limit: int, offset: int) -> dict[str, Any]:
    params = {
        "query": search_query,
        "limit": limit,
        "offset": offset,
        "fields": SCHOLAR_FIELDS,
    }
    last_throttled: requests.Response | None = None

    with _SCHOLAR_LOCK:
        for attempt, wait in enumerate((0, *_SCHOLAR_RETRY_WAITS)):
            if wait:
                time.sleep(wait)
            _wait_for_scholar_slot_locked()
            try:
                resp = requests.get(
                    SCHOLAR_API,
                    params=params,
                    headers=_scholar_headers(),
                    timeout=90,
                )
            except requests.RequestException as exc:
                raise ScholarError(f"Could not reach Semantic Scholar: {exc}") from exc

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ScholarError("Semantic Scholar returned invalid JSON.") from exc

            if resp.status_code in (429, 503):
                last_throttled = resp
                retry_after = _retry_after_seconds(resp)
                if retry_after and attempt < len(_SCHOLAR_RETRY_WAITS):
                    time.sleep(retry_after)
                if attempt < len(_SCHOLAR_RETRY_WAITS):
                    continue
                _mark_scholar_rate_limited(retry_after)
                raise ScholarError(
                    "Semantic Scholar is rate-limiting requests. Wait 1–2 minutes, then click Fetch preview once."
                )

            if resp.status_code >= 400:
                raise ScholarError(f"Semantic Scholar returned HTTP {resp.status_code}.")

    if last_throttled is not None:
        _mark_scholar_rate_limited(_retry_after_seconds(last_throttled))
    raise ScholarError("Semantic Scholar is busy. Wait 1–2 minutes, then click Fetch preview once.")


def _fetch_scholar_all_pages(search_query: str, total: int, year_filter: int | None) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    offset = 0
    while len(papers) < total:
        batch_size = min(SCHOLAR_MAX_PER_PAGE, total - len(papers))
        payload = _fetch_scholar_page(search_query, batch_size, offset)
        batch_raw = payload.get("data") or []
        if not batch_raw:
            break
        for item in batch_raw:
            doc = _parse_scholar_paper(item)
            if not doc:
                continue
            if year_filter and doc.get("year") and doc["year"] != year_filter:
                continue
            papers.append(doc)
            if len(papers) >= total:
                break
        offset += len(batch_raw)
        if len(batch_raw) < batch_size:
            break
        if offset >= int(payload.get("total") or 0):
            break
    return papers


def fetch_scholar_preview(
    query: str,
    max_results: int = 20,
    *,
    use_cache_only: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Fetch papers from Semantic Scholar; cache on disk for preview + run."""
    q = _sanitize_user_query(query)
    if not q:
        raise ScholarError("Enter a search topic to find related papers on Semantic Scholar.")

    max_results = min(max(1, max_results), SCHOLAR_HARD_CAP)
    cache_key = _cache_key(q, max_results)

    hit = get_cached_scholar(q, max_results)
    if hit:
        return hit
    if use_cache_only:
        stale = _stale_cache_fallback(cache_key)
        if stale:
            return stale
        raise ScholarError(
            "Search results are not cached yet. Click Fetch preview once, wait, then run analysis."
        )

    if _scholar_rate_limited():
        stale = _stale_cache_fallback(cache_key)
        if stale:
            return stale
        raise ScholarError(
            "Semantic Scholar is temporarily rate-limiting this app. Wait 1–2 minutes, then click Fetch preview once."
        )

    api_query = build_scholar_search_query(q)
    if not api_query:
        raise ScholarError("Could not build a valid search from your input.")

    year_filter = _year_filter_from_query(q)
    try:
        papers = _fetch_scholar_all_pages(api_query, max_results, year_filter)
    except ScholarError:
        stale = _stale_cache_fallback(cache_key)
        if stale:
            return stale
        raise

    if not papers:
        hint = ""
        years = re.findall(r"\b(?:19|20)\d{2}\b", q)
        if years and int(years[-1]) > _current_year():
            hint = (
                f" No papers exist for calendar year {years[-1]} yet — "
                "search used your topic words only (year treated as context)."
            )
        raise ScholarError(
            f"No papers on Semantic Scholar matched «{q}». Try fewer or broader keywords."
            + hint
        )

    _store_cache(cache_key, papers, api_query)
    return papers, api_query


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def parse_patent_json(data: Any) -> list[dict[str, Any]]:
    docs = []
    items = data if isinstance(data, list) else data.get("patents", data.get("items", [data]))
    if not isinstance(items, list):
        items = [items]
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("invention_title") or "Untitled patent"
        abstract = item.get("abstract") or item.get("description") or ""
        year = item.get("year") or item.get("filing_year")
        if not year and item.get("date"):
            year = int(str(item["date"])[:4])
        docs.append(
            {
                "title": str(title),
                "abstract": str(abstract),
                "authors": item.get("inventors", item.get("assignee", [])),
                "published": str(item.get("date", "")),
                "year": int(year) if year else None,
                "paper_id": "",
                "category": item.get("classification", item.get("cpc", "")),
                "source": "uploaded",
                "text": f"{title}\n\n{abstract}",
            }
        )
    return docs


def ingest_uploaded_files(upload_dir: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    if not upload_dir.exists():
        return documents
    for path in sorted(upload_dir.iterdir()):
        if path.suffix.lower() == ".pdf":
            text = extract_pdf_text(path.read_bytes())
            title = path.stem.replace("_", " ")
            documents.append(
                {
                    "title": title,
                    "abstract": text[:2000] if len(text) > 2000 else text,
                    "authors": [],
                    "published": "",
                    "year": _guess_year_from_text(text),
                    "paper_id": "",
                    "category": "pdf",
                    "source": "uploaded",
                    "text": text or title,
                    "filename": path.name,
                }
            )
        elif path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            for doc in parse_patent_json(raw):
                doc["filename"] = path.name
                documents.append(doc)
    return documents


def _guess_year_from_text(text: str) -> int | None:
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", text[:5000])]
    return max(years) if years else None


def merge_corpus(scholar_docs: list[dict], uploaded_docs: list[dict]) -> list[dict]:
    seen = set()
    merged = []
    for doc in scholar_docs + uploaded_docs:
        key = doc.get("paper_id") or doc.get("doi") or doc.get("title", "")[:80]
        if key in seen:
            continue
        seen.add(key)
        merged.append(doc)
    return merged
