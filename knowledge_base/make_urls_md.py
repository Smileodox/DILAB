"""
Regenerate one urls*.md per sources*.json manifest in this directory.

Naming:
    sources.json     -> urls.md
    sources_rs.json  -> urls_rs.md
    sources_xyz.json -> urls_xyz.md

Run after editing any manifest:
    python make_urls_md.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def render(doc: dict, out_path: Path) -> None:
    sources = doc["sources"]
    cats = doc.get("categories", {})

    by_cat: dict[str, list[dict]] = {}
    for s in sources:
        by_cat.setdefault(s["category"], []).append(s)

    auto = [s for s in sources if not s.get("manual_download")]
    manual = [s for s in sources if s.get("manual_download")]

    lines: list[str] = []
    lines += [
        f"# {doc['field_of_interest']} - source URL list",
        "",
        f"{len(sources)} publicly available PDFs total ({len(auto)} downloadable by "
        f"`fetch.py`, {len(manual)} requiring a manual browser download).",
        "",
        "Each entry: target filename (drop the file under `pdfs/<filename>`), URL.",
        "",
    ]
    if doc.get("vendor_bias_note"):
        lines += [f"> **Vendor-bias note.** {doc['vendor_bias_note']}", ""]

    for cat_id in sorted(by_cat):
        cat_desc = cats.get(cat_id, cat_id)
        lines.append(f"## {cat_id} - {cat_desc}")
        lines.append("")
        for s in by_cat[cat_id]:
            tag = "  (MANUAL)" if s.get("manual_download") else ""
            lines.append(f"- **{s['id']}**{tag} - {s.get('title','')}")
            lines.append(f"  - publisher: {s.get('publisher','')} ({s.get('year','')})")
            lines.append(f"  - file: `pdfs/{s['filename']}`")
            lines.append(f"  - URL: <{s['url']}>")
            if s.get("landing_page"):
                lines.append(f"  - landing page: <{s['landing_page']}>")
            lines.append("")
        lines.append("")

    lines += [
        "## Plain URL list (one per line, in `id` order)",
        "",
        "```",
    ]
    for s in sources:
        lines.append(s["url"])
    lines += ["```", ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    manifests = sorted(HERE.glob("sources*.json"))
    if not manifests:
        raise SystemExit(f"no sources*.json files found in {HERE}")
    for mf in manifests:
        doc = json.loads(mf.read_text(encoding="utf-8"))
        suffix = mf.stem[len("sources"):]  # "" for sources.json, "_rs" for sources_rs.json
        out = HERE / f"urls{suffix}.md"
        render(doc, out)
        print(f"Wrote {out.name} from {mf.name} ({len(doc['sources'])} sources)")


if __name__ == "__main__":
    main()
