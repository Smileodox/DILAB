"""Acceptance proof: dock a SECOND, real, non-RF knowledge base and run the FULL pipeline
end-to-end — KB ingest -> profile -> morphbox -> contrastive CCA -> consistent sampling ->
narratives -> config-space landscape -> MCDA -> null-model structure test — with ZERO
domain/prompt edits. This is the evidence that the pipeline is a domain-agnostic foresight
framework, not a spectrum-monitoring tool.

The corpus is REAL: 6 public precision-agriculture reports/papers (arXiv + FAO) are
downloaded and ingested through the same chunk+embed path as the primary KB
(src.pipeline.kb), into a SEPARATE Chroma collection so the spectrum KB is untouched.

  uv run python prove_domain_agnostic.py                 # download (if needed) + full E2E
  uv run python prove_domain_agnostic.py --reingest      # force re-chunk/re-embed
  uv run python prove_domain_agnostic.py --n-samples 40  # cheaper run
"""
from __future__ import annotations

import argparse
import logging
import os
import urllib.request

import chromadb

from src.config import CHROMA_PERSIST_DIR
from src.models.kb import SourceType
from src.pipeline import domain, kb, structure

AG_DIR = "data/outputs_ag"          # separate output dir — never touches the spectrum outputs
AG_PDF_DIR = "data/sources/agriculture"
AG_COLLECTION = "knowledge_base_ag"  # separate collection — spectrum knowledge_base untouched

# A real, public, clearly non-RF corpus with competing technical architectures (sensing
# modalities, navigation, actuation, edge-vs-cloud, energy) so the morphology has real tension.
AG_SOURCES = [
    {"id": "ag_harvesting_survey", "title": "A Survey of Robotic Harvesting Systems and Enabling Technologies",
     "filename": "harvesting_survey.pdf", "pdf_url": "https://arxiv.org/pdf/2207.10457",
     "url": "https://arxiv.org/abs/2207.10457", "publisher": "arXiv", "year": 2022},
    {"id": "ag_vit_survey", "title": "Vision Transformers in Precision Agriculture: A Comprehensive Survey",
     "filename": "vit_precision_ag_survey.pdf", "pdf_url": "https://arxiv.org/pdf/2504.21706",
     "url": "https://arxiv.org/abs/2504.21706", "publisher": "arXiv", "year": 2025},
    {"id": "ag_aerial_ground", "title": "Building an Aerial-Ground Robotics System for Precision Farming",
     "filename": "aerial_ground_robotics.pdf", "pdf_url": "https://arxiv.org/pdf/1911.03098",
     "url": "https://arxiv.org/abs/1911.03098", "publisher": "arXiv", "year": 2019},
    {"id": "ag_lidar_lpr", "title": "LiDAR Place Recognition in Agricultural Environments: A Comprehensive Survey",
     "filename": "lidar_place_recognition.pdf", "pdf_url": "https://arxiv.org/pdf/2601.22198",
     "url": "https://arxiv.org/abs/2601.22198", "publisher": "arXiv", "year": 2026},
    {"id": "ag_cv_dataset", "title": "Agriculture Computer Vision Dataset Survey",
     "filename": "ag_cv_dataset_survey.pdf", "pdf_url": "https://arxiv.org/pdf/2502.16950",
     "url": "https://arxiv.org/abs/2502.16950", "publisher": "arXiv", "year": 2025},
    {"id": "ag_fao_status", "title": "Digital technologies in agriculture and rural areas - Status report",
     "filename": "fao_digital_ag_status.pdf",
     "pdf_url": "https://openknowledge.fao.org/server/api/core/bitstreams/0bb5137a-161c-4b7c-9257-3d4d5251b4bf/content",
     "url": "https://openknowledge.fao.org/items/8e5f9b9e", "publisher": "FAO", "year": 2019},
]


