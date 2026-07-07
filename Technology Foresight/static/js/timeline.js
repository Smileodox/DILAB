function initTimeline(result) {
  const evo = result.evolution || {};
  document.getElementById("timeline-why").textContent = evo.why || "";

  const timeline = evo.timeline || {};
  const clusters = result.clusters || [];
  const traces = Object.keys(timeline).map((tid) => {
    const series = timeline[tid];
    const label = clusters.find((c) => String(c.topic_id) === tid)?.label || `Topic ${tid}`;
    return {
      x: series.map((p) => p.year),
      y: series.map((p) => p.count),
      mode: "lines+markers",
      name: label,
      type: "scatter",
    };
  });

  Plotly.newPlot(
    document.getElementById("evolution-chart"),
    traces.length ? traces : [{ x: [2020], y: [0], mode: "markers", name: "No data" }],
    {
      paper_bgcolor: "#F8F9FC",
      plot_bgcolor: "#fff",
      margin: { t: 24, r: 24, b: 48, l: 48 },
      xaxis: { title: "Year", dtick: 1 },
      yaxis: { title: "Publications" },
      font: { family: "DM Sans, sans-serif" },
      legend: { orientation: "h", y: -0.2 },
    },
    { responsive: true, displayModeBar: false }
  );

  const eventsList = document.getElementById("change-events-list");
  eventsList.innerHTML = "";
  (evo.events || []).forEach((ev) => {
    const card = document.createElement("div");
    card.className = "event-card";
    const kws = (ev.keywords || []).slice(0, 6).map((k) => `<span class="keyword-pill">${k}</span>`).join(" ");
    card.innerHTML = `
      <div class="event-header">
        <span class="event-badge ${ev.type}">${ev.type}</span>
        <strong>Topic ${ev.topic_id}</strong>
        <span class="muted">${ev.year || ""}</span>
      </div>
      <p class="muted" style="margin:0.5rem 0">${ev.why || ""}</p>
      <div class="keyword-row">${kws}</div>
      <div class="llm-box">${ev.llm_explanation || ""}${ev.llm_source === "contextual_fallback" ? '<br><span class="muted" style="font-size:0.7rem">Rule-based explanation (LLM unavailable)</span>' : ""}</div>`;
    eventsList.appendChild(card);
  });

  const weakList = document.getElementById("weak-signals-list");
  weakList.innerHTML = "";
  (evo.weak_signals || []).forEach((sig) => {
    const div = document.createElement("div");
    div.className = "weak-signal-item";
    div.innerHTML = `
      <strong>${sig.label}</strong>
      <span class="pill">growth ×${sig.growth_rate}</span>
      <p class="muted">${sig.why}</p>
      <div class="keyword-row">${(sig.keywords || []).map((k) => `<span class="keyword-pill">${k}</span>`).join("")}</div>`;
    weakList.appendChild(div);
  });
}

function initReasoning(result) {
  const reasoning = result.reasoning || {};
  document.getElementById("influence-why").textContent = reasoning.why_influence || "";

  const list = document.getElementById("influence-list");
  list.innerHTML = "";
  (reasoning.influence || []).forEach((edge) => {
    const row = document.createElement("div");
    row.className = "influence-row";
    row.innerHTML = `
      <span class="tech-name">${edge.from}</span>
      <span class="relation-pill">${edge.relation} →</span>
      <span>
        <span class="tech-name">${edge.to}</span>
        <p class="muted" style="margin:0.35rem 0 0">${edge.reason}</p>
      </span>`;
    list.appendChild(row);
  });

  const saoWrap = document.getElementById("sao-groups");
  saoWrap.innerHTML = "";
  const sao = reasoning.sao || {};
  Object.keys(sao).forEach((tid) => {
    const group = sao[tid];
    const cluster = (result.clusters || []).find((c) => String(c.topic_id) === tid);
    const div = document.createElement("div");
    div.className = "sao-topic";
    const actions = (group.dominant_actions || [])
      .map((a) => `<span class="keyword-pill">${a.action} (${a.count})</span>`)
      .join("");
    const triples = (group.triples || [])
      .slice(0, 8)
      .map(
        (t) =>
          `<span class="keyword-pill">${t.subject}</span> → <span class="keyword-pill">${t.action}</span> → <span class="keyword-pill">${t.object || "—"}</span>`
      )
      .join("<br>");
    div.innerHTML = `
      <h3>${cluster?.label || `Topic ${tid}`}</h3>
      <p class="muted">${group.why || ""}</p>
      <p><strong>Dominant actions:</strong> ${actions}</p>
      <div>${triples}</div>`;
    saoWrap.appendChild(div);
  });
}

window.initTimeline = initTimeline;
window.initReasoning = initReasoning;
