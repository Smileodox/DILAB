# Knowledge base — Regulatory Spectrum Monitoring

This directory is the seed corpus for the **Technology Foresight** pipeline that the
student team is building. It is intentionally separate from the existing
`foresight.py` / `generate_report.py` code (which uses a hosted LLM) and has **no
dependency** on it — students can ingest these PDFs into any local-LLM RAG
pipeline they like (Ollama / llama.cpp / vLLM, with LangChain, LlamaIndex,
Haystack, or plain custom code).

## What is in here

This folder contains **no PDFs** — only the URLs, metadata, and a downloader.
Each student runs `fetch.py` on their own machine to populate `pdfs/`
(~80 MB total). The corpus is therefore cheap to ship and trivially
reproducible.

- **`sources.json`** — the master manifest (32 entries: regulators, standards
  bodies, EU/OECD strategy, academic surveys, security, measurement
  frameworks). Every PDF has provenance metadata: `id`, `title`, `publisher`,
  `year`, `url`, `landing_page` (when relevant), `category`, `filename`, and a
  one-paragraph `why_relevant` field.
- **`sources_rs.json`** — optional supplementary manifest (15 entries) with
  Rohde & Schwarz vendor literature describing the full technology system
  (antennas → receivers → direction finders → software). Vendor-biased — use
  it for system-architecture coverage, but cross-check claims against
  `sources.json`. Categories J–P are reserved for this manifest.
- **`urls.md`** / **`urls_rs.md`** — share-ready, human-readable URL lists
  generated from the corresponding `sources*.json`. Regenerate with
  `python make_urls_md.py`.
- **`fetch.py`** — idempotent downloader. Uses only the standard library
  (`certifi` if available); records SHA-256, byte size, HTTP status, and a
  timestamp for every file in `fetch_report.json` and produces `manifest.md`
  (both are generated, not version-controlled). Automatically picks up every
  `sources*.json` in this directory; use `--manifest sources.json` to restrict.
- **`manual_downloads.md`** — checklist of the 5 PDFs that cannot be retrieved
  by the script (publisher uses Cloudflare bot-protection, or a TLS cert chain
  that Python does not validate). Open these URLs in a normal browser, save
  with the exact filename listed, drop them into `pdfs/`, then re-run
  `python fetch.py` to register them (it will hash them and mark them OK).
- **`make_urls_md.py`** — regenerates `urls.md` from `sources.json`.

## Quick start (for a student)

```bash
cd knowledge_base
python fetch.py
# Default: downloads from BOTH sources.json (32) and sources_rs.json (15).
# 41 of 47 PDFs download automatically (~135 MB).
# 6 need a browser - see manual_downloads.md.

# Or restrict to one corpus:
python fetch.py --manifest sources.json       # neutral corpus only (32)
python fetch.py --manifest sources_rs.json    # R&S vendor corpus only (15)
```

After the script finishes you will have:

- `pdfs/` — the corpus.
- `fetch_report.json` — machine-readable record (the **traceability artefact**
  for step 1: every PDF is bound to URL + publisher + year + SHA-256 + fetch
  timestamp).
- `manifest.md` — human-readable summary.

`fetch.py` flags:

- `python fetch.py --force` — re-download everything.
- `python fetch.py --only A` — only the canonical ITU set.
- `python fetch.py --only F` — only the academic AI/ML surveys, etc.

## Categories (and what they buy you in step 1)

`sources.json` (neutral corpus):

| Prefix | Theme | Drivers it helps you identify |
|---|---|---|
| **A** | ITU canonical (handbook, WRC-23 Final Acts, SM.2542 next-gen monitoring) | The vocabulary of the discipline; what the world has agreed to monitor and protect; the ITU-stamped "next generation" agenda |
| **B** | Regional regulators (Ofcom, BNetzA, CEPT/ECC) | National/regional priorities, automation, data harmonisation, enforcement |
| **C** | US regulators (FCC, NTIA) | National spectrum strategy, federal/non-federal sharing, automation |
| **D** | EU strategy (RSPG opinions) | 6G vision, UHF beyond 2030, EU digital sovereignty |
| **E** | Industry / international (GSMA, OECD) | Commercial spectrum demand and the regulator-of-the-future debate |
| **F** | Academic AI/ML surveys (arXiv) | AI/ML, AMR, RF fingerprinting, cognitive radio, sharing |
| **G** | Distributed / UAV sensing (arXiv) | Crowdsourced sensing, anomaly detection, UAV-based 3D measurement |
| **H** | Security (ENISA) | Cybersecurity of the radio infrastructure being monitored |
| **I** | Measurement frameworks (NIST/NASCTN CBRS) | Concrete operational sharing-monitoring at scale |

