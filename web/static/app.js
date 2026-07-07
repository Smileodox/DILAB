const API = '';
let allDrivers = [];
let allScenarios = [];

const PLOTLY_CFG = { responsive: true, displayModeBar: false };
const PLOTLY_DARK = { paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#9ca3af', size: 11 } };

// --- Tabs ---
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
        window.dispatchEvent(new Event('resize'));
    });
});

// --- Helpers ---
function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}
function originBadge(origin) {
    const map = { both: 'validated', bom: 'incremental', trend: 'speculative' };
    const label = map[origin] || origin;
    return `<span class="badge badge-${label}">${label}</span>`;
}
function confBadge(conf) { return `<span class="badge badge-${conf}">${conf}</span>`; }
function typeBadge(type) { return `<span class="badge badge-${type}">${type}</span>`; }
function sourceTypeBadge(type) {
    const map = { product_page: ['Product', 'incremental'], datasheet: ['Datasheet', 'incremental'], research_paper: ['Research', 'speculative'], trend_report: ['Trend', 'speculative'], regulation: ['Regulation', 'validated'], tech_article: ['Article', 'speculative'] };
    const [label, cls] = map[type] || [type, 'speculative'];
    return `<span class="badge badge-${cls}">${label}</span>`;
}
function contentOriginBadge(origin) {
    if (origin === 'fetched') return '<span class="badge badge-validated">fetched</span>';
    return '<span class="badge" style="background:rgba(251,191,36,0.15);color:#fbbf24;border-color:rgba(251,191,36,0.3)">curated</span>';
}

// --- Overview ---
async function loadOverview() {
    const data = await fetch(API + '/api/overview').then(r => r.json());
    document.getElementById('overview-cards').innerHTML = [
        { value: data.sources, label: 'Sources' },
        { value: data.chunks, label: 'Chunks' },
        { value: data.drivers_total, label: 'Drivers' },
        { value: data.scenarios, label: 'Scenarios' },
    ].map(s => `
        <div class="stat-card">
            <div class="stat-value">${s.value}</div>
            <div class="stat-label">${s.label}</div>
        </div>
    `).join('');

    document.getElementById('stats-badges').innerHTML = `
        <span class="badge badge-validated">${data.drivers_by_origin.both || 0} validated</span>
        <span class="badge badge-incremental">${data.drivers_by_origin.bom || 0} incremental</span>
        <span class="badge badge-speculative">${data.drivers_by_origin.trend || 0} speculative</span>
    `;

    document.getElementById('pipe-sources').textContent = `${data.sources} sources`;
    document.getElementById('pipe-drivers').textContent = `${data.drivers_total} drivers`;
    document.getElementById('pipe-cib').textContent = `${data.cib_drivers} drivers`;
    document.getElementById('pipe-scenarios').textContent = `${data.scenarios} scenarios`;

    const o = data.drivers_by_origin;
    Plotly.newPlot('driver-pie', [{
        values: [o.both || 0, o.bom || 0, o.trend || 0],
        labels: ['Validated', 'Incremental', 'Speculative'],
        type: 'pie',
        hole: 0.45,
        marker: { colors: ['#34d399', '#60a5fa', '#a78bfa'] },
        textinfo: 'label+value',
        textfont: { size: 11, color: '#e5e7eb' },
        insidetextorientation: 'horizontal',
    }], { ...PLOTLY_DARK, margin: { t: 5, b: 5, l: 5, r: 5 }, showlegend: false }, PLOTLY_CFG);
}

