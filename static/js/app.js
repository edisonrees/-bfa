(() => {
  const cfg = window.MOCKA || {};
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    tasks: [],
    stats: {},
    filter: "all",
    pollTimer: null,
  };

  const els = {
    form: $("#runForm"),
    usernames: $("#usernames"),
    source: $("#source"),
    file: $("#passwordFile"),
    passwords: $("#passwords"),
    stopOnFirst: $("#stopOnFirst"),
    dropzone: $("#dropzone"),
    fileMeta: $("#fileMeta"),
    fileName: $("#fileName"),
    fileCount: $("#fileCount"),
    filePreview: $("#filePreview"),
    pasteHint: $("#pasteHint"),
    submitBtn: $("#submitBtn"),
    submitLabel: $("#submitLabel"),
    taskList: $("#taskList"),
    emptyState: $("#emptyState"),
    clearFinished: $("#clearFinished"),
    healthPill: $("#healthPill"),
    boardSub: $("#boardSub"),
    toasts: $("#toasts"),
    dialog: $("#detailDialog"),
    detailTitle: $("#detailTitle"),
    detailBody: $("#detailBody"),
    copyExport: $("#copyExport"),
    downloadExport: $("#downloadExport"),
    statActive: $("#statActive"),
    statHits: $("#statHits"),
    statAttempts: $("#statAttempts"),
    statDone: $("#statDone"),
  };

  function toast(message, type = "info") {
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    node.textContent = message;
    els.toasts.appendChild(node);
    setTimeout(() => {
      node.style.opacity = "0";
      setTimeout(() => node.remove(), 220);
    }, 4200);
  }

  function setSource(source) {
    els.source.value = source;
    $$(".tab").forEach((tab) => {
      const active = tab.dataset.source === source;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    ["upload", "paste", "sample"].forEach((key) => {
      const panel = $(`#panel-${key}`);
      if (!panel) return;
      panel.hidden = key !== source;
      panel.classList.toggle("is-active", key === source);
    });
  }

  async function previewFile(file) {
    const body = new FormData();
    body.append("passwordFile", file);
    const res = await fetch("/api/preview", { method: "POST", body });
    const data = await res.json();
    if (!data.success) {
      toast(data.error || "Could not read file", "error");
      return;
    }
    els.fileMeta.hidden = false;
    els.fileName.textContent = data.filename || file.name;
    els.fileCount.textContent = `${data.password_count} passwords`;
    els.filePreview.innerHTML = (data.preview || [])
      .map((p) => `<span class="mini-chip">${escapeHtml(p)}</span>`)
      .join("");
  }

  function previewPaste() {
    const text = els.passwords.value;
    const lines = text
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#"));
    let count = 0;
    for (const line of lines) {
      if (line.includes(":")) {
        const right = line.split(":", 2)[1] || "";
        count += right.includes(",")
          ? right.split(",").filter((x) => x.trim()).length
          : right.trim()
            ? 1
            : 0;
      } else if (line.includes(",")) {
        count += line.split(",").filter((x) => x.trim()).length;
      } else {
        count += 1;
      }
    }
    els.pasteHint.textContent = `${count} password${count === 1 ? "" : "s"} parsed`;
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatEta(seconds) {
    if (seconds == null) return "—";
    if (seconds < 60) return `${Math.ceil(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.ceil(seconds % 60);
    return `${m}m ${s}s`;
  }

  function filteredTasks() {
    if (state.filter === "all") return state.tasks;
    if (state.filter === "hits") return state.tasks.filter((t) => t.successful_logins?.length);
    if (state.filter === "processing") {
      return state.tasks.filter((t) => t.status === "processing" || t.status === "pending");
    }
    return state.tasks.filter((t) => t.status === state.filter);
  }

  function renderStats(stats = {}) {
    els.statActive.textContent = stats.active ?? 0;
    els.statHits.textContent = stats.hits ?? 0;
    els.statAttempts.textContent = stats.attempts ?? 0;
    els.statDone.textContent =
      (stats.completed || 0) + (stats.failed || 0) + (stats.cancelled || 0);
    const active = stats.active || 0;
    els.boardSub.textContent = active
      ? `${active} run${active === 1 ? "" : "s"} in flight`
      : "Waiting for runs";
  }

  function renderTasks() {
    const tasks = filteredTasks();
    els.taskList.innerHTML = tasks.map(renderTask).join("");
    els.emptyState.hidden = tasks.length > 0;
  }

  function renderTask(task) {
    const names = (task.usernames && task.usernames.length
      ? task.usernames
      : [task.username]
    ).filter(Boolean);
    const title = names.slice(0, 3).join(", ") + (names.length > 3 ? ` +${names.length - 3}` : "");
    const pct = Math.min(100, Number(task.percent) || 0);
    const hits = (task.successful_logins || [])
      .map(
        (h) => `
      <div class="hit">
        <span>${escapeHtml(h.username)}:${escapeHtml(h.password)}</span>
        <button type="button" class="btn btn-ghost" data-copy="${escapeHtml(h.username)}:${escapeHtml(h.password)}">Copy</button>
      </div>`
      )
      .join("");

    const canCancel = task.status === "processing" || task.status === "pending";

    return `
      <article class="task" data-id="${task.task_id}">
        <div class="task-top">
          <div>
            <div class="task-title">${escapeHtml(title || "Untitled")}</div>
            <div class="task-id">${escapeHtml(task.task_id.slice(0, 8))} · ${escapeHtml(task.source || "upload")} · ${task.password_count || 0} pw</div>
          </div>
          <span class="status status-${escapeHtml(task.status)}">${escapeHtml(task.status)}</span>
        </div>
        <div class="progress"><i style="width:${pct}%"></i></div>
        <div class="task-meta">
          <span>${task.progress || 0}/${task.total || 0} (${pct}%)</span>
          <span>${task.attempts_per_second || 0}/s</span>
          <span>ETA ${formatEta(task.eta_seconds)}</span>
          ${task.error ? `<span style="color:var(--rose)">${escapeHtml(task.error)}</span>` : ""}
        </div>
        ${hits ? `<div class="hits">${hits}</div>` : ""}
        <div class="task-actions">
          ${canCancel ? `<button type="button" class="btn btn-ghost" data-cancel="${task.task_id}">Cancel</button>` : ""}
          <button type="button" class="btn btn-ghost" data-export="${task.task_id}">Export</button>
          <button type="button" class="btn btn-danger" data-delete="${task.task_id}">Delete</button>
        </div>
      </article>`;
  }

  async function refresh() {
    try {
      const res = await fetch("/api/tasks");
      const data = await res.json();
      if (!data.success) return;
      state.tasks = data.tasks || [];
      state.stats = data.stats || {};
      renderStats(state.stats);
      renderTasks();
    } catch {
      /* keep UI alive */
    }
  }

  async function checkHealth() {
    try {
      const res = await fetch("/health");
      const data = await res.json();
      if (data.status === "healthy") {
        els.healthPill.textContent = "online";
        els.healthPill.classList.remove("pill-down");
        els.healthPill.classList.add("pill-live");
      } else {
        throw new Error("unhealthy");
      }
    } catch {
      els.healthPill.textContent = "offline";
      els.healthPill.classList.remove("pill-live");
      els.healthPill.classList.add("pill-down");
    }
  }

  async function startRun(event) {
    event.preventDefault();
    const usernames = els.usernames.value.trim();
    if (!usernames) {
      toast("Add at least one username", "error");
      return;
    }

    const source = els.source.value;
    const body = new FormData();
    body.append("usernames", usernames);
    body.append("source", source);
    body.append("stop_on_first", els.stopOnFirst.checked ? "true" : "false");

    if (source === "upload") {
      if (!els.file.files.length) {
        toast("Choose a password file", "error");
        return;
      }
      body.append("passwordFile", els.file.files[0]);
    } else if (source === "paste") {
      if (!els.passwords.value.trim()) {
        toast("Paste at least one password", "error");
        return;
      }
      body.append("passwords", els.passwords.value);
    }

    els.submitBtn.disabled = true;
    els.submitLabel.textContent = "Starting…";

    try {
      const res = await fetch("/api/tasks", { method: "POST", body });
      const data = await res.json();
      if (!data.success) {
        toast(data.error || "Failed to start", "error");
        return;
      }
      toast(data.message || "Run started", "success");
      if (source === "upload") {
        els.file.value = "";
        els.fileMeta.hidden = true;
      }
      if (source === "paste") {
        els.passwords.value = "";
        previewPaste();
      }
      await refresh();
    } catch (err) {
      toast(String(err.message || err), "error");
    } finally {
      els.submitBtn.disabled = false;
      els.submitLabel.textContent = "Start run";
    }
  }

  async function cancelTask(id) {
    const res = await fetch(`/api/tasks/${id}/cancel`, { method: "POST" });
    const data = await res.json();
    toast(data.success ? "Cancel requested" : data.error || "Cancel failed", data.success ? "info" : "error");
    refresh();
  }

  async function deleteTask(id) {
    if (!confirm("Delete this run?")) return;
    const res = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
    const data = await res.json();
    toast(data.success ? "Deleted" : data.error || "Delete failed", data.success ? "success" : "error");
    refresh();
  }

  async function exportTask(id) {
    const res = await fetch(`/api/tasks/${id}/export`);
    const data = await res.json();
    if (!data.success) {
      toast(data.error || "Export failed", "error");
      return;
    }
    const json = JSON.stringify(data.export, null, 2);
    els.detailTitle.textContent = `Export ${id.slice(0, 8)}`;
    els.detailBody.textContent = json;
    els.downloadExport.href = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    els.downloadExport.download = `mocka-${id.slice(0, 8)}.json`;
    els.copyExport.onclick = async () => {
      await navigator.clipboard.writeText(json);
      toast("Copied export JSON", "success");
    };
    els.dialog.showModal();
  }

  // Events
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => setSource(tab.dataset.source)));

  $$(".chip[data-filter]").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.filter = chip.dataset.filter;
      $$(".chip[data-filter]").forEach((c) => c.classList.toggle("is-active", c === chip));
      renderTasks();
    });
  });

  els.form.addEventListener("submit", startRun);

  els.file.addEventListener("change", () => {
    if (els.file.files[0]) previewFile(els.file.files[0]);
  });

  ["dragenter", "dragover"].forEach((evt) => {
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.dropzone.classList.add("is-drag");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.dropzone.classList.remove("is-drag");
    });
  });
  els.dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    els.file.files = dt.files;
    previewFile(file);
  });

  els.passwords.addEventListener("input", previewPaste);

  els.clearFinished.addEventListener("click", async () => {
    const res = await fetch("/api/tasks/clear-finished", { method: "POST" });
    const data = await res.json();
    toast(data.success ? `Cleared ${data.removed}` : "Clear failed", data.success ? "success" : "error");
    refresh();
  });

  els.taskList.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    if (btn.dataset.cancel) cancelTask(btn.dataset.cancel);
    if (btn.dataset.delete) deleteTask(btn.dataset.delete);
    if (btn.dataset.export) exportTask(btn.dataset.export);
    if (btn.dataset.copy) {
      navigator.clipboard.writeText(btn.dataset.copy).then(() => toast("Copied hit", "success"));
    }
  });

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });

  setSource("upload");
  checkHealth();
  refresh();
  state.pollTimer = setInterval(refresh, cfg.pollMs || 1500);
  setInterval(checkHealth, 15000);
})();
