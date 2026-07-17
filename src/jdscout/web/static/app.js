// JD-Scout 前端交互。
// 关键点: 我们要 POST 一个文件(FormData), 而浏览器原生 EventSource 只支持 GET,
// 所以用 fetch() 拿到 response.body 这个可读流, 手动解析 SSE(按 \n\n 切分事件)。

const $ = (sel) => document.querySelector(sel);

const els = {
  jd: $("#jd-text"),
  file: $("#resume-file"),
  fileDrop: $("#file-drop"),
  fileName: $("#file-name"),
  btn: $("#analyze-btn"),
  inputError: $("#input-error"),
  progressPanel: $("#progress-panel"),
  resultPanel: $("#result-panel"),
  steps: $("#steps"),
};

// 文件选择反馈
els.file.addEventListener("change", () => {
  const f = els.file.files[0];
  if (f) {
    els.fileName.textContent = f.name;
    els.fileDrop.classList.add("has-file");
  }
});

els.btn.addEventListener("click", startAnalysis);

function showError(msg) {
  els.inputError.textContent = msg;
  els.inputError.hidden = false;
}

function resetSteps() {
  els.steps.querySelectorAll(".step").forEach((li) => {
    li.classList.remove("running", "done", "error");
    li.querySelector(".step-icon").textContent = "○";
  });
}

function setStep(node, state) {
  const li = els.steps.querySelector(`.step[data-node="${node}"]`);
  if (!li) return;
  li.classList.remove("running", "done", "error");
  li.classList.add(state);
  const icon = li.querySelector(".step-icon");
  icon.textContent = state === "running" ? "◐" : state === "done" ? "✓" : state === "error" ? "✕" : "○";
}

async function startAnalysis() {
  const jd = els.jd.value.trim();
  const file = els.file.files[0];
  els.inputError.hidden = true;

  if (jd.length < 200) return showError("JD 文本太短(至少 200 字),请粘贴完整 JD。");
  if (!file) return showError("请上传简历 PDF。");

  els.btn.disabled = true;
  els.btn.textContent = "分析中…";
  els.progressPanel.hidden = false;
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
    els.btn.textContent = "开始分析";
  }
}

// 解析 fetch 流为一个个 SSE 事件。SSE 以空行(\n\n)分隔事件, 每个事件里
// "event:" 是类型、"data:" 是负载。
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
  let type = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { type, data: JSON.parse(data) };
  } catch {
    return { type, data };
  }
}

function handleEvent(type, data) {
  if (type === "node_start") setStep(data.node, "running");
  else if (type === "node_end") setStep(data.node, "done");
  else if (type === "final_result") renderResult(data);
  else if (type === "error") {
    els.steps.querySelectorAll(".step.running").forEach((li) => setStep(li.dataset.node, "error"));
    showError(data.message || "分析出错。");
  }
}

// ---------- 渲染结果 ----------
function renderResult(report) {
  els.resultPanel.hidden = false;

  // 若有节点软错误, 提示但仍尽量展示已有结果
  if (report.errors && report.errors.length) {
    showError("部分步骤未完成:" + report.errors.join("; "));
  }

  const gap = report.gap;
  const advice = report.advice;

  // 匹配度环形
  if (gap) {
    const score = gap.overall_match_score;
    $("#score-num").textContent = score;
    const deg = Math.round((score / 100) * 360);
    $("#score-ring").style.background =
      `conic-gradient(var(--accent-light) ${deg}deg, var(--panel-2) ${deg}deg)`;

    // 技能表
    const body = $("#skills-body");
    body.innerHTML = "";
    (gap.skill_matches || []).forEach((sm) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td class="skill-name">${escapeHtml(sm.skill)}</td>` +
        `<td><span class="status-tag ${sm.status}">${sm.status}</span></td>` +
        `<td class="evidence">${escapeHtml(sm.evidence || "")}</td>`;
      body.appendChild(tr);
    });
  }

  // 建议
  if (advice) {
    const badge = $("#apply-badge");
    badge.textContent = applyLabel(advice.should_apply);
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
        `<div class="why">💡 ${escapeHtml(b.rationale)}</div>`;
      rw.appendChild(div);
    });

    const prep = $("#prep-list");
    prep.innerHTML = "";
    (advice.interview_prep_focus || []).forEach((p) => {
      const li = document.createElement("li");
      li.innerHTML = marked.parseInline(p);
      prep.appendChild(li);
    });
  }
}

function applyLabel(v) {
  return {
    strongly_recommend: "强烈推荐投递",
    worth_trying: "值得一试",
    stretch: "冲刺型",
    not_recommended: "不建议投递",
  }[v] || v;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}