// --- Sources ---
async function loadSources() {
    const sources = await fetch(API + '/api/sources').then(r => r.json());
    const el = document.getElementById('source-count');
    if (el) el.textContent = `${sources.length} sources across ${new Set(sources.map(s => s.pool)).size} pools`;
    document.getElementById('source-table').innerHTML = sources.map(s => `
        <tr class="border-b border-gray-800">
            <td class="py-2.5 px-3">
                <div class="font-medium text-sm">${esc(s.title)}</div>
                <div class="text-[11px] text-gray-600 mt-0.5">${s.chunk_count || 0} chunks</div>
            </td>
            <td class="py-2.5 px-3">${sourceTypeBadge(s.type)}</td>
            <td class="py-2.5 px-3"><span class="badge badge-${s.pool === 'product' ? 'validated' : 'incremental'}">${esc(s.pool)}</span></td>
            <td class="py-2.5 px-3">${contentOriginBadge(s.content_origin)}</td>
            <td class="py-2.5 px-3 text-xs text-gray-500">${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener" class="text-blue-400 hover:underline">${esc(s.url.substring(0, 45))}...</a>` : '<span class="text-gray-700">—</span>'}</td>
        </tr>
    `).join('');
}

// --- BOM Tree ---
async function loadBOM() {
    const data = await fetch(API + '/api/bom').then(r => r.json());
    document.getElementById('bom-stats').textContent = `${data.total_nodes} nodes · ${data.total_drivers} technology drivers`;

    const levelColors = ['#60a5fa', '#34d399', '#a78bfa', '#fb923c', '#f87171'];

    function renderNode(node, depth = 0) {
        const color = levelColors[Math.min(depth, levelColors.length - 1)];
        const driverTag = node.is_driver ? ' <span class="bom-driver-tag">driver</span>' : '';
        const isRoot = depth === 0;
        let html = `<div class="bom-node ${isRoot ? 'bom-root' : ''}" style="margin-left: ${depth === 0 ? 0 : 1.25}rem">`;
        html += `<div class="bom-node-label"><span class="level-dot" style="background: ${color}"></span> ${esc(node.name)}${driverTag}</div>`;
        if (node.children && node.children.length > 0) {
            for (const child of node.children) {
                html += renderNode(child, depth + 1);
            }
        }
        html += '</div>';
        return html;
    }
    document.getElementById('bom-tree').innerHTML = renderNode(data.tree);

    // sunburst chart
    const ids = [], labels = [], parents = [], values = [], colors = [];
    function flatten(node, parentId) {
        const id = node.id;
        ids.push(id);
        labels.push(node.name.length > 22 ? node.name.substring(0, 20) + '...' : node.name);
        parents.push(parentId || '');
        values.push(node.children.length || 1);
        colors.push(node.is_driver ? '#34d399' : levelColors[Math.min(node.level, levelColors.length - 1)]);
        for (const c of node.children) flatten(c, id);
    }
    flatten(data.tree, '');

    Plotly.newPlot('bom-sunburst', [{
        type: 'sunburst',
        ids, labels, parents, values,
        branchvalues: 'total',
        marker: { colors, line: { width: 1, color: '#111827' } },
        textfont: { size: 9, color: '#e5e7eb' },
        hovertemplate: '<b>%{label}</b><br>Level: %{customdata}<extra></extra>',
        customdata: ids.map((_, i) => {
            let depth = 0, p = parents[i];
            while (p) { depth++; p = parents[ids.indexOf(p)]; }
            return depth;
        }),
    }], { ...PLOTLY_DARK, margin: { t: 10, b: 10, l: 10, r: 10 } }, PLOTLY_CFG);
}

// --- Drivers ---
async function loadDrivers() {
    allDrivers = await fetch(API + '/api/drivers').then(r => r.json());
    renderDriverTable('all');
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDriverTable(btn.dataset.filter);
        });
    });
}

function renderDriverTable(filter) {
    const filtered = filter === 'all' ? allDrivers : allDrivers.filter(d => d.origin === filter);
    const el = document.getElementById('driver-count');
    if (el) el.textContent = `${filtered.length} of ${allDrivers.length} drivers`;
    document.getElementById('driver-table').innerHTML = filtered.map(d => `
        <tr data-id="${d.id}">
            <td class="py-2 px-3 font-medium text-sm">${esc(d.name)}</td>
            <td class="py-2 px-3">${originBadge(d.origin)}</td>
            <td class="py-2 px-3">${confBadge(d.confidence)}</td>
            <td class="py-2 px-3 text-gray-500 text-xs">${d.source_chunk_ids.length}</td>
        </tr>
    `).join('');
    document.querySelectorAll('#driver-table tr').forEach(row => {
        row.addEventListener('click', () => {
            const driver = allDrivers.find(d => d.id === row.dataset.id);
            if (driver) showDriverDetail(driver);
        });
    });
}

function showDriverDetail(d) {
    const panel = document.getElementById('driver-detail');
    panel.classList.remove('hidden');
    panel.innerHTML = `
        <div class="flex items-center gap-3 mb-3">
            <h3 class="text-base font-bold">${esc(d.name)}</h3>
            ${originBadge(d.origin)} ${confBadge(d.confidence)}
        </div>
        <p class="text-sm text-gray-300 mb-3 leading-relaxed">${esc(d.description)}</p>
        ${d.merge_reasoning ? `<p class="text-xs text-gray-500"><strong>Merge reasoning:</strong> ${esc(d.merge_reasoning)}</p>` : ''}
        <p class="text-xs text-gray-600 mt-2">Source chunks: ${d.source_chunk_ids.length}</p>
    `;
}

// --- CIB ---
async function loadCIB() {
    const cib = await fetch(API + '/api/cib').then(r => r.json());
    const n = cib.driver_names.length;
    const shortNames = cib.driver_names.map(s => s.length > 16 ? s.substring(0, 14) + '…' : s);
    const heatmapHeight = Math.max(500, n * 32 + 120);

    Plotly.newPlot('cib-heatmap', [{
        z: cib.matrix, x: shortNames, y: shortNames,
        type: 'heatmap',
        colorscale: [
            [0, '#991b1b'], [0.17, '#dc2626'], [0.33, '#f87171'],
            [0.5, '#374151'],
            [0.67, '#4ade80'], [0.83, '#16a34a'], [1, '#065f46']
        ],
        zmin: -3, zmax: 3,
        text: cib.matrix.map(row => row.map(v => v !== 0 ? String(v) : '')),
        texttemplate: '%{text}',
        textfont: { size: 8, color: '#e5e7eb' },
        hovertemplate: '%{y}<br>→ %{x}<br>Score: %{z}<extra></extra>',
        colorbar: {
            title: { text: 'Net Impact', font: { color: '#6b7280', size: 10 } },
            tickfont: { color: '#6b7280', size: 9 },
            thickness: 12, len: 0.5,
        },
    }], {
        ...PLOTLY_DARK,
        height: heatmapHeight,
        font: { color: '#9ca3af', size: 7 },
        margin: { t: 10, b: 110, l: 120, r: 50 },
        xaxis: { tickangle: -45, side: 'bottom', tickfont: { size: 8 } },
        yaxis: { autorange: 'reversed', tickfont: { size: 8 } },
    }, PLOTLY_CFG);

    const infVals = cib.driver_ids.map(id => cib.influence[id]);
    const depVals = cib.driver_ids.map(id => cib.dependence[id]);
    const scatterNames = cib.driver_names.map(s => s.length > 25 ? s.substring(0, 23) + '...' : s);
    const meanInf = infVals.reduce((a, b) => a + b, 0) / n;
    const meanDep = depVals.reduce((a, b) => a + b, 0) / n;

    Plotly.newPlot('cib-scatter', [{
        x: depVals, y: infVals, text: scatterNames,
        mode: 'markers+text', type: 'scatter',
        textposition: 'top center',
        textfont: { size: 8, color: '#6b7280' },
        marker: { size: 10, color: '#60a5fa', opacity: 0.85, line: { width: 1, color: '#1e3a5f' } },
        hovertemplate: '<b>%{text}</b><br>Influence: %{y}<br>Dependence: %{x}<extra></extra>',
    }], {
        ...PLOTLY_DARK,
        margin: { t: 20, b: 45, l: 45, r: 20 },
        xaxis: { title: { text: 'Dependence', font: { size: 11 } }, gridcolor: '#1f2937', zerolinecolor: '#374151' },
        yaxis: { title: { text: 'Influence', font: { size: 11 } }, gridcolor: '#1f2937', zerolinecolor: '#374151' },
        shapes: [
            { type: 'line', x0: meanDep, x1: meanDep, y0: Math.min(...infVals) - 1, y1: Math.max(...infVals) + 1, line: { dash: 'dot', color: '#374151', width: 1 } },
            { type: 'line', y0: meanInf, y1: meanInf, x0: Math.min(...depVals) - 1, x1: Math.max(...depVals) + 1, line: { dash: 'dot', color: '#374151', width: 1 } },
        ],
        annotations: [
            { x: Math.max(...depVals), y: Math.max(...infVals), text: 'Critical', showarrow: false, font: { color: '#ef4444', size: 9 } },
            { x: Math.min(...depVals), y: Math.max(...infVals), text: 'Enabler', showarrow: false, font: { color: '#22c55e', size: 9 } },
            { x: Math.max(...depVals), y: Math.min(...infVals), text: 'Dependent', showarrow: false, font: { color: '#f59e0b', size: 9 } },
            { x: Math.min(...depVals), y: Math.min(...infVals), text: 'Isolated', showarrow: false, font: { color: '#4b5563', size: 9 } },
        ],
    }, PLOTLY_CFG);
}

// --- Scenarios ---
async function loadScenarios() {
    allScenarios = await fetch(API + '/api/scenarios').then(r => r.json());

    const colors = allScenarios.map(s => s.type === 'evolutionary' ? '#60a5fa' : '#fb923c');
    const sizes = allScenarios.map(s => Math.max(s.assessment.confidence * 35 + 8, 15));

    Plotly.newPlot('scenario-scatter', [{
        x: allScenarios.map(s => s.assessment.probability),
        y: allScenarios.map(s => s.assessment.impact),
        text: allScenarios.map(s => s.title.length > 30 ? s.title.substring(0, 28) + '...' : s.title),
        mode: 'markers+text',
        type: 'scatter',
        textposition: 'top center',
        textfont: { size: 9, color: '#d1d5db' },
        marker: { size: sizes, color: colors, opacity: 0.9, line: { width: 1.5, color: '#111827' } },
        hovertemplate: '<b>%{text}</b><br>Impact: %{y}<br>Probability: %{x}<extra></extra>',
    }], {
        ...PLOTLY_DARK,
        margin: { t: 20, b: 45, l: 45, r: 20 },
        xaxis: { title: { text: 'Probability', font: { size: 11 } }, range: [0.5, 10.5], gridcolor: '#1f2937', zerolinecolor: '#374151', dtick: 2 },
        yaxis: { title: { text: 'Impact', font: { size: 11 } }, range: [0.5, 10.5], gridcolor: '#1f2937', zerolinecolor: '#374151', dtick: 2 },
        shapes: [
            { type: 'line', x0: 5, x1: 5, y0: 0.5, y1: 10.5, line: { dash: 'dot', color: '#374151' } },
            { type: 'line', x0: 0.5, x1: 10.5, y0: 5, y1: 5, line: { dash: 'dot', color: '#374151' } },
        ],
        annotations: [
            { x: 8, y: 9.8, text: 'HIGH PRIORITY', showarrow: false, font: { color: '#ef4444', size: 10 } },
            { x: 2.5, y: 9.8, text: 'MONITOR', showarrow: false, font: { color: '#f59e0b', size: 10 } },
            { x: 8, y: 1.2, text: 'EXPECTED', showarrow: false, font: { color: '#22c55e', size: 10 } },
            { x: 2.5, y: 1.2, text: 'LOW PRIORITY', showarrow: false, font: { color: '#4b5563', size: 10 } },
        ],
    }, PLOTLY_CFG);

    document.getElementById('scenario-cards').innerHTML = allScenarios.map((s, i) => `
        <div class="card scenario-card" data-id="${s.id}" data-index="${i}">
            <div class="flex items-center gap-2 mb-2">
                ${typeBadge(s.type)}
            </div>
            <h3 class="font-bold text-sm leading-tight mb-3">${esc(s.title)}</h3>
            <div class="space-y-1.5 mb-3">
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-gray-500 w-14">Impact</span>
                    <div class="score-bar"><div class="score-bar-fill impact" style="width: ${s.assessment.impact * 10}%"></div></div>
                    <span class="text-white font-bold w-7 text-right text-[11px]">${s.assessment.impact}</span>
                </div>
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-gray-500 w-14">Prob.</span>
                    <div class="score-bar"><div class="score-bar-fill probability" style="width: ${s.assessment.probability * 10}%"></div></div>
                    <span class="text-white font-bold w-7 text-right text-[11px]">${s.assessment.probability}</span>
                </div>
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-gray-500 w-14">Conf.</span>
                    <div class="score-bar"><div class="score-bar-fill confidence" style="width: ${s.assessment.confidence * 100}%"></div></div>
                    <span class="text-white font-bold w-7 text-right text-[11px]">${s.assessment.confidence.toFixed(2)}</span>
                </div>
            </div>
            <div class="text-[11px] text-gray-600 mb-3 flex flex-wrap gap-1">${(() => {
                const counts = {};
                s.assumptions.forEach(a => counts[a.state] = (counts[a.state] || 0) + 1);
                const stateColors = { breakthrough: '#34d399', steady_progress: '#60a5fa', stagnation: '#f87171' };
                return Object.entries(counts).map(([st, ct]) =>
                    `<span style="color:${stateColors[st] || '#6b7280'}">${ct}× ${st.replace('_', ' ')}</span>`
                ).join('<span class="text-gray-700">·</span>');
            })()}</div>
            <div class="flex gap-3">
                <button class="text-xs text-blue-400 hover:text-blue-300 narrative-toggle" data-index="${i}">Narrative</button>
                <button class="text-xs text-blue-400 hover:text-blue-300 trace-btn" data-id="${s.id}">Traceability</button>
            </div>
            <div class="narrative text-[13px] text-gray-400 mt-3 leading-relaxed" id="narrative-${i}">${esc(s.narrative)}</div>
        </div>
    `).join('');

    document.querySelectorAll('.narrative-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const el = document.getElementById('narrative-' + btn.dataset.index);
            el.classList.toggle('open');
            btn.textContent = el.classList.contains('open') ? 'Hide narrative' : 'Narrative';
        });
    });
    document.querySelectorAll('.trace-btn').forEach(btn => {
        btn.addEventListener('click', () => loadTraceability(btn.dataset.id));
    });
}

async function loadTraceability(scenarioId) {
    const data = await fetch(API + `/api/traceability/${scenarioId}`).then(r => r.json());
    const panel = document.getElementById('traceability-panel');
    panel.classList.remove('hidden');

    document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('selected'));
    document.querySelector(`.scenario-card[data-id="${scenarioId}"]`)?.classList.add('selected');

    panel.innerHTML = `
        <h3 class="card-title">Traceability: ${esc(data.scenario.title)}</h3>
        <div class="text-sm mb-4 text-gray-400 leading-relaxed">${esc(data.assessment?.reasoning || '')}</div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-2">Assumptions</h4>
        <div class="trace-tree mb-4">
            ${data.assumptions.map(a => `
                <div class="trace-node">
                    <div class="trace-node-title">${esc(a.description)}</div>
                    ${a.driver ? `<div class="trace-node-meta">${originBadge(a.driver.origin)} ${confBadge(a.driver.confidence)}${a.driver.merge_reasoning ? ` · ${esc(a.driver.merge_reasoning.substring(0, 100))}` : ''}</div>` : ''}
                </div>
            `).join('')}
        </div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-2">Source Chain</h4>
        <div class="trace-tree">
            ${data.source_chain.map(s => `
                <div class="trace-node">
                    <div class="trace-node-title">${esc(s.source.title)}</div>
                    <div class="trace-node-meta">
                        ${esc(s.source.type)} · ${esc(s.source.pool)}
                        ${s.source.url ? ` · <a href="${esc(s.source.url)}" target="_blank" rel="noopener" class="text-blue-400 hover:underline">link</a>` : ''}
                        <br><span class="text-gray-700">${esc(s.chunk_preview.substring(0, 150))}...</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    panel.scrollIntoView({ behavior: 'smooth' });
}

// --- Export ---
document.getElementById('export-btn').addEventListener('click', async () => {
    const data = await fetch(API + '/api/export').then(r => r.json());
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dilab-foresight-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
});

// --- Init ---
loadOverview();
loadSources();
loadBOM();
loadDrivers();
loadCIB();
loadScenarios();
