// JD-Scout 前端交互。
// SSE: 要 POST 文件(FormData), 原生 EventSource 只支持 GET, 所以用 fetch 拿可读流手动解析。

const $ = (sel) => document.querySelector(sel);

// ---- Lucide 图标(inline SVG path, currentColor 描边, 自动跟随主题色) ----
const ICONS = {
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  circleCheck: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  triangle: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  circleX: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
  award: '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
  thumbsUp: '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
};
function svg(name, size = 16) {
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
}

const els = {
  jd: $("#jd-text"),
  file: $("#resume-file"),
  fileDrop: $("#file-drop"),
  fileName: $("#file-name"),
  btn: $("#analyze-btn"),
  inputError: $("#input-error"),
  inputPanel: $("#input-panel"),
  resultPanel: $("#result-panel"),
  stepper: $("#stepper"),
  sidebar: $("#sidebar"),
  scrim: $("#sidebar-scrim"),
  hamburger: $("#hamburger"),
  newBtn: $("#new-analysis-btn"),
  historyList: $("#history-list"),
  historyCount: $("#history-count"),
};

const APPLY = {
  strongly_recommend: { label: "强烈推荐投递", short: "强烈推荐", icon: "award" },
  worth_trying: { label: "值得一试", short: "值得一试", icon: "thumbsUp" },
  stretch: { label: "冲刺型", short: "冲刺型", icon: "triangle" },
  not_recommended: { label: "不建议投递", short: "不建议", icon: "circleX" },
};
const STATUS_ICON = { matched: "circleCheck", partial: "triangle", missing: "circleX" };

let activeHistoryId = null;

// ---------- 初始化 ----------
els.file.addEventListener("change", () => {
  const f = els.file.files[0];
  if (f) { els.fileName.textContent = f.name; els.fileDrop.classList.add("has-file"); }
});
els.btn.addEventListener("click", startAnalysis);
els.newBtn.addEventListener("click", () => { showInputView(); closeSidebar(); });
els.hamburger.addEventListener("click", toggleSidebar);
els.scrim.addEventListener("click", closeSidebar);
loadHistory();

// ---------- Sidebar 开关(移动端) ----------
function toggleSidebar() {
  const open = els.sidebar.classList.toggle("open");
  els.scrim.classList.toggle("show", open);
}
function closeSidebar() {
  els.sidebar.classList.remove("open");
  els.scrim.classList.remove("show");
}

// ---------- 视图切换 ----------
function showInputView() {
  els.inputPanel.hidden = false;
  els.resultPanel.hidden = true;
  els.inputError.hidden = true;
  els.jd.value = "";
  els.file.value = "";
  els.fileName.textContent = "点击选择 PDF 简历";
  els.fileDrop.classList.remove("has-file");
  resetSteps();
  setActiveHistory(null);
}

function showError(msg) { els.inputError.textContent = msg; els.inputError.hidden = false; }

// ---------- 进度条 ----------
function resetSteps() {
  els.stepper.querySelectorAll(".step").forEach((li) => {
    li.classList.remove("running", "done", "error");
    li.querySelector(".dot").innerHTML = "";
  });
}
function setStep(node, state) {
  const li = els.stepper.querySelector(`.step[data-node="${node}"]`);
  if (!li) return;
  li.classList.remove("running", "done", "error");
  li.classList.add(state);
  const dot = li.querySelector(".dot");
  dot.innerHTML = state === "done" ? svg("check", 16) : state === "error" ? svg("x", 16) : "";
}
function markAllStepsDone() {
  els.stepper.querySelectorAll(".step").forEach((li) => setStep(li.dataset.node, "done"));
}

// ---------- 分析(SSE) ----------
async function startAnalysis() {
  const jd = els.jd.value.trim();
  const file = els.file.files[0];
  els.inputError.hidden = true;

  if (jd.length < 200) return showError("JD 文本太短(至少 200 字),请粘贴完整 JD。");
  if (!file) return showError("请上传简历 PDF。");

  els.btn.disabled = true;
  els.btn.innerHTML = "分析中…";
  els.resultPanel.hidden = true;
  resetSteps();

  const form = new FormData();
  form.append("jd_text", jd);
  form.append("resume_file", file);

  try {
    const resp = await fetch("/api/analyze/stream", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err?.detail?.message || `请求失败 (${resp.status})`);
    }
    await consumeSSE(resp.body, handleEvent);
  } catch (e) {
    showError(e.message || "分析失败,请重试。");
  } finally {
    els.btn.disabled = false;
    els.btn.innerHTML = `${svg("play", 18)} 开始分析`;
  }
}

