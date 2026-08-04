const $ = (selector) => document.querySelector(selector);
const input = $("#chatInput");
const analyzeButton = $("#analyzeButton");
const sampleButton = $("#sampleButton");
const fileInput = $("#fileInput");
const dropzone = $(".dropzone");
const previewStats = $("#previewStats");
const progressSection = $("#progressSection");
const reportSection = $("#reportSection");
const evidenceDialog = $("#evidenceDialog");
let currentResult = null;
let previewTimer = null;

const payload = () => ({
  text: input.value,
  aliases: $("#aliasToggle").checked,
  mode: $("#deepToggle").checked ? "deep" : "quick",
});

input.addEventListener("input", () => {
  analyzeButton.disabled = input.value.trim().length < 40;
  clearTimeout(previewTimer);
  if (!analyzeButton.disabled) previewTimer = setTimeout(loadPreview, 350);
});

sampleButton.addEventListener("click", async () => {
  const response = await fetch("/api/sample");
  input.value = (await response.json()).text;
  input.dispatchEvent(new Event("input"));
  input.scrollIntoView({ behavior: "smooth", block: "center" });
});

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (file) await acceptFile(file);
});

["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault(); dropzone.classList.add("drag");
}));
["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault(); dropzone.classList.remove("drag");
}));
dropzone.addEventListener("drop", async (event) => {
  const file = event.dataTransfer.files[0];
  if (file) await acceptFile(file);
});

async function acceptFile(file) {
  if (file.size > 30 * 1024 * 1024) return alert("文件超过 30MB 演示限制");
  input.value = await file.text();
  input.dispatchEvent(new Event("input"));
}

async function loadPreview() {
  try {
    const response = await fetch("/api/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    const data = await response.json();
    if (!response.ok) return;
    const stats = data.stats;
    previewStats.hidden = false;
    previewStats.innerHTML = `<span><b>${formatNumber(stats.message_count)}</b>条消息</span><span><b>${formatNumber(stats.estimated_tokens)}</b>上下文估算 Tokens</span><span><b>${stats.participants.length}</b>位参与者</span><span><b>${data.privacy.redaction_count}</b>处敏感信息</span>`;
  } catch (_) { /* live preview is non-blocking */ }
}

analyzeButton.addEventListener("click", async () => {
  analyzeButton.disabled = true;
  reportSection.hidden = true;
  progressSection.hidden = false;
  progressSection.scrollIntoView({ behavior: "smooth", block: "center" });
  animateProgress();
  try {
    const response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "分析失败");
    currentResult = data;
    renderReport(data);
    progressSection.hidden = true;
    reportSection.hidden = false;
    reportSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    progressSection.hidden = true;
    alert(`分析没有完成：${error.message}`);
  } finally {
    analyzeButton.disabled = false;
  }
});

function animateProgress() {
  const items = [
    ["正在建立证据索引", "为每条消息分配可回溯编号。"],
    ["正在寻找跨月线索", "把分散在不同月份的回应和约定连接起来。"],
    ["正在检查推断边界", "证据不足的判断会被删除或降低置信度。"],
  ];
  let index = 0;
  const tick = () => {
    if (progressSection.hidden) return;
    $("#progressTitle").textContent = items[index][0];
    $("#progressCopy").textContent = items[index][1];
    index = (index + 1) % items.length;
    setTimeout(tick, 2600);
  };
  tick();
}

function renderReport(data) {
  const r = data.report;
  $("#reportTitle").textContent = r.title || "你们的后来";
  $("#reportSubtitle").textContent = r.subtitle || "";
  $("#overview").textContent = r.overview || "";
  $("#engineBadge").textContent = data.engine === "local-demo" ? "LOCAL PREVIEW · 未调用模型" : `${data.engine} · ${data.stages.join(" → ")}`;
  $("#confidenceNote").textContent = r.confidence_note || "";
  $("#closingLetter").textContent = r.closing_letter || "";
  renderStats(data.stats);
  renderPulse(r.monthly || []);
  renderTopics(r.topics || []);
  renderOpenLoops(r.open_loops || []);
  renderTimeline(r.turning_points || []);
  renderStories("#supportMoments", r.support_moments || [], "detail");
  renderStories("#patterns", r.patterns || [], "possible_meaning", "observation");
}

async function replaySavedResult() {
  if (new URLSearchParams(window.location.search).get("replay") !== "1") return;
  try {
    const response = await fetch("/api/replay");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "无法载入回放结果");
    currentResult = data;
    renderReport(data);
    reportSection.hidden = false;
    requestAnimationFrame(() => reportSection.scrollIntoView({ block: "start" }));
  } catch (error) {
    console.error(error);
  }
}

function renderStats(stats) {
  const days = stats.start && stats.end ? Math.max(1, Math.round((new Date(stats.end) - new Date(stats.start)) / 86400000)) : 0;
  const cards = [[formatNumber(stats.message_count), "条消息"], [formatNumber(stats.character_count), "个文字"], [days, "天的跨度"], [formatNumber(stats.late_night_count), "条深夜对话"]];
  $("#statsCards").innerHTML = cards.map(([value, label]) => `<div class="stat-card"><b>${value}</b><span>${label}</span></div>`).join("");
}

