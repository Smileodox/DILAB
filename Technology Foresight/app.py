"""Technology Foresight — Flask application."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

load_dotenv()

from pipeline.hf_cache import configure_hf_cache

configure_hf_cache()

from pipeline.ingest import (
    ScholarError,
    fetch_scholar_preview,
    get_cached_scholar,
    ingest_uploaded_files,
    merge_corpus,
    parse_foresight_query,
)
from pipeline.runner import run_pipeline
from storage.graph_store import (
    job_dir,
    load_corpus,
    load_progress,
    load_result,
    save_corpus,
    save_job_meta,
    save_progress,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scholar/preview", methods=["POST"])
def scholar_preview():
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()
    max_results = int(data.get("max_results") or 20)
    if not query:
        return jsonify({"error": "Query required"}), 400
    try:
        papers, api_query = fetch_scholar_preview(query, max_results)
        return jsonify(
            {
                "papers": [
                    {
                        "title": p["title"],
                        "paper_id": p.get("paper_id"),
                        "year": p.get("year"),
                        "category": p.get("category"),
                    }
                    for p in papers
                ],
                "count": len(papers),
                "api_query": api_query,
            }
        )
    except ScholarError as e:
        return jsonify({"error": str(e), "query": query}), 422
    except Exception as e:
        return jsonify({"error": f"Semantic Scholar fetch failed: {e}"}), 500


@app.route("/api/jobs/create", methods=["POST"])
def create_job():
    """Accept uploads + optional Semantic Scholar snapshot; return job_id."""
    job_id = uuid.uuid4().hex[:12]
    upload_path = job_dir(job_id)

    scholar_docs = []
    scholar_query = (request.form.get("scholar_query") or "").strip()
    if scholar_query:
        try:
            max_results = int(request.form.get("scholar_max_results") or 20)
            use_cache_only = request.form.get("scholar_use_cache") == "1"
            cached = get_cached_scholar(scholar_query, max_results)
            if cached:
                scholar_docs, _ = cached
            else:
                scholar_docs, _ = fetch_scholar_preview(
                    scholar_query, max_results, use_cache_only=use_cache_only
                )
        except ScholarError as e:
            return jsonify({"error": str(e), "query": scholar_query}), 422
        except Exception as e:
            return jsonify({"error": f"Semantic Scholar fetch failed: {e}"}), 500

    for f in request.files.getlist("files"):
        if f and f.filename:
            dest = upload_path / f.filename
            f.save(dest)

    uploaded_docs = ingest_uploaded_files(upload_path)
    corpus = merge_corpus(scholar_docs, uploaded_docs)

    if not corpus:
        return jsonify({"error": "No documents provided. Upload PDF/JSON or fetch papers from Semantic Scholar."}), 400

    foresight = parse_foresight_query(scholar_query) if scholar_query else {}
    save_job_meta(
        job_id,
        {
            "scholar_query": scholar_query,
            "foresight": foresight,
            "document_count": len(corpus),
        },
    )
    save_corpus(job_id, corpus)
    save_progress(job_id, "ready", 0, "Ready to run analysis")
    return jsonify({"job_id": job_id, "document_count": len(corpus)})


@app.route("/api/progress/<job_id>")
def progress(job_id):
    return jsonify(load_progress(job_id))


@app.route("/run/<job_id>", methods=["POST"])
def run_analysis(job_id):
    corpus = load_corpus(job_id)
    if not corpus:
        return jsonify({"error": "Job not found or empty corpus"}), 404
    try:
        run_pipeline(job_id, corpus)
    except Exception as e:
        save_progress(job_id, "error", 0, f"Error: {e}")
        return jsonify({"error": str(e)}), 500
    return redirect(url_for("dashboard", job_id=job_id))


@app.route("/dashboard/<job_id>")
def dashboard(job_id):
    result = load_result(job_id)
    if not result:
        return redirect(url_for("index"))
    return render_template("dashboard.html", job_id=job_id, result_json=json.dumps(result))


if __name__ == "__main__":
    import os

    Path("uploads").mkdir(exist_ok=True)
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port, use_reloader=False)