async function consumeSSE(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const evt = parseEvent(raw);
      if (evt) onEvent(evt.type, evt.data);
    }
  }
}
function parseEvent(raw) {
  let type = "message", data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try { return { type, data: JSON.parse(data) }; }
  catch { return { type, data }; }
}
function handleEvent(type, data) {
  if (type === "node_start") setStep(data.node, "running");
  else if (type === "node_end") setStep(data.node, "done");
  else if (type === "final_result") {
    renderResult(data);
    // 分析产生了新历史 -> 刷新列表并高亮
    if (data.history_id) { loadHistory().then(() => setActiveHistory(data.history_id)); }
  } else if (type === "error") {
    els.stepper.querySelectorAll(".step.running").forEach((li) => setStep(li.dataset.node, "error"));
    showError(data.message || "分析出错。");
  }
}

// ---------- 渲染结果 ----------
function renderResult(report) {
  els.resultPanel.hidden = false;
  if (report.errors && report.errors.length) {
    showError("部分步骤未完成:" + report.errors.join("; "));
  }

  const gap = report.gap;
  const advice = report.advice;

  if (gap) {
    $("#score-num").textContent = gap.overall_match_score;
    const deg = Math.round((gap.overall_match_score / 100) * 360);
    $("#score-ring").style.background =
      `conic-gradient(var(--accent) ${deg}deg, var(--bg-secondary) ${deg}deg)`;
    renderSkills(gap.skill_matches || []);
  } else {
    $("#score-num").textContent = "–";
    $("#skills").innerHTML = "";
  }

  if (advice) {
    const badge = $("#apply-badge");
    const meta = APPLY[advice.should_apply] || { label: advice.should_apply, icon: "triangle" };
    badge.innerHTML = svg(meta.icon, 16) + `<span>${meta.label}</span>`;
    badge.className = "badge " + advice.should_apply;
    $("#apply-reason").textContent = advice.should_apply_reason || "";

    const rw = $("#rewrites");
    rw.innerHTML = "";
    (advice.bullet_rewrites || []).forEach((b) => {
      const div = document.createElement("div");
      div.className = "rewrite";
      div.innerHTML =
        `<div class="orig">${escapeHtml(b.original)}</div>` +
        `<div class="new">${marked.parseInline(b.rewritten || "")}</div>` +
        `<div class="why">${escapeHtml(b.rationale)}</div>`;
      rw.appendChild(div);
    });
    fillList("#prep-list", advice.interview_prep_focus || []);
    const qs = advice.questions_to_ask_interviewer || [];
    $("#questions-block").hidden = qs.length === 0;
    fillList("#questions-list", qs);
  } else {
    $("#apply-badge").innerHTML = "无建议";
    $("#apply-badge").className = "badge";
    $("#apply-reason").textContent = "";
    $("#rewrites").innerHTML = "";
    fillList("#prep-list", []);
    $("#questions-block").hidden = true;
  }

  renderSimilar(report.similar_histories || []);
}

// 相似投递参考卡片
function renderSimilar(similar) {
  const block = $("#similar-block");
  const host = $("#similar-cards");
  if (!similar.length) { block.hidden = true; host.innerHTML = ""; return; }
  block.hidden = false;
  host.innerHTML = "";
  similar.forEach((s) => {
    const applyMeta = APPLY[s.should_apply];
    const card = document.createElement("div");
    card.className = "similar-card";
    card.innerHTML =
      `<div class="sc-summary">${escapeHtml(s.jd_summary)}</div>` +
      `<div class="sc-mid">` +
        `<span class="sc-score">${s.match_score != null ? s.match_score : "–"}</span>` +
        (applyMeta ? `<span class="sc-badge ${s.should_apply}">${svg(applyMeta.icon, 12)}${applyMeta.short}</span>` : "") +
      `</div>` +
      `<div class="sc-foot">` +
        `<span class="sc-sim">${Math.round((s.similarity_score || 0) * 100)}% 相似</span>` +
        `<span>${relativeTime(s.created_at)}</span>` +
      `</div>`;
    card.addEventListener("click", () => openHistory(s.history_id));
    host.appendChild(card);
  });
}