`sources_rs.json` (Rohde & Schwarz vendor corpus, optional):

| Prefix | Theme | Drivers it helps you identify |
|---|---|---|
| **J** | R&S system-level white papers (modern monitoring vision, hybrid AOA/TDOA, DF methodologies, BNetzA DDF550 case) | What "a full system" looks like end-to-end; how a national rollout actually happens |
| **K** | R&S monitoring receivers (ESMW, EM200, PR200) | The receiver sub-system: SDR, real-time bandwidth, distributed deployments, portable use |
| **L** | R&S direction finders / outdoor locators (DDF550, UMS300) | Precision geolocation; combined sensor + locator nodes |
| **M** | R&S antennas (active-antenna portfolio) | The antenna sub-system across HF to microwave |
| **N** | R&S software (ARGUS, CEPTOR, GSACSM) | The software-system axis: workflows, automatic classification, satellite monitoring |
| **P** | R&S application notes (1EF77 real-time spectrum analysis) | Enabling DSP techniques (POI, FMT, persistence) under the receivers |

## How this connects to the pipeline

The pipeline the team is building is:

> 0) Pick a field of interest →
> 1) Identify technology drivers →
> 2) Make 5–10 year assumptions about how each driver may evolve →
> 3) Generate plausible scenarios →
> 4) Cluster and evaluate scenarios.

This corpus is the **input to step 1**.

A recommended scalable, local-LLM workflow:

1. **Chunk + embed** every PDF in `pdfs/` with a local embedding model
   (e.g. `bge-small-en`, `nomic-embed-text` via Ollama). Keep the chunk →
   source-`id` mapping so every later claim is citable back to a `sources.json`
   entry — that is the traceability requirement.
2. **Cluster the chunks** by topic (k-means / HDBSCAN on the embeddings, or a
   topic model). Each cluster is a candidate driver family.
3. For each cluster, prompt a local LLM (e.g. `llama-3.1-8b-instruct`,
   `qwen2.5-7b-instruct`, `mistral-7b`) with the top-N representative chunks and
   ask: *"Summarise this cluster as one technology driver for regulatory spectrum
   monitoring over the next 5–10 years. Output: short name, one-paragraph
   description, supporting source ids."*
4. **De-duplicate and rank** the resulting drivers (semantic similarity +
   evidence count across sources). Aim for 8–15 distinct drivers.
5. Persist the result as a `drivers.json` in the **same schema** as
   `../config/drivers.json` so that the existing `foresight.py` could in
   principle consume it, but the team is free to use their own downstream
   tooling.

## Traceability & scalability checklist

Use these as acceptance criteria for step 1:

- Every driver produced by the pipeline cites at least **2 distinct sources**
  from `sources.json` (by `id`), with page or chunk references.
- The pipeline can be re-run end-to-end from `sources.json` (URLs + hashes) →
  `drivers.json` with **no manual editing** of intermediate files.
- The pipeline is parameterised on the embedding model, the LLM, and the
  clustering algorithm, so swapping a 7B model for a 70B model (or a different
  local provider) is a config change.
- All prompts used are stored in version control (so a re-run on the same model
  weights is reproducible up to LLM non-determinism — record `temperature`,
  `seed`, model name and revision).
- `fetch_report.json` shows the SHA-256 of every input PDF, so a corpus update
  is detectable (driver-identification can be re-run only on changed inputs).

## Licences

Every PDF is the intellectual property of its respective publisher. The
manifest stores only URLs and metadata. Before any redistribution, check the
copyright statement on the publisher's landing page. The corpus is fine for
**internal student-team use** (reading, RAG indexing, model evaluation); ask
each publisher before publishing derivative works.

## Adding sources

To extend the corpus:

1. Add a new entry to `sources.json`. Required fields: `id`, `category`,
   `title`, `publisher`, `year`, `url`, `filename`, `why_relevant`. Optional:
   `landing_page`, `arxiv_id`, `manual_download`, `manual_reason`.
2. Use a descriptive `id` matching the naming convention `<CATEGORY><NN>_<slug>`
   (e.g. `F07_arxiv_new_survey_2026`).
3. Run `python fetch.py --only <id>`.
4. Commit `sources.json`, the new PDF (or note it in `manual_downloads.md`),
   and the updated `fetch_report.json` + `manifest.md`.
