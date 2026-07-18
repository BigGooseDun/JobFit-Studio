// JD-Scout 前端交互。
// SSE: 要 POST 文件(FormData), 原生 EventSource 只支持 GET, 所以用 fetch 拿可读流手动解析。

const $ = (sel) => document.querySelector(sel);

// ---- Lucide 图标(inline SVG path, 用 currentColor 描边, 不依赖外部图标库) ----
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
  resultPanel: $("#result-panel"),
  stepper: $("#stepper"),
};

els.file.addEventListener("change", () => {
  const f = els.file.files[0];
  if (f) { els.fileName.textContent = f.name; els.fileDrop.classList.add("has-file"); }
});
els.btn.addEventListener("click", startAnalysis);

function showError(msg) { els.inputError.textContent = msg; els.inputError.hidden = false; }

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

// 解析 fetch 流为 SSE 事件(以空行 \n\n 分隔, event:/data: 行)。
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
  else if (type === "final_result") renderResult(data);
  else if (type === "error") {
    els.stepper.querySelectorAll(".step.running").forEach((li) => setStep(li.dataset.node, "error"));
    showError(data.message || "分析出错。");
  }
}

// ---------- 渲染结果 ----------
const APPLY = {
  strongly_recommend: { label: "强烈推荐投递", icon: "award" },
  worth_trying: { label: "值得一试", icon: "thumbsUp" },
  stretch: { label: "冲刺型", icon: "triangle" },
  not_recommended: { label: "不建议投递", icon: "circleX" },
};
const STATUS_ICON = { matched: "circleCheck", partial: "triangle", missing: "circleX" };

function renderResult(report) {
  els.resultPanel.hidden = false;
  if (report.errors && report.errors.length) {
    showError("部分步骤未完成:" + report.errors.join("; "));
  }

  const gap = report.gap;
  const advice = report.advice;

  if (gap) {
    const score = gap.overall_match_score;
    $("#score-num").textContent = score;
    const deg = Math.round((score / 100) * 360);
    $("#score-ring").style.background =
      `conic-gradient(var(--accent) ${deg}deg, var(--bg-secondary) ${deg}deg)`;
    renderSkills(gap.skill_matches || []);
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
  }
}

// 技能三色分组:matched 组默认折叠成一行"N 项完全匹配", 点击展开; partial/missing 展开。
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

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}
