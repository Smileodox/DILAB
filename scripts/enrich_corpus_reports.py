"""Corpus enrichment (reports) — download curated public report PDFs into the TREND pool.

Targets the market & geopolitical buckets, which arXiv abstracts cannot fill (economics /
policy / national-security content lives in institutional reports, not preprints). Mechanism is
generic: download -> kb.extract_chunks (pymupdf) -> embed -> UPSERT with source_id + year
traceability. The URL list below is test-case config (kept in scripts/, not src/). The source-cap
in trends.py (MAX_CHUNKS_PER_SOURCE) keeps any large report from dominating the orphan pool.

Run:  uv run python scripts/enrich_corpus_reports.py
"""
from __future__ import annotations

import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.llm import embed
from src.models.common import stable_id
from src.pipeline.kb import extract_chunks
from src.rag import get_collection

PDF_DIR = "knowledge_base/pdfs/reports"

# (dimension, url, title, publisher, year) — public, directly-downloadable PDFs (verified 200/pdf).
REPORTS = [
    ("market", "https://www.oecd.org/content/dam/oecd/en/publications/reports/2022/10/developments-in-spectrum-management-for-communication-services_ae18e03f/175e7ce5-en.pdf",
     "OECD Developments in Spectrum Management for Communication Services (2022)", "OECD", "2022"),
    ("market", "https://www.oecd.org/content/dam/oecd/en/publications/reports/2014/05/new-approaches-to-spectrum-management_g17a2490/5jz44fnq066c-en.pdf",
     "OECD New Approaches to Spectrum Management (2014)", "OECD", "2014"),
    ("market", "https://www.gsma.com/connectivity-for-good/spectrum/wp-content/uploads/2022/01/mobile-spectrum-maximising-socio-economic-value.pdf",
     "GSMA Maximising the Socio-Economic Value of Spectrum (2022)", "GSMA", "2022"),
    ("market", "https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-economy/wp-content/uploads/2025/02/030325-The-Mobile-Economy-2025.pdf",
     "GSMA The Mobile Economy 2025", "GSMA", "2025"),
    ("market", "https://www.gsma.com/spectrum/wp-content/uploads/2013/06/Economic-Value-of-Spectrum-Use-in-Europe_Junev4.1.pdf",
     "GSMA Valuing the Use of Spectrum in the EU (2013)", "GSMA", "2013"),
    ("market", "https://www.ucm.es/data/cont/media/www/pag-131600/Impact-of-spectrum-prices-on-consumers-Technical-Report.pdf",
     "The Impact of Spectrum Prices on Consumers — Technical Report (2019)", "GSMA/Plum", "2019"),
    ("geopolitical", "https://www.ntia.gov/sites/default/files/publications/national_spectrum_strategy_final.pdf",
     "NTIA National Spectrum Strategy (2023)", "NTIA", "2023"),
    ("geopolitical", "https://www.ntia.gov/files/ntia/publications/s1059-full.pdf",
     "NTIA Assessment of Electromagnetic Spectrum Reallocation", "NTIA", "2022"),
    ("geopolitical", "https://www.airandspaceforces.com/app/uploads/2020/10/ELECTROMAGNETIC_SPECTRUM_SUPERIORITY_STRATEGY.pdf",
     "DoD Electromagnetic Spectrum Superiority Strategy (2020)", "US DoD", "2020"),
    ("geopolitical", "https://www.brookings.edu/wp-content/uploads/2020/04/FP_20200427_5g_competition_turner_lee_v2.pdf",
     "Brookings Navigating the US-China 5G Competition (2020)", "Brookings", "2020"),
]

_UA = {"User-Agent": "Mozilla/5.0 (dilab-foresight corpus enrichment)"}


def _download(url: str, dest: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as f:  # noqa: S310
        f.write(r.read())


def main():
    os.makedirs(PDF_DIR, exist_ok=True)
    col = get_collection()
    write = getattr(col, "upsert", None) or col.add
    total, per_dim = 0, {}

    for dim, url, title, publisher, year in REPORTS:
        fname = url.rsplit("/", 1)[-1].split("?")[0] or f"{stable_id(url)}.pdf"
        dest = os.path.join(PDF_DIR, fname)
        try:
            if not os.path.exists(dest):
                _download(url, dest)
        except Exception as e:  # noqa: BLE001
            print(f"[SKIP] download failed — {title}: {e}", flush=True)
            continue
        try:
            chunks = extract_chunks(dest)
        except Exception as e:  # noqa: BLE001
            print(f"[SKIP] extract failed — {title}: {e}", flush=True)
            continue
        if not chunks:
            print(f"[SKIP] no chunks — {title}", flush=True)
            continue

        sid = stable_id("report", url)
        ids, metas = [], []
        for text in chunks:
            ids.append(stable_id(sid, text[:200]))
            metas.append({"source_id": sid, "source_title": title, "pool": "trend",
                          "section": dim, "publisher": publisher, "year": year})
        for s in range(0, len(chunks), 64):  # batch embeds (Azure per-request limit)
            sl = slice(s, s + 64)
            write(ids=ids[sl], embeddings=embed(chunks[sl]), documents=chunks[sl], metadatas=metas[sl])

        print(f"[{dim:13s}] +{len(chunks):4d} chunks  {title}", flush=True)
        per_dim[dim] = per_dim.get(dim, 0) + len(chunks)
        total += len(chunks)

    print(f"\nTotal added: {total} chunks  |  per dimension: {per_dim}")


if __name__ == "__main__":
    main()
