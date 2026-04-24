const state = {
  sessions: [],
  currentSessionId: null,
  currentIterationId: null,
  currentIterations: [],
};

const el = {
  sessionList: document.getElementById("session-list"),
  newSession: document.getElementById("new-session"),
  model: document.getElementById("model"),
  embedModel: document.getElementById("embed-model"),
  topK: document.getElementById("top-k"),
  temperature: document.getElementById("temperature"),
  outputPath: document.getElementById("output-path"),
  compilerCsvPath: document.getElementById("compiler-csv-path"),
  task: document.getElementById("task"),
  compilerErrors: document.getElementById("compiler-errors"),
  existingCode: document.getElementById("existing-code"),
  labelNotes: document.getElementById("label-notes"),
  generate: document.getElementById("generate"),
  saveCode: document.getElementById("save-code"),
  loadCsv: document.getElementById("load-csv"),
  repairCsv: document.getElementById("repair-csv"),
  exportTraining: document.getElementById("export-training"),
  markGood: document.getElementById("mark-good"),
  markBad: document.getElementById("mark-bad"),
  status: document.getElementById("status"),
  answer: document.getElementById("answer"),
  sources: document.getElementById("sources"),
  history: document.getElementById("history"),
  iterationMeta: document.getElementById("iteration-meta"),
  compareIteration: document.getElementById("compare-iteration"),
  viewDiff: document.getElementById("view-diff"),
  diffOutput: document.getElementById("diff-output"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function setStatus(message) {
  el.status.textContent = message;
}

function badgeClass(label) {
  return label === "good" || label === "bad" ? label : "unreviewed";
}

function renderSessions() {
  el.sessionList.innerHTML = "";
  state.sessions.forEach((session) => {
    const button = document.createElement("button");
    button.className = `session-item${session.id === state.currentSessionId ? " active" : ""}`;
    button.innerHTML = `
      <div class="session-title">${escapeHtml(session.title)}</div>
      <div class="session-meta">
        ${session.iteration_count || 0} iterations | ${session.good_count || 0} good | ${session.bad_count || 0} bad
      </div>
    `;
    button.addEventListener("click", () => loadSession(session.id));
    el.sessionList.appendChild(button);
  });
}

function renderIteration(iteration) {
  state.currentIterationId = iteration ? iteration.id : null;
  el.answer.textContent = iteration ? iteration.answer : "";
  el.sources.innerHTML = "";
  el.iterationMeta.textContent = iteration
    ? `Iteration ${iteration.id} | ${iteration.label} | ${iteration.model}`
    : "";

  if (!iteration) {
    el.diffOutput.textContent = "";
    return;
  }

  el.task.value = iteration.user_task || "";
  el.compilerErrors.value = iteration.compiler_errors || "";
  el.existingCode.value = iteration.code || iteration.existing_code || "";
  el.outputPath.value = iteration.output_path || el.outputPath.value;
  el.labelNotes.value = iteration.label_notes || "";

  iteration.sources.forEach((source) => {
    const div = document.createElement("div");
    div.className = "source-item";
    div.innerHTML = `
      <div><a href="${source.url}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a></div>
      <div class="meta">chunk ${source.chunk_index} | score ${Number(source.score).toFixed(4)}</div>
    `;
    el.sources.appendChild(div);
  });
  renderCompareOptions();
}

function renderHistory() {
  el.history.innerHTML = "";
  state.currentIterations
    .slice()
    .reverse()
    .forEach((iteration) => {
      const row = document.createElement("div");
      row.className = "history-item";
      row.innerHTML = `
        <div class="panel-header">
          <div>
            <div><strong>${escapeHtml(iteration.user_task.slice(0, 90) || "Untitled iteration")}</strong></div>
            <div class="history-meta">${iteration.created_at}</div>
          </div>
          <span class="badge ${badgeClass(iteration.label)}">${escapeHtml(iteration.label)}</span>
        </div>
        <div class="artifact">${iteration.artifact_path ? `Artifact: ${escapeHtml(iteration.artifact_path)}` : "No artifact saved yet."}</div>
      `;
      const actions = document.createElement("div");
      actions.className = "history-actions";

      const loadBtn = document.createElement("button");
      loadBtn.className = "secondary-btn";
      loadBtn.textContent = "Load";
      loadBtn.addEventListener("click", () => renderIteration(iteration));
      actions.appendChild(loadBtn);

      row.appendChild(actions);
      el.history.appendChild(row);
    });
}

function renderCompareOptions() {
  const currentId = state.currentIterationId;
  el.compareIteration.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select iteration";
  el.compareIteration.appendChild(placeholder);

  state.currentIterations
    .filter((iteration) => iteration.id !== currentId)
    .forEach((iteration) => {
      const option = document.createElement("option");
      option.value = iteration.id;
      option.textContent = `#${iteration.id} | ${iteration.label} | ${iteration.created_at}`;
      el.compareIteration.appendChild(option);
    });
}

async function loadSessions() {
  const data = await api("/api/sessions");
  state.sessions = data.sessions;
  if (!state.sessions.length) {
    const created = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title: "Session " + new Date().toLocaleString() }),
    });
    state.sessions = [created];
  }
  if (!state.currentSessionId) {
    state.currentSessionId = state.sessions[0].id;
  }
  renderSessions();
  await loadSession(state.currentSessionId);
}