// ISO 时间 -> 相对(如 "3 天前")
function relativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const sec = Math.max(0, Math.round((now - then) / 1000));
  if (sec < 60) return "刚刚";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day} 天前`;
  const mon = Math.round(day / 30);
  if (mon < 12) return `${mon} 个月前`;
  return `${Math.round(mon / 12)} 年前`;
}

function renderSkills(matches) {
  const groups = { matched: [], partial: [], missing: [] };
  matches.forEach((sm) => (groups[sm.status] || (groups[sm.status] = [])).push(sm));

  const host = $("#skills");
  host.innerHTML = "";

  if (groups.matched.length) {
    const wrap = document.createElement("div");
    wrap.className = "skill-group";
    const header = document.createElement("div");
    header.className = "group-header matched collapsed";
    header.innerHTML =
      svg("circleCheck", 16) +
      `<span>${groups.matched.length} 项完全匹配</span>` +
      `<span class="chevron">${svg("chevron", 16)}</span>`;
    const list = document.createElement("div");
    list.className = "skill-list collapsed";
    groups.matched.forEach((sm) => list.appendChild(skillRow(sm)));
    header.addEventListener("click", () => {
      const collapsed = list.classList.toggle("collapsed");
      header.classList.toggle("collapsed", collapsed);
    });
    wrap.appendChild(header);
    wrap.appendChild(list);
    host.appendChild(wrap);
  }
  ["partial", "missing"].forEach((status) => {
    (groups[status] || []).forEach((sm) => host.appendChild(skillRow(sm)));
  });
}
function skillRow(sm) {
  const row = document.createElement("div");
  row.className = "skill-row " + sm.status;
  row.innerHTML =
    svg(STATUS_ICON[sm.status] || "triangle", 16) +
    `<span class="s-name">${escapeHtml(sm.skill)}</span>` +
    `<span class="s-evidence">${escapeHtml(sm.evidence || "")}</span>`;
  return row;
}
function fillList(sel, items) {
  const ul = $(sel);
  ul.innerHTML = "";
  items.forEach((p) => {
    const li = document.createElement("li");
    li.innerHTML = marked.parseInline(p);
    ul.appendChild(li);
  });
}

// ---------- History sidebar ----------
async function loadHistory() {
  let entries = [];
  try {
    const resp = await fetch("/api/history");
    if (resp.ok) entries = await resp.json();
  } catch { /* 离线时静默 */ }

  els.historyCount.textContent = `历史 (${entries.length})`;
  els.historyList.innerHTML = "";

  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "还没有记录,跑一次分析试试。";
    els.historyList.appendChild(empty);
    return;
  }

  // 按日期分组渲染
  let lastGroup = null;
  entries.forEach((e) => {
    const g = dateGroup(e.created_at);
    if (g !== lastGroup) {
      const label = document.createElement("div");
      label.className = "history-group-label";
      label.textContent = g;
      els.historyList.appendChild(label);
      lastGroup = g;
    }
    els.historyList.appendChild(historyItem(e));
  });

  if (activeHistoryId) setActiveHistory(activeHistoryId);
}

function historyItem(e) {
  const item = document.createElement("div");
  item.className = "history-item";
  item.dataset.id = e.id;

  const applyShort = APPLY[e.should_apply]?.short || e.should_apply || "";
  const metaBits = [e.match_score != null ? e.match_score : "–", applyShort].filter(Boolean).join(" · ");

  item.innerHTML =
    `<div class="hi-summary">${escapeHtml(e.jd_summary)}</div>` +
    `<div class="hi-meta"><span>${escapeHtml(metaBits)}</span></div>` +
    `<button class="hi-del" title="删除">${svg("trash", 15)}</button>`;

  item.addEventListener("click", (ev) => {
    if (ev.target.closest(".hi-del")) return;   // 点删除不算打开
    openHistory(e.id);
  });
  item.querySelector(".hi-del").addEventListener("click", (ev) => {
    ev.stopPropagation();
    deleteHistory(e.id);
  });
  return item;
}

async function openHistory(id) {
  try {
    const resp = await fetch(`/api/history/${id}`);
    if (!resp.ok) throw new Error("加载失败");
    const detail = await resp.json();
    els.inputPanel.hidden = true;      // 切到详情视图
    markAllStepsDone();
    renderResult(detail.full_result || {});
    setActiveHistory(id);
    closeSidebar();
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch {
    showError("加载历史详情失败。");
  }
}

async function deleteHistory(id) {
  if (!window.confirm("确认删除这条分析吗?")) return;
  try {
    const resp = await fetch(`/api/history/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new Error();
    if (activeHistoryId === id) { activeHistoryId = null; showInputView(); }
    await loadHistory();
  } catch {
    showError("删除失败。");
  }
}

function setActiveHistory(id) {
  activeHistoryId = id;
  els.historyList.querySelectorAll(".history-item").forEach((it) => {
    it.classList.toggle("active", Number(it.dataset.id) === id);
  });
}

// 今天 / 昨天 / 本周 / 更早
function dateGroup(iso) {
  const d = new Date(iso);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startYesterday = new Date(startToday); startYesterday.setDate(startToday.getDate() - 1);
  const mondayOffset = (startToday.getDay() + 6) % 7;   // 0=周一
  const startWeek = new Date(startToday); startWeek.setDate(startToday.getDate() - mondayOffset);
  if (d >= startToday) return "今天";
  if (d >= startYesterday) return "昨天";
  if (d >= startWeek) return "本周";
  return "更早";
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}
