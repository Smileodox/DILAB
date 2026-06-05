function initClusterMap(result) {
  const scatterWhy = document.getElementById("scatter-why");
  const panel = document.getElementById("cluster-side-panel");
  const points = result.scatter?.points || [];
  const clusters = result.clusters || [];

  scatterWhy.textContent = result.scatter?.why || "";

  const palette = [
    "#2563EB", "#22C55E", "#F59E0B", "#EF4444", "#9333EA",
    "#06B6D4", "#EC4899", "#84CC16", "#F97316", "#6366F1",
  ];
  const topicIds = [...new Set(points.map((p) => p.topic_id))];
  const colorMap = {};
  topicIds.forEach((id, i) => {
    colorMap[id] = palette[i % palette.length];
  });

  const traces = topicIds.map((tid) => {
    const pts = points.filter((p) => p.topic_id === tid);
    const c = clusters.find((x) => x.topic_id === tid);
    return {
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      mode: "markers",
      type: "scatter",
      name: c?.label || `Topic ${tid}`,
      marker: { size: 10, color: colorMap[tid], opacity: 0.85 },
      text: pts.map(
        (p) =>
          `${p.title || p.preview}<br>Source: ${p.source}<br>Year: ${p.year || "n/a"}`
      ),
      hoverinfo: "text",
      customdata: pts.map((p) => ({ topic_id: tid })),
    };
  });

  const layout = {
    paper_bgcolor: "#F8F9FC",
    plot_bgcolor: "#ffffff",
    margin: { t: 24, r: 24, b: 48, l: 48 },
    xaxis: { title: "UMAP-1", zeroline: false },
    yaxis: { title: "UMAP-2", zeroline: false },
    legend: { orientation: "h", y: -0.15 },
    font: { family: "DM Sans, sans-serif" },
  };

  const el = document.getElementById("cluster-scatter");
  Plotly.newPlot(el, traces, layout, { responsive: true, displayModeBar: false });

  el.on("plotly_click", (ev) => {
    const tid = ev.points[0]?.customdata?.topic_id ?? ev.points[0]?.data?.name;
    const topicId = typeof tid === "object" ? tid.topic_id : parseInt(String(tid).replace(/\D/g, ""), 10);
    showClusterPanel(clusters.find((c) => c.topic_id === topicId) || clusters[0]);
  });

  document.getElementById("close-cluster-panel")?.addEventListener("click", () => {
    panel.classList.add("hidden");
  });

  function showClusterPanel(cluster) {
    if (!cluster) return;
    panel.classList.remove("hidden");
    document.getElementById("panel-cluster-title").textContent = cluster.label || `Topic ${cluster.topic_id}`;
    const badge = document.getElementById("panel-stage-badge");
    badge.textContent = cluster.lifecycle_stage || "unknown";
    badge.className = "badge";
    badge.style.background =
      { introduction: "#DCFCE7", growth: "#DBEAFE", maturity: "#F3E8FF", decline: "#FEE2E2" }[
        cluster.lifecycle_stage
      ] || "#F1F5F9";
    badge.style.color =
      { introduction: "#166534", growth: "#1E40AF", maturity: "#6B21A8", decline: "#991B1B" }[
        cluster.lifecycle_stage
      ] || "#334155";

    const sb = cluster.source_breakdown || {};
    document.getElementById("panel-source-breakdown").innerHTML = `
      <span class="pill">scholar: ${sb.scholar || 0}</span>
      <span class="pill">uploaded: ${sb.uploaded || 0}</span>`;

    document.getElementById("panel-keywords").innerHTML = (cluster.keywords || [])
      .map((k) => `<span class="keyword-pill">${k}</span>`)
      .join("");

    document.getElementById("panel-lifecycle-static").textContent =
      cluster.lifecycle_explanation || "Lifecycle stage from S-curve fit on yearly publication counts.";

    document.getElementById("panel-lifecycle-llm").textContent =
      cluster.lifecycle_llm || "Select a cluster to see foresight interpretation.";
  }
}

window.initClusterMap = initClusterMap;