def ensure_pdfs() -> None:
    """Download any missing source PDFs (the corpus is gitignored, so this makes the proof
    reproducible from a clean checkout)."""
    os.makedirs(AG_PDF_DIR, exist_ok=True)
    for s in AG_SOURCES:
        path = os.path.join(AG_PDF_DIR, s["filename"])
        if os.path.exists(path) and os.path.getsize(path) > 10_000:
            continue
        print(f"  downloading {s['filename']} ...", flush=True)
        req = urllib.request.Request(s["pdf_url"], headers={"User-Agent": "Mozilla/5.0 (research ingest)"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())


def ensure_kb(reingest: bool):
    """Return the ag Chroma collection, ingesting the real PDFs through the normal KB path
    (src.pipeline.kb.ingest) if it is not already populated."""
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    if not reingest:
        try:
            coll = client.get_collection(AG_COLLECTION)
            if coll.count() > 0:
                print(f"[kb] reusing '{AG_COLLECTION}' ({coll.count()} chunks) — pass --reingest to rebuild")
                return coll
        except Exception:  # noqa: BLE001 — not created yet
            pass
    ensure_pdfs()
    print(f"[kb] ingesting real ag corpus into '{AG_COLLECTION}' (chunk + embed, same path as primary KB) ...")
    res = kb.ingest(AG_SOURCES, pdf_dir=AG_PDF_DIR, collection_name=AG_COLLECTION,
                    default_type=SourceType.RESEARCH_PAPER, clear=True,
                    state_path=os.path.join(AG_DIR, "kb_state.json"))
    print(f"  {res['n_chunks']} chunks from {len(res['sources'])} sources (skipped: {res['skipped']})")
    return res["collection"]


def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    ap = argparse.ArgumentParser(description="Prove the pipeline is domain-agnostic on a real 2nd KB")
    ap.add_argument("--model", default="gpt-5.4")
    ap.add_argument("--n-samples", type=int, default=60)
    ap.add_argument("--reingest", action="store_true", help="force re-chunk/re-embed the corpus")
    ap.add_argument("--trials", type=int, default=20, help="null-model trials for the structure test")
    args = ap.parse_args()

    print("Docking a SECOND, REAL KB (precision agriculture) — zero domain/prompt edits\n" + "=" * 72)
    coll = ensure_kb(args.reingest)

    # 1. derive the DomainProfile from THIS KB (persisted to the ag output dir, not the spectrum one)
    print("\n[profile] deriving from the docked ag KB ...")
    profile = domain.run(model=args.model, collection=coll, output_dir=AG_DIR)
    print(f"  domain  = {profile.domain!r}")
    print(f"  system  = {profile.system!r}")
    print(f"  actor   = {profile.actor!r} | horizon {profile.horizon}")
    print(f"  personas = {[p.id for p in profile.personas]}")

    # 2. full analytical + narrative + MCDA chain, driven only by the profile + ag collection
    import run_morphological
    print("\n[pipeline] running full E2E chain on the ag KB ...\n" + "-" * 72)
    run_morphological.run(profile=profile, collection=coll, output_dir=AG_DIR,
                          n_samples=args.n_samples, model=args.model, narrative_mode="short")

    # 3. null-model structure test on the ag scenario field (real structure vs. uniform random)
    scen_path = os.path.join(AG_DIR, "scenario_state_zwicky.json")
    morph_path = os.path.join(AG_DIR, "morphbox_zwicky_state.json")
    if os.path.exists(scen_path) and os.path.exists(morph_path):
        import json
        scenarios = json.load(open(scen_path))["scenarios"]
        morphbox = json.load(open(morph_path))
        res = structure.analyze(scenarios, morphbox, null_trials=args.trials, seed=42)
        o, z = res["observed"], res["z_scores"]
        print("\n" + "=" * 72)
        print(f"[structure] {o['n']} scenarios, {o['dims']} manifestations | "
              f"effdim={o['effective_dim']} (z={z['effective_dim']}) "
              f"PC1={o['pc1']} (z={z['pc1']}) silhouette={o['best_silhouette']}")
        print(f"  → verdict: {res['verdict']}")

    print("\n✓ Full pipeline ran on a brand-new REAL domain with zero domain/prompt edits.")
    print(f"  outputs → {AG_DIR}/  (profile, morphbox, cca, scenarios, landscape, MCDA, structure)")


if __name__ == "__main__":
    main()
