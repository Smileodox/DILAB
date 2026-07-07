const SCENARIO_ORDER = ["optimistic", "disruptive", "constrained", "stagnant"];

const ROWS = [
  { key: "scenario", label: "Scenario", tier: "scenario" },
  { key: "core", label: "Core Technologies", tier: "core" },
  { key: "evolving", label: "Evolving Capabilities", tier: "evolving" },
  { key: "impact", label: "Sector Impacts", tier: "impact" },
];

const LINK_STYLES = {
  "scenario-core": { stroke: "#7BA3D4", marker: "ip-arrow-blue", active: "#2563EB" },
  "core-evolving": { stroke: "#5EC97A", marker: "ip-arrow-green", active: "#16A34A" },
  "evolving-impact": { stroke: "#F5A962", marker: "ip-arrow-orange", active: "#EA580C" },
};

function initScenarios(result) {
  const sc = result.scenarios || {};
  const foresight = result.foresight || {};
  const whyEl = document.getElementById("scenarios-why");
  const focusBits = [];
  if (foresight.topic_label) focusBits.push(`Focus domain: ${foresight.topic_label}`);
  if (foresight.horizon_year) focusBits.push(`Forecast horizon: ${foresight.horizon_year}`);
  whyEl.textContent = [focusBits.join(" · "), sc.why || ""].filter(Boolean).join("\n\n");

  const driversEl = document.getElementById("uncertainty-drivers");
  driversEl.innerHTML = "";
  (sc.drivers || []).forEach((d) => {
    const card = document.createElement("div");
    card.className = "driver-card";
    card.innerHTML = `<h3>${escapeHtml(d.axis)}</h3><p>${escapeHtml(d.description)}</p><p class="muted">${escapeHtml(d.why)}</p>`;
    driversEl.appendChild(card);
  });

  const scenarios = sc.scenarios || {};
  const trees = sc.impact_trees || {};
  const tabsEl = document.getElementById("impact-path-tabs");
  const vizEl = document.getElementById("impact-paths-viz");
  const detailEl = document.getElementById("impact-path-detail");
  const matrix = document.getElementById("scenario-matrix");
  matrix.innerHTML = "";

  let activeKey = SCENARIO_ORDER.find((k) => scenarios[k]) || SCENARIO_ORDER[0];

  tabsEl.innerHTML = "";
  SCENARIO_ORDER.forEach((key) => {
    const s = scenarios[key];
    if (!s) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `ip-tab${key === activeKey ? " ip-tab--active" : ""}`;
    btn.role = "tab";
    btn.setAttribute("aria-selected", key === activeKey ? "true" : "false");
    btn.dataset.key = key;
    btn.style.setProperty("--tab-color", s.color);
    btn.textContent = s.title;
    btn.addEventListener("click", () => {
      activeKey = key;
      tabsEl.querySelectorAll(".ip-tab").forEach((t) => {
        const on = t.dataset.key === key;
        t.classList.toggle("ip-tab--active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      renderActivePath(vizEl, detailEl, scenarios, trees, key);
    });
    tabsEl.appendChild(btn);
  });

  SCENARIO_ORDER.forEach((key) => {
    const s = scenarios[key];
    if (!s) return;
    const treeMeta = trees[key] || {};
    const card = document.createElement("div");
    card.className = "scenario-card";
    card.innerHTML = `
      <div class="top-border" style="background:${s.color}"></div>
      <div class="body">
        <h3>${escapeHtml(s.title)}</h3>
        <p class="muted">${escapeHtml(s.why)}</p>
        <p>${escapeHtml(s.narrative)}</p>
        <p class="tree-stats muted">
          ${treeMeta.paths_discovered ?? "?"} paths ·
          ${treeMeta.paths_in_scenario ?? "?"} in scenario ·
          ${treeMeta.branch_count ?? treeMeta.tree?.branch_count ?? "?"} branches
        </p>
      </div>`;
    matrix.appendChild(card);
  });

  renderActivePath(vizEl, detailEl, scenarios, trees, activeKey);
}

function renderActivePath(vizEl, detailEl, scenarios, trees, key) {
  const s = scenarios[key];
  const treeMeta = trees[key] || {};
  const root = treeMeta.tree || { name: treeMeta.main_technology || "Main technology", children: [] };
  renderImpactPathsViz(vizEl, root, {
    detailEl,
    scenarioKey: key,
    scenarioTitle: s?.title || key,
    scenarioColor: s?.color || "#2563EB",
    scenarioWhy: treeMeta.why || "",
    scenarioNarrative: s?.narrative || "",
    pathsDiscovered: treeMeta.paths_discovered,
    pathsInScenario: treeMeta.paths_in_scenario,
    mainTech: root.name,
  });
  detailEl.innerHTML = `
    <p class="ip-detail-hint muted">Click a <strong>Sector Impact</strong> node to see why and how the technology affects that sector.</p>
    <p class="ip-detail-text">${escapeHtml(s?.narrative || "")}</p>
    ${treeMeta.why ? `<p class="ip-detail-meta muted">${escapeHtml(treeMeta.why)}</p>` : ""}`;
}

function buildLayout(rootData, opts) {
  const branches = rootData.children || [];
  const nodes = [];
  const links = [];

  const scenarioId = "scenario";
  nodes.push({
    id: scenarioId,
    row: "scenario",
    title: opts.scenarioTitle,
    subtitle: `${opts.pathsInScenario ?? "?"} prioritized paths`,
    tier: "scenario",
    data: { why: opts.scenarioWhy },
  });

  const mainId = "main";
  nodes.push({
    id: mainId,
    row: "core",
    title: truncate(rootData.name, 42),
    subtitle: `${rootData.path_count ?? branches.length} branches · core focus`,
    tier: "core",
    data: rootData,
  });
  links.push({ source: scenarioId, target: mainId, tier: "scenario-core" });

  branches.forEach((branch, i) => {
    const evId = `ev-${i}`;
    const trend = branch.trend ? String(branch.trend).split("/")[0].trim() : "";
    nodes.push({
      id: evId,
      row: "evolving",
      title: truncate(branch.name, 36),
      subtitle: [trend, branch.path_count > 1 ? `${branch.path_count} paths` : ""].filter(Boolean).join(" · ") || "evolving driver",
      tier: "evolving",
      data: branch,
      branchIdx: i,
    });
    links.push({ source: mainId, target: evId, tier: "core-evolving" });

    (branch.children || []).forEach((imp, j) => {
      const impId = `imp-${i}-${j}`;
      const sector = imp.sector || inferSector(imp.name);
      const why = imp.why || "";
      nodes.push({
        id: impId,
        row: "impact",
        title: truncate(imp.name, 28),
        subtitle: sector,
        tier: "impact",
        data: { ...imp, sector, why, how: imp.how || "" },
        branchIdx: i,
        parentEv: evId,
      });
      links.push({ source: evId, target: impId, tier: "evolving-impact" });
    });
  });

  return { nodes, links };
}

function impactNodeHtml(n) {
  const sector = n.data?.sector || n.subtitle;
  const why = n.data?.why || "";
  const whyPreview = why ? truncate(why, 72) : "Click for impact rationale";
  return `
    <span class="ip-sector-badge ip-sector-badge--${sectorClass(sector)}">${escapeHtml(sector)}</span>
    <div class="ip-node-title">${escapeHtml(n.title)}</div>
    <div class="ip-node-why">${why ? `<span class="ip-why-label">Why:</span> ${escapeHtml(whyPreview)}` : escapeHtml(whyPreview)}</div>`;
}

function renderImpactPathsViz(container, rootData, opts) {
  const { nodes, links } = buildLayout(rootData, opts);
  const byRow = Object.fromEntries(ROWS.map((r) => [r.key, nodes.filter((n) => n.row === r.key)]));

  container.innerHTML = `
    <div class="ip-viz" style="--scenario-accent:${opts.scenarioColor}">
      <svg class="ip-links" aria-hidden="true">
        <defs>
          <marker id="ip-arrow-blue" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5.5" orient="auto-start-reverse">
            <path d="M0,0 L10,4 L0,8 z" fill="#7BA3D4"/>
          </marker>
          <marker id="ip-arrow-green" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5.5" orient="auto-start-reverse">
            <path d="M0,0 L10,4 L0,8 z" fill="#5EC97A"/>
          </marker>
          <marker id="ip-arrow-orange" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="5.5" orient="auto-start-reverse">
            <path d="M0,0 L10,4 L0,8 z" fill="#F5A962"/>
          </marker>
          <marker id="ip-arrow-blue-active" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,4 L0,8 z" fill="#2563EB"/>
          </marker>
          <marker id="ip-arrow-green-active" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,4 L0,8 z" fill="#16A34A"/>
          </marker>
          <marker id="ip-arrow-orange-active" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,4 L0,8 z" fill="#EA580C"/>
          </marker>
        </defs>
      </svg>
      ${ROWS.map((row) => {
        const rowNodes = byRow[row.key] || [];
        const isImpact = row.key === "impact";
        return `
          <div class="ip-row ip-row--${row.key}">
            <div class="ip-row-label">${row.label}</div>
            <div class="ip-row-track${isImpact ? " ip-row-track--impacts" : ""}">
              ${rowNodes
                .map((n) => {
                  const inner = isImpact ? impactNodeHtml(n) : `
                  <div class="ip-node-title">${escapeHtml(n.title)}</div>
                  <div class="ip-node-sub">${escapeHtml(n.subtitle)}</div>`;
                  return `
                <div class="ip-node ip-node--${n.tier}" data-id="${n.id}" data-branch="${n.branchIdx ?? ""}" tabindex="0">
                  ${inner}
                </div>`;
                })
                .join("")}
            </div>
          </div>`;
      }).join("")}
    </div>`;

  const viz = container.querySelector(".ip-viz");
  viz._nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));
  viz._whyMap = Object.fromEntries(nodes.filter((n) => n.data?.why).map((n) => [n.id, n.data.why]));
  layoutRowNodes(viz);
  drawPathLinks(viz, links);
  wirePathInteractions(viz, links, opts);

  if (container._resizeObserver) container._resizeObserver.disconnect();
  container._resizeObserver = new ResizeObserver(() => {
    const v = container.querySelector(".ip-viz");
    if (!v) return;
    layoutRowNodes(v);
    drawPathLinks(v, links);
  });
  container._resizeObserver.observe(container);
}

function layoutRowNodes(viz) {
  viz.querySelectorAll(".ip-row").forEach((rowEl) => {
    const track = rowEl.querySelector(".ip-row-track");
    const nodeEls = [...track.querySelectorAll(".ip-node")];
    const n = nodeEls.length;
    if (!n) return;

    if (track.classList.contains("ip-row-track--impacts")) {
      nodeEls.forEach((el) => {
        el.style.left = "";
        el.style.width = "";
      });
      return;
    }

    const trackW = track.clientWidth;
    nodeEls.forEach((el, i) => {
      const x = ((i + 1) / (n + 1)) * trackW;
      el.style.left = `${x}px`;
    });
  });
}

function drawPathLinks(viz, links) {
  const svg = viz.querySelector(".ip-links");
  const vizRect = viz.getBoundingClientRect();
  const positions = {};

  viz.querySelectorAll(".ip-node").forEach((el) => {
    const r = el.getBoundingClientRect();
    positions[el.dataset.id] = {
      x: r.left + r.width / 2 - vizRect.left,
      yTop: r.top - vizRect.top,
      yBot: r.bottom - vizRect.top,
    };
  });

  const defs = svg.querySelector("defs");
  const paths = links
    .map((l) => {
      const a = positions[l.source];
      const b = positions[l.target];
      if (!a || !b) return "";
      const style = LINK_STYLES[l.tier] || LINK_STYLES["scenario-core"];
      const x0 = a.x;
      const y0 = a.yBot + 4;
      const x1 = b.x;
      const y1 = b.yTop - 4;
      const dy = y1 - y0;
      const c1y = y0 + dy * 0.42;
      const c2y = y1 - dy * 0.42;
      return `<path class="ip-link" data-from="${l.source}" data-to="${l.target}" data-tier="${l.tier}"
        marker-end="url(#${style.marker})"
        style="stroke:${style.stroke}"
        d="M${x0},${y0} C${x0},${c1y} ${x1},${c2y} ${x1},${y1}"/>`;
    })
    .join("");

  svg.setAttribute("width", vizRect.width);
  svg.setAttribute("height", vizRect.height);
  svg.setAttribute("viewBox", `0 0 ${vizRect.width} ${vizRect.height}`);
  svg.innerHTML = (defs ? defs.outerHTML : "") + paths;
}

function wirePathInteractions(viz, links, opts) {
  const related = (nodeId) => {
    const rel = new Set([nodeId]);
    let changed = true;
    while (changed) {
      changed = false;
      links.forEach((l) => {
        if (rel.has(l.target) && !rel.has(l.source)) {
          rel.add(l.source);
          changed = true;
        }
        if (rel.has(l.source) && !rel.has(l.target)) {
          rel.add(l.target);
          changed = true;
        }
      });
    }
    return rel;
  };

  const highlight = (nodeId) => {
    const rel = related(nodeId);
    viz.querySelectorAll(".ip-node").forEach((el) => {
      el.classList.toggle("ip-node--dim", !rel.has(el.dataset.id));
      el.classList.toggle("ip-node--focus", el.dataset.id === nodeId);
    });
    viz.querySelectorAll(".ip-link").forEach((el) => {
      const on = rel.has(el.dataset.from) && rel.has(el.dataset.to);
      const tier = el.dataset.tier;
      const style = LINK_STYLES[tier] || LINK_STYLES["scenario-core"];
      el.classList.toggle("ip-link--active", on);
      if (on) {
        el.style.stroke = style.active;
        el.setAttribute("marker-end", `url(#${style.marker}-active)`);
      } else {
        el.style.stroke = style.stroke;
        el.setAttribute("marker-end", `url(#${style.marker})`);
      }
    });
  };

  const clear = () => {
    viz.querySelectorAll(".ip-node--dim, .ip-node--focus").forEach((el) => {
      el.classList.remove("ip-node--dim", "ip-node--focus");
    });
    viz.querySelectorAll(".ip-link").forEach((el) => {
      el.classList.remove("ip-link--active");
      const tier = el.dataset.tier;
      const style = LINK_STYLES[tier] || LINK_STYLES["scenario-core"];
      el.style.stroke = style.stroke;
      el.setAttribute("marker-end", `url(#${style.marker})`);
    });
  };

  viz.querySelectorAll(".ip-node").forEach((el) => {
    el.addEventListener("mouseenter", () => highlight(el.dataset.id));
    el.addEventListener("mouseleave", clear);
    el.addEventListener("focus", () => highlight(el.dataset.id));
    el.addEventListener("blur", clear);
    el.addEventListener("click", () => {
      const node = viz._nodeMap?.[el.dataset.id];
      if (!node) return;
      if (node.tier === "impact") {
        showImpactDetail(opts.detailEl, node, viz._nodeMap, opts);
      } else {
        const why = node.data?.why || viz._whyMap?.[el.dataset.id];
        if (why) showNodeTooltip(viz, el, why, opts.scenarioColor);
      }
    });
  });
}

function showImpactDetail(detailEl, impactNode, nodeMap, opts) {
  if (!detailEl) return;
  const evNode = impactNode.parentEv ? nodeMap[impactNode.parentEv] : null;
  const mainNode = nodeMap.main;
  const scenarioNode = nodeMap.scenario;
  const d = impactNode.data || {};
  const sector = d.sector || impactNode.subtitle || "Innovation";
  const why = d.why || "No rationale available for this impact.";
  const how = d.how || "Re-run analysis to generate mechanism details for this path.";
  const sourceLabel = llmSourceLabel(d.llm_source);

  const chain = [
    { label: "Scenario", value: scenarioNode?.title || opts.scenarioTitle },
    { label: "Core technology", value: mainNode?.title || opts.mainTech },
    { label: "Evolving capability", value: evNode?.title || d.evolving_tech || "—" },
    { label: "Sector impact", value: impactNode.title },
  ];

  detailEl.innerHTML = `
    <div class="ip-impact-detail">
      <div class="ip-impact-detail-header">
        <span class="ip-sector-badge ip-sector-badge--${sectorClass(sector)}">${escapeHtml(sector)}</span>
        <h3 class="ip-impact-detail-title">${escapeHtml(impactNode.title)}</h3>
        ${sourceLabel ? `<span class="ip-llm-badge">${escapeHtml(sourceLabel)}</span>` : ""}
      </div>
      <div class="ip-path-chain">
        ${chain
          .map(
            (c, i) => `
          <span class="ip-chain-step">
            <span class="ip-chain-label">${escapeHtml(c.label)}</span>
            <span class="ip-chain-value">${escapeHtml(c.value)}</span>
          </span>
          ${i < chain.length - 1 ? '<span class="ip-chain-arrow" aria-hidden="true">→</span>' : ""}`
          )
          .join("")}
      </div>
      <div class="ip-rationale-grid">
        <div class="ip-rationale-block ip-rationale-block--why">
          <h4>Why this sector is affected</h4>
          <p>${escapeHtml(why)}</p>
        </div>
        <div class="ip-rationale-block ip-rationale-block--how">
          <h4>How the effect materialises</h4>
          <p>${escapeHtml(how)}</p>
        </div>
      </div>
    </div>`;
}

function showNodeTooltip(viz, nodeEl, text, color) {
  let tip = viz.querySelector(".ip-tooltip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "ip-tooltip";
    viz.appendChild(tip);
  }
  tip.textContent = text;
  tip.style.borderColor = color;
  tip.classList.add("ip-tooltip--visible");
  const r = nodeEl.getBoundingClientRect();
  const v = viz.getBoundingClientRect();
  tip.style.left = `${r.left - v.left + r.width / 2}px`;
  tip.style.top = `${r.bottom - v.top + 8}px`;
  clearTimeout(tip._hideTimer);
  tip._hideTimer = setTimeout(() => tip.classList.remove("ip-tooltip--visible"), 5000);
}

function llmSourceLabel(source) {
  if (source === "openrouter") return "LLM-generated";
  if (source === "contextual_fallback") return "Data-driven fallback (no API)";
  if (source === "template_fallback") return "Rule-based fallback";
  return "";
}

function sectorClass(sector) {
  const s = (sector || "").toLowerCase();
  if (s.includes("society")) return "society";
  if (s.includes("econom")) return "economy";
  if (s.includes("govern")) return "governance";
  return "innovation";
}

function inferSector(name) {
  const n = (name || "").toLowerCase();
  if (/society|social|talent|people|workforce|public|migration/.test(n)) return "Society";
  if (/econom|market|demand|vendor|supply|competitive|acquisition|partnership|cost|substitution/.test(n)) return "Economy";
  if (/govern|regulat|policy|compliance|legal|standard|fragment/.test(n)) return "Governance";
  return "Innovation";
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function truncate(s, n) {
  if (!s || s.length <= n) return s;
  return s.slice(0, n - 1) + "…";
}

window.initScenarios = initScenarios;
