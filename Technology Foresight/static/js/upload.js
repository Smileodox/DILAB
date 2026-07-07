(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const combinedPreview = document.getElementById("combined-preview");
  const emptyPreview = document.getElementById("empty-preview");
  const scholarPreviewList = document.getElementById("scholar-preview-list");
  const scholarStatus = document.getElementById("scholar-status");
  const scholarQueryInput = document.getElementById("scholar-query");
  const scholarCountInput = document.getElementById("scholar-count");
  const runBtn = document.getElementById("run-btn");
  const progressWrap = document.getElementById("progress-wrap");
  const progressBar = document.getElementById("progress-bar");
  const progressLabel = document.getElementById("progress-label");
  const progressPct = document.getElementById("progress-pct");
  const progressSteps = document.querySelectorAll(".progress-steps li");

  let localFiles = [];
  let scholarPapers = [];
  let scholarFetchedForQuery = "";
  let scholarFetchedForCount = 0;
  let jobId = null;

  function getScholarQuery() {
    return scholarQueryInput.value.trim();
  }

  function getScholarMaxResults() {
    const n = parseInt(scholarCountInput.value, 10);
    return Math.min(100, Math.max(1, n || 20));
  }

  function setScholarStatus(message, type = "info") {
    if (!scholarStatus) return;
    scholarStatus.textContent = message;
    scholarStatus.className = `scholar-status scholar-status-${type}`;
    scholarStatus.classList.toggle("hidden", !message);
  }

  function updatePreview() {
    const items = [];
    localFiles.forEach((f) => {
      items.push({ title: f.name, source: "uploaded" });
    });
    scholarPapers.forEach((p) => {
      items.push({ title: p.title, source: "scholar" });
    });

    combinedPreview.innerHTML = "";
    scholarPreviewList.innerHTML = "";

    const hasQuery = !!getScholarQuery();
    const canRun = items.length > 0 || hasQuery;

    if (!canRun) {
      emptyPreview.classList.remove("hidden");
      runBtn.disabled = true;
      return;
    }
    emptyPreview.classList.add("hidden");
    runBtn.disabled = false;

    items.forEach((item) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${escapeHtml(item.title)}</span><span class="pill">${item.source}</span>`;
      combinedPreview.appendChild(li);
    });

    if (!items.length && hasQuery) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="muted">Semantic Scholar papers will be fetched on Run Analysis: «${escapeHtml(getScholarQuery())}»</span><span class="pill">scholar</span>`;
      combinedPreview.appendChild(li);
    }

    scholarPapers.forEach((p) => {
      const li = document.createElement("li");
      const meta = [p.paper_id, p.year, p.category].filter(Boolean).join(" · ");
      li.innerHTML = `<span>${escapeHtml(p.title)}</span>${meta ? `<span class="muted" style="font-size:0.75rem">${escapeHtml(meta)}</span>` : ""}`;
      scholarPreviewList.appendChild(li);
    });
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  async function fetchScholarPreview() {
    const query = getScholarQuery();
    const maxResults = getScholarMaxResults();
    if (!query) {
      setScholarStatus("Enter a search query first.", "error");
      return false;
    }

    const btn = document.getElementById("scholar-fetch-btn");
    if (btn.dataset.busy === "1") return false;
    btn.dataset.busy = "1";
    btn.disabled = true;
    btn.textContent = "Fetching…";
    setScholarStatus("Searching Semantic Scholar — please wait…", "info");

    try {
      const res = await fetch("/api/scholar/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, max_results: maxResults }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data.error || (res.status === 422 ? "No papers matched your topic." : "Fetch failed");
        throw new Error(msg);
      }

      scholarPapers = data.papers || [];
      scholarFetchedForQuery = query.toLowerCase();
      scholarFetchedForCount = maxResults;
      setScholarStatus(
        `Found ${data.count} paper(s). Cached — Run Analysis will reuse these results.`,
        "success"
      );
      updatePreview();
      return true;
    } catch (err) {
      scholarPapers = [];
      scholarFetchedForQuery = "";
      scholarFetchedForCount = 0;
      const msg = err.message || "Fetch failed";
      const rateLimited = /rate.?limit|429|busy|wait/i.test(msg);
      setScholarStatus(
        rateLimited
          ? `${msg} Use Fetch preview once, wait 1–2 minutes, then run analysis.`
          : msg,
        "error"
      );
      updatePreview();
      return false;
    } finally {
      btn.disabled = false;
      btn.dataset.busy = "0";
      btn.textContent = "Fetch preview";
    }
  }

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    localFiles = [...localFiles, ...e.dataTransfer.files];
    updatePreview();
  });
  fileInput.addEventListener("change", () => {
    localFiles = [...localFiles, ...fileInput.files];
    updatePreview();
  });

  function clearScholarCache() {
    scholarPapers = [];
    scholarFetchedForQuery = "";
    scholarFetchedForCount = 0;
  }

  scholarQueryInput.addEventListener("input", () => {
    if (getScholarQuery().toLowerCase() !== scholarFetchedForQuery) {
      clearScholarCache();
    }
    updatePreview();
  });
  scholarCountInput.addEventListener("input", () => {
    if (getScholarMaxResults() !== scholarFetchedForCount) {
      clearScholarCache();
    }
    updatePreview();
  });

  document.getElementById("scholar-fetch-btn").addEventListener("click", fetchScholarPreview);

  const STAGE_ORDER = ["ingesting", "embedding", "clustering", "evolution", "reasoning", "scenarios", "done"];

  function setStepActive(stage) {
    const idx = STAGE_ORDER.indexOf(stage);
    progressSteps.forEach((li, i) => {
      li.classList.remove("active", "done");
      if (i < idx) li.classList.add("done");
      if (i === idx) li.classList.add("active");
    });
  }

  async function pollProgress(id) {
    const res = await fetch(`/api/progress/${id}`);
    const p = await res.json();
    progressBar.style.width = `${p.percent || 0}%`;
    progressLabel.textContent = p.label || "";
    progressPct.textContent = `${p.percent || 0}%`;
    if (p.stage) setStepActive(p.stage);
    return p;
  }

  runBtn.addEventListener("click", async () => {
    const query = getScholarQuery();
    if (!localFiles.length && !query && !scholarPapers.length) {
      alert("Upload files or enter a Semantic Scholar search query.");
      return;
    }

    runBtn.disabled = true;
    progressWrap.classList.remove("hidden");

    const form = new FormData();
    localFiles.forEach((f) => form.append("files", f));
    if (query) {
      form.append("scholar_query", query);
      form.append("scholar_max_results", String(getScholarMaxResults()));
      if (
        scholarFetchedForQuery &&
        scholarFetchedForQuery === query.toLowerCase() &&
        scholarFetchedForCount === getScholarMaxResults() &&
        scholarPapers.length > 0
      ) {
        form.append("scholar_use_cache", "1");
      }
    }

    try {
      const createRes = await fetch("/api/jobs/create", { method: "POST", body: form });
      const createData = await createRes.json();
      if (!createRes.ok) throw new Error(createData.error || "Job creation failed");
      jobId = createData.job_id;

      const pollId = setInterval(async () => {
        const p = await pollProgress(jobId);
        if (p.stage === "done" || p.stage === "error") clearInterval(pollId);
      }, 800);

      const runRes = await fetch(`/run/${jobId}`, { method: "POST", redirect: "follow" });
      clearInterval(pollId);
      if (runRes.redirected) {
        window.location.href = runRes.url;
      } else if (runRes.ok) {
        window.location.href = `/dashboard/${jobId}`;
      } else {
        const err = await runRes.json().catch(() => ({}));
        throw new Error(err.error || "Pipeline failed");
      }
    } catch (err) {
      alert(err.message);
      runBtn.disabled = false;
    }
  });

  updatePreview();
})();