function renderPulse(monthly) {
  if (!monthly.length) { $("#pulseChart").innerHTML = "<p>没有足够的月度数据</p>"; return; }
  const width = 960, height = 220, left = 35, top = 15, bottom = 28;
  const x = (i) => monthly.length === 1 ? width / 2 : left + i * (width - left * 2) / (monthly.length - 1);
  const y = (v) => top + (100 - Number(v || 0)) * (height - top - bottom) / 100;
  const path = (key) => monthly.map((item, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(item[key]).toFixed(1)}`).join(" ");
  const grid = [0,25,50,75,100].map(v => `<line x1="${left}" y1="${y(v)}" x2="${width-left}" y2="${y(v)}" stroke="#ded9cd" stroke-width="1"/><text x="0" y="${y(v)+4}" fill="#8a887f" font-size="9">${v}</text>`).join("");
  const labels = monthly.map((m,i) => `<text x="${x(i)}" y="${height-4}" text-anchor="middle" fill="#77746c" font-size="9">${escapeHtml(m.month.slice(5))}月</text>`).join("");
  const points = (key, color) => monthly.map((m,i) => `<circle cx="${x(i)}" cy="${y(m[key])}" r="4" fill="${color}" stroke="#fbfaf5" stroke-width="2"/>`).join("");
  $("#pulseChart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="月度关系温度和摩擦信号折线图">${grid}<path d="${path("warmth")}" fill="none" stroke="#ee6b4d" stroke-width="3"/>${points("warmth", "#ee6b4d")}<path d="${path("friction")}" fill="none" stroke="#315fcd" stroke-width="2" stroke-dasharray="5 5"/>${points("friction", "#315fcd")}${labels}</svg>`;
  $("#monthNotes").innerHTML = monthly.map(m => `<div class="month-note"><strong>${escapeHtml(m.month)}</strong>${escapeHtml(m.summary || "")}${evidenceButtons(m.evidence_ids)}</div>`).join("");
}

function renderTopics(topics) {
  $("#topics").innerHTML = topics.map(t => `<div class="topic"><div class="topic-line"><span>${escapeHtml(t.name)}</span><b>${Number(t.share || 0)}%</b></div><div class="topic-bar"><i style="width:${Math.min(100, Number(t.share || 0))}%"></i></div><p>${escapeHtml(t.change || "")}</p>${evidenceButtons(t.evidence_ids)}</div>`).join("") || "<p>暂无足够信息</p>";
}

function renderOpenLoops(items) {
  $("#openLoops").innerHTML = items.map(item => `<div class="open-loop"><strong>${escapeHtml(item.item)}</strong><span>${escapeHtml(item.status || "待确认")}</span>${evidenceButtons(item.evidence_ids)}</div>`).join("") || "<p>没有发现明确的未完成约定。</p>";
}

function renderTimeline(items) {
  $("#turningPoints").innerHTML = items.map(item => `<div class="timeline-item"><div class="timeline-date">${escapeHtml(item.date || "")}</div><div class="timeline-content"><strong>${escapeHtml(item.title || "")}</strong><p>${escapeHtml(item.observation || "")}</p><em>${escapeHtml(item.inference || "")}</em>${evidenceButtons(item.evidence_ids)}</div></div>`).join("") || "<p>暂无足够信息</p>";
}

function renderStories(selector, items, detailKey, secondaryKey) {
  $(selector).innerHTML = items.map(item => `<div class="story"><strong>${escapeHtml(item.title || "")}</strong>${secondaryKey ? `<p>${escapeHtml(item[secondaryKey] || "")}</p>` : ""}<p>${escapeHtml(item[detailKey] || "")}</p>${evidenceButtons(item.evidence_ids)}</div>`).join("") || "<p>暂无足够信息</p>";
}

function evidenceButtons(ids = []) {
  if (!ids.length) return "";
  return `<div class="evidence-links">${ids.map(id => `<button data-evidence="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join("")}</div>`;
}

document.addEventListener("click", (event) => {
  const id = event.target.dataset?.evidence;
  if (!id || !currentResult) return;
  const item = currentResult.evidence[id];
  $("#evidenceBody").innerHTML = item ? `<div class="evidence-message"><div>${escapeHtml(item.id)} · ${escapeHtml(item.timestamp)} · ${escapeHtml(item.speaker)}</div><p>${escapeHtml(item.text)}</p></div>` : `<p>该证据未在输入中找到，可能已在审计阶段被标记。</p>`;
  evidenceDialog.showModal();
});

$("#closeDialog").addEventListener("click", () => evidenceDialog.close());
$("#printButton").addEventListener("click", () => window.print());
$("#jsonButton").addEventListener("click", () => {
  if (!currentResult) return;
  const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: "application/json" });
  const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "relationship-yearbook.json" });
  link.click(); URL.revokeObjectURL(link.href);
});

function formatNumber(value) { return new Intl.NumberFormat("zh-CN").format(Number(value || 0)); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }

replaySavedResult();
