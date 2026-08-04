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
const apiKeyInput = $("#apiKeyInput");
const consentToggle = $("#consentToggle");
let currentResult = null;
let previewTimer = null;

const basePayload = () => ({
  text: input.value,
  aliases: $("#aliasToggle").checked,
  mode: $("#deepToggle").checked ? "deep" : "quick",
});

const analysisPayload = () => ({
  ...basePayload(),
  ark_api_key: apiKeyInput.value.trim(),
});

function updateAnalyzeState() {
  analyzeButton.disabled = input.value.trim().length < 40 || !consentToggle.checked;
}

input.addEventListener("input", () => {
  updateAnalyzeState();
  clearTimeout(previewTimer);
  if (input.value.trim().length >= 40) previewTimer = setTimeout(loadPreview, 350);
});

consentToggle.addEventListener("input", updateAnalyzeState);

$("#toggleApiKey").addEventListener("click", () => {
  const revealing = apiKeyInput.type === "password";
  apiKeyInput.type = revealing ? "text" : "password";
  $("#toggleApiKey").textContent = revealing ? "隐藏" : "显示";
  $("#toggleApiKey").setAttribute("aria-label", revealing ? "隐藏 API Key" : "显示 API Key");
});

sampleButton.addEventListener("click", async () => {
  const response = await fetch("/api/sample");
  input.value = (await response.json()).text;
  consentToggle.checked = true;
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
  if (file.size > 8 * 1024 * 1024) return alert("文件超过 8MB 限制");
  input.value = await file.text();
  consentToggle.checked = false;
  input.dispatchEvent(new Event("input"));
}

async function loadPreview() {
  try {
    const response = await fetch("/api/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(basePayload()) });
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
    const requestBody = JSON.stringify(analysisPayload());
    apiKeyInput.value = "";
    apiKeyInput.type = "password";
    $("#toggleApiKey").textContent = "显示";
    const response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: requestBody });
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
    updateAnalyzeState();
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
  const accessLabel = data.access_mode === "user-key" ? "你的 Key · 用后即忘" : data.access_mode === "server-key" ? "站点模型" : data.engine === "local-demo" ? "未调用模型" : "模型调用";
  $("#engineBadge").textContent = data.engine === "local-demo" ? `LOCAL PREVIEW · ${accessLabel}` : `${data.engine} · ${accessLabel}`;
  $("#confidenceNote").textContent = r.confidence_note || "";
  $("#closingLetter").textContent = r.closing_letter || "";
  renderStats(data.stats);
  renderWordCloud(data.stats.word_cloud || [], r.topics || []);
  renderFunFacts(data.stats);
  renderActivityHeatmap(data.stats);
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
  const cards = [[formatNumber(stats.message_count), "条消息"], [formatNumber(stats.active_days), "个活跃日"], [days, "天的跨度"], [`${Number(stats.late_night_ratio || 0)}%`, "发生在深夜"]];
  $("#statsCards").innerHTML = cards.map(([value, label]) => `<div class="stat-card"><b>${value}</b><span>${label}</span></div>`).join("");
}

function renderWordCloud(localWords, topics) {
  const merged = new Map();
  localWords.forEach(item => merged.set(String(item.text || ""), Number(item.weight || 1)));
  topics.forEach(item => {
    const name = String(item.name || "").trim();
    if (name) merged.set(name, Math.max(merged.get(name) || 0, Math.max(2, Math.min(5, Math.ceil(Number(item.share || 0) / 12)))));
  });
  const words = [...merged.entries()].filter(([text]) => text).sort((a, b) => b[1] - a[1]).slice(0, 32);
  $("#wordCloud").innerHTML = words.length
    ? words.map(([text, weight], index) => `<span class="cloud-word level-${Math.max(1, Math.min(5, weight))} tone-${index % 4}">${escapeHtml(text)}</span>`).join("")
    : "<p>还没有足够的高频词。</p>";
}

function renderFunFacts(stats) {
  const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const hour = stats.busiest_hour == null ? "—" : `${String(stats.busiest_hour).padStart(2, "0")}:00`;
  const reply = stats.median_reply_minutes == null
    ? "—"
    : stats.median_reply_minutes < 60
      ? `${Math.round(stats.median_reply_minutes)} 分钟`
      : `${(stats.median_reply_minutes / 60).toFixed(1)} 小时`;
  const items = [
    [stats.busiest_day ? stats.busiest_day.slice(5).replace("-", " / ") : "—", `最热闹的一天 · ${formatNumber(stats.busiest_day_count)} 条`],
    [`${formatNumber(stats.longest_streak_days)} 天`, "最长连续有话说"],
    [hour, `最常出现的时刻 · ${stats.busiest_weekday == null ? "—" : weekdays[stats.busiest_weekday]}`],
    [reply, "跨说话者中位回应间隔"],
  ];
  $("#funFacts").innerHTML = items.map(([value, label], index) => `<div class="fun-fact tone-${index}"><b>${escapeHtml(value)}</b><span>${escapeHtml(label)}</span></div>`).join("");
}

function renderActivityHeatmap(stats) {
  const entries = Object.entries(stats.daily_counts || {}).sort(([a], [b]) => a.localeCompare(b));
  if (!entries.length) {
    $("#activityHeatmap").innerHTML = "<p>还没有足够的日期数据。</p>";
    $("#heatmapCaption").textContent = "";
    return;
  }
  const parseDay = value => new Date(`${value}T00:00:00`);
  const formatDay = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  const end = parseDay(entries[entries.length - 1][0]);
  const earliest = parseDay(entries[0][0]);
  const capStart = new Date(end); capStart.setDate(end.getDate() - 365);
  const start = earliest < capStart ? capStart : earliest;
  const counts = Object.fromEntries(entries);
  const maximum = Math.max(...entries.map(([, count]) => Number(count || 0)), 1);
  const cells = Array(start.getDay() === 0 ? 6 : start.getDay() - 1).fill('<span class="heat-cell empty"></span>');
  for (const cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) {
    const date = formatDay(cursor);
    const count = Number(counts[date] || 0);
    const level = count ? Math.max(1, Math.ceil(count / maximum * 4)) : 0;
    cells.push(`<span class="heat-cell level-${level}" title="${date} · ${count} 条消息" aria-label="${date}，${count} 条消息"></span>`);
  }
  $("#activityHeatmap").innerHTML = `<div class="heatmap-grid">${cells.join("")}</div>`;
  const capped = earliest < capStart ? "最近 365 天" : `${entries[0][0]} 至 ${entries[entries.length - 1][0]}`;
  $("#heatmapCaption").textContent = `${capped} · 共 ${formatNumber(stats.active_days)} 个活跃日，颜色越深代表当天消息越多。`;
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
  const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "chat-later-yearbook.json" });
  link.click(); URL.revokeObjectURL(link.href);
});

function formatNumber(value) { return new Intl.NumberFormat("zh-CN").format(Number(value || 0)); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }

async function loadRuntimeConfig() {
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    const config = await response.json();
    if (!response.ok) throw new Error("config unavailable");
    $("#apiModeStatus").textContent = config.server_key_configured
      ? "站点已配置模型；你也可以填写自己的 Key。"
      : "站点未提供公共额度：填写自己的 Key 调用模型，留空体验本地预览。";
  } catch (_) {
    $("#apiModeStatus").textContent = "无法读取站点配置；你仍可填写自己的 Key。";
  }
}

loadRuntimeConfig();
replaySavedResult();