async function loadSession(sessionId) {
  const session = await api(`/api/sessions/${sessionId}`);
  state.currentSessionId = session.id;
  state.currentIterations = session.iterations;
  renderSessions();
  renderHistory();
  renderIteration(session.iterations[session.iterations.length - 1] || null);
  renderCompareOptions();
  setStatus(`Loaded session "${session.title}".`);
}

async function loadModels() {
  const data = await api("/api/models");
  el.model.innerHTML = "";
  data.models.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === "qwen3-coder:30b") {
      option.selected = true;
    }
    el.model.appendChild(option);
  });
}

async function generate() {
  if (!state.currentSessionId) {
    return;
  }
  setStatus("Generating...");
  const payload = {
    task: el.task.value,
    existing_code: el.existingCode.value,
    compiler_errors: el.compilerErrors.value,
    model: el.model.value,
    embed_model: el.embedModel.value,
    top_k: Number(el.topK.value),
    temperature: Number(el.temperature.value),
    output_path: el.outputPath.value,
  };
  const iteration = await api(`/api/sessions/${state.currentSessionId}/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.currentIterations.push(iteration);
  renderIteration(iteration);
  renderHistory();
  renderCompareOptions();
  await refreshSessions();
  setStatus(`Generated iteration ${iteration.id}.`);
}

async function markIteration(label) {
  if (!state.currentIterationId) {
    setStatus("Generate or load an iteration first.");
    return;
  }
  const payload = {
    label,
    notes: el.labelNotes.value,
    compiler_errors: el.compilerErrors.value,
  };
  const updated = await api(`/api/iterations/${state.currentIterationId}/label`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const index = state.currentIterations.findIndex((item) => item.id === updated.id);
  if (index >= 0) {
    state.currentIterations[index] = updated;
  }
  renderIteration(updated);
  renderHistory();
  renderCompareOptions();
  await refreshSessions();
  setStatus(`Iteration ${updated.id} marked ${label}.`);
}

async function saveCode() {
  if (!state.currentIterationId) {
    setStatus("No iteration selected.");
    return;
  }
  if (!el.outputPath.value.trim()) {
    setStatus("Enter a save path first.");
    return;
  }
  const updated = await api(`/api/iterations/${state.currentIterationId}/save`, {
    method: "POST",
    body: JSON.stringify({
      output_path: el.outputPath.value,
      code: el.existingCode.value,
    }),
  });
  const index = state.currentIterations.findIndex((item) => item.id === updated.id);
  if (index >= 0) {
    state.currentIterations[index] = updated;
  }
  renderIteration(updated);
  renderCompareOptions();
  await refreshSessions();
  setStatus(`Saved code to ${updated.output_path}.`);
}

async function loadCompilerCsv() {
  if (!el.compilerCsvPath.value.trim()) {
    setStatus("Enter a compiler CSV path first.");
    return;
  }
  setStatus("Loading compiler CSV...");
  const path = encodeURIComponent(el.compilerCsvPath.value.trim());
  const loaded = await api(`/api/compiler-errors/load?path=${path}`);
  el.compilerErrors.value = loaded.text || "";
  setStatus(`Loaded ${loaded.count} compiler errors from ${loaded.path}.`);
}

async function repairFromCsv() {
  if (!state.currentSessionId) {
    return;
  }
  if (!el.compilerCsvPath.value.trim()) {
    setStatus("Enter a compiler CSV path first.");
    return;
  }
  setStatus("Repairing from compiler CSV...");
  const payload = {
    task:
      el.task.value.trim() ||
      "Fix this NinjaTrader script so it compiles and preserves the intended behavior.",
    existing_code: el.existingCode.value,
    compiler_errors: "",
    compiler_errors_csv_path: el.compilerCsvPath.value.trim(),
    model: el.model.value,
    embed_model: el.embedModel.value,
    top_k: Number(el.topK.value),
    temperature: Number(el.temperature.value),
    output_path: el.outputPath.value,
  };
  const iteration = await api(`/api/sessions/${state.currentSessionId}/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.currentIterations.push(iteration);
  renderIteration(iteration);
  renderHistory();
  renderCompareOptions();
  await refreshSessions();
  setStatus(`Generated repair iteration ${iteration.id} from compiler CSV.`);
}

async function viewDiff() {
  if (!state.currentIterationId) {
    setStatus("Load an iteration first.");
    return;
  }
  if (!el.compareIteration.value) {
    setStatus("Choose another iteration to compare against.");
    return;
  }
  const diff = await api(
    `/api/iterations/${state.currentIterationId}/diff?other_id=${encodeURIComponent(
      el.compareIteration.value
    )}`
  );
  el.diffOutput.textContent = diff.diff || "No code differences.";
  setStatus(`Compared iteration ${diff.left_iteration_id} with iteration ${diff.right_iteration_id}.`);
}

async function exportTraining() {
  setStatus("Exporting training set...");
  const summary = await api("/api/export", {
    method: "POST",
    body: JSON.stringify({}),
  });
  setStatus(
    `Exported ${summary.good_examples} good and ${summary.bad_examples} bad examples to ${summary.export_dir}.`
  );
}

async function refreshSessions() {
  const data = await api("/api/sessions");
  state.sessions = data.sessions;
  renderSessions();
}

async function createSession() {
  const title = window.prompt("Session name", "New strategy review");
  if (title === null) {
    return;
  }
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  state.sessions.unshift(session);
  await loadSession(session.id);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

el.generate.addEventListener("click", () => generate().catch((error) => setStatus(error.message)));
el.markGood.addEventListener("click", () => markIteration("good").catch((error) => setStatus(error.message)));
el.markBad.addEventListener("click", () => markIteration("bad").catch((error) => setStatus(error.message)));
el.saveCode.addEventListener("click", () => saveCode().catch((error) => setStatus(error.message)));
el.loadCsv.addEventListener("click", () => loadCompilerCsv().catch((error) => setStatus(error.message)));
el.repairCsv.addEventListener("click", () => repairFromCsv().catch((error) => setStatus(error.message)));
el.viewDiff.addEventListener("click", () => viewDiff().catch((error) => setStatus(error.message)));
el.exportTraining.addEventListener("click", () => exportTraining().catch((error) => setStatus(error.message)));
el.newSession.addEventListener("click", () => createSession().catch((error) => setStatus(error.message)));

Promise.all([loadModels(), loadSessions()]).catch((error) => setStatus(error.message));
