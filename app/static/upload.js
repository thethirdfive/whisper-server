/* 后台分块断点续传上传管理器
 *
 * - 全局单例 window.uploadManager，脚本在 #page 之外加载，跨 htmx-boost 导航存活。
 * - 一次处理一个会议（对上行带宽友好），会议内文件顺序分块上传。
 * - 每块 5MB：远小于 nginx client_max_body_size / 超时，避免 WAN 上整文件 POST 被掐断。
 * - 失败自动重试，偏移与服务端不符（409）时自动续传。
 * - 未完成会议存 localStorage；整页刷新后托盘提示“重选文件续传”（浏览器无法持久化 File）。
 */
(function () {
  if (window.uploadManager) return;

  const CHUNK = 5 * 1024 * 1024;
  const MAX_RETRY = 5;
  const LS_KEY = "ws_uploads";

  const state = { jobs: [], activeId: null };

  // ---------- 工具 ----------
  const uid = () => Math.random().toString(36).slice(2, 9);
  function fmtBytes(n) {
    const u = ["B", "KB", "MB", "GB"]; let i = 0;
    while (n >= 1024 && i < 3) { n /= 1024; i++; }
    return n.toFixed(n < 10 && i > 0 ? 1 : 0) + u[i];
  }
  function totals(j) {
    const total = j.files.reduce((s, f) => s + f.size, 0);
    const up = j.files.reduce((s, f) => s + f.uploaded, 0);
    return { total, up, pct: total ? Math.floor((up / total) * 100) : 0 };
  }
  const api = (method, url, opts = {}) =>
    fetch(url, { method, credentials: "same-origin", ...opts });

  // ---------- 持久化（仅元数据，不能存 File） ----------
  function persist() {
    const slim = state.jobs
      .filter((j) => ["uploading", "interrupted", "queued"].includes(j.status) && j.meetingId)
      .map((j) => ({
        id: j.id, meetingId: j.meetingId, title: j.title,
        files: j.files.map((f) => ({ fid: f.fid, name: f.name, size: f.size, uploaded: f.uploaded })),
      }));
    try { localStorage.setItem(LS_KEY, JSON.stringify(slim)); } catch (e) { /* ignore */ }
  }
  function restore() {
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch (e) { /* ignore */ }
    for (const j of saved) {
      if (!j.meetingId) continue;
      state.jobs.push({
        id: j.id || uid(), meetingId: j.meetingId, title: j.title || "未命名", meta: null,
        files: j.files.map((f) => ({ ...f, file: null, speed: 0 })),
        status: "interrupted", error: "上传中断",
      });
    }
    render();
  }

  // ---------- 核心 ----------
  async function processQueue() {
    if (state.activeId) return;
    const job = state.jobs.find((j) => j.status === "queued" && j.files.every((f) => f.file));
    if (!job) return;
    state.activeId = job.id;
    job.status = "uploading"; job.error = null; render(); persist();
    try {
      if (!job.meetingId) {
        const r = await api("POST", "/meetings/draft", {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...job.meta, files: job.files.map((f) => ({ name: f.name, size: f.size })) }),
        });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "建会议失败");
        const d = await r.json();
        job.meetingId = d.meeting_id;
        d.files.forEach((sf, i) => { job.files[i].fid = sf.id; job.files[i].uploaded = sf.uploaded_bytes; });
        persist();
      }
      for (const f of job.files) {
        if (f.uploaded < f.size) await uploadFile(job, f);
      }
      const rf = await api("POST", `/meetings/${job.meetingId}/finalize`);
      if (!rf.ok) throw new Error((await rf.json().catch(() => ({}))).detail || "入队失败");
      job.status = "done"; render(); persist();
    } catch (e) {
      job.status = job.meetingId ? "interrupted" : "failed";
      job.error = e.message || String(e);
      render(); persist();
    } finally {
      state.activeId = null;
      setTimeout(processQueue, 200);
    }
  }

  async function uploadFile(job, f) {
    f.t0 = Date.now(); f.b0 = f.uploaded;
    while (f.uploaded < f.size) {
      const buf = await f.file.slice(f.uploaded, f.uploaded + CHUNK).arrayBuffer();
      let tries = 0;
      for (;;) {
        try {
          const r = await api("PUT",
            `/meetings/${job.meetingId}/files/${f.fid}/chunk?offset=${f.uploaded}`,
            { headers: { "Content-Type": "application/octet-stream" }, body: buf });
          if (r.status === 409) { f.uploaded = (await r.json()).uploaded_bytes; break; }
          if (!r.ok) throw new Error("HTTP " + r.status);
          f.uploaded = (await r.json()).uploaded_bytes; break;
        } catch (err) {
          if (++tries > MAX_RETRY) throw new Error(f.name + "：" + (err.message || err));
          await new Promise((res) => setTimeout(res, Math.min(1000 * tries, 5000)));
          try { const rs = await api("GET", `/meetings/${job.meetingId}/files/${f.fid}`);
            if (rs.ok) f.uploaded = (await rs.json()).uploaded_bytes; } catch (_) { /* ignore */ }
        }
      }
      const dt = (Date.now() - f.t0) / 1000;
      if (dt > 0.5) { f.speed = (f.uploaded - f.b0) / dt; f.t0 = Date.now(); f.b0 = f.uploaded; }
      render(); persist();
    }
  }

  // ---------- 对外 ----------
  function addJob(meta, fileList) {
    const files = Array.from(fileList).map((file) =>
      ({ fid: null, name: file.name, size: file.size, uploaded: 0, file, speed: 0 }));
    if (!files.length) return;
    state.jobs.push({ id: uid(), meetingId: null, title: meta.title || "未命名", meta, files, status: "queued", error: null });
    render(); persist(); processQueue();
  }
  function resumeJob(jobId, fileList) {
    const job = state.jobs.find((j) => j.id === jobId);
    if (!job) return;
    const byName = {}; Array.from(fileList).forEach((f) => { byName[f.name] = f; });
    let ok = true;
    job.files.forEach((f) => {
      const p = byName[f.name];
      if (p && p.size === f.size) f.file = p; else ok = false;
    });
    if (!ok) { alert("请选择与原来同名、同大小的文件以续传"); job.files.forEach((f) => { f.file = null; }); return; }
    job.status = "queued"; render(); persist(); processQueue();
  }
  function removeJob(jobId) {
    const job = state.jobs.find((j) => j.id === jobId);
    if (!job) return;
    if (job.meetingId && ["interrupted", "failed"].includes(job.status)) {
      api("POST", `/meetings/${job.meetingId}/cancel`).catch(() => {});
    }
    state.jobs = state.jobs.filter((j) => j.id !== jobId);
    render(); persist();
  }

  // ---------- 托盘 UI ----------
  function el(tag, attrs = {}, html) {
    const e = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function render() {
    let tray = document.getElementById("upload-tray");
    const active = state.jobs.filter((j) => j.status !== "done" || true);
    if (!state.jobs.length) { if (tray) tray.remove(); return; }
    if (!tray) {
      tray = el("div", { id: "upload-tray", style:
        "position:fixed;right:16px;bottom:16px;width:340px;max-height:60vh;overflow:auto;z-index:9999;" +
        "background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);font-size:13px;" });
      document.body.appendChild(tray);
    }
    const STATUS = { queued: "排队中", uploading: "上传中", done: "已排队转录 ✓", interrupted: "已中断", failed: "失败" };
    const COLOR = { queued: "#64748b", uploading: "#2563eb", done: "#16a34a", interrupted: "#d97706", failed: "#dc2626" };
    tray.innerHTML = "";
    tray.appendChild(el("div", { style:
      "padding:8px 12px;border-bottom:1px solid #f1f5f9;font-weight:600;display:flex;justify-content:space-between;align-items:center;" },
      `上传 (${state.jobs.length}) <span id="ul-min" style="cursor:pointer;color:#94a3b8;font-weight:400">—</span>`));
    const body = el("div", { id: "ul-body", style: "padding:4px 0;" });
    for (const j of state.jobs) {
      const { up, total, pct } = totals(j);
      const row = el("div", { style: "padding:8px 12px;border-bottom:1px solid #f8fafc;" });
      const speed = (j.status === "uploading" && j.files.some((f) => f.speed))
        ? "  " + fmtBytes(j.files.reduce((s, f) => s + (f.speed || 0), 0)) + "/s" : "";
      row.appendChild(el("div", { style: "display:flex;justify-content:space-between;gap:8px;" },
        `<span style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px">${escapeHtml(j.title)}</span>
         <span style="color:${COLOR[j.status]};white-space:nowrap">${STATUS[j.status]}</span>`));
      if (["uploading", "queued", "interrupted"].includes(j.status)) {
        const barOuter = el("div", { style: "height:6px;background:#f1f5f9;border-radius:3px;margin:5px 0;overflow:hidden;" });
        barOuter.appendChild(el("div", { style: `height:6px;width:${pct}%;background:${COLOR[j.status]};transition:width .2s;` }));
        row.appendChild(barOuter);
        row.appendChild(el("div", { style: "color:#94a3b8;font-size:11px;" },
          `${fmtBytes(up)} / ${fmtBytes(total)} · ${pct}%${speed}`));
      }
      if (j.error && j.status !== "done") row.appendChild(el("div", { style: "color:#dc2626;font-size:11px;margin-top:2px;" }, escapeHtml(j.error)));
      // 操作
      const actions = el("div", { style: "margin-top:6px;display:flex;gap:10px;" });
      if (j.status === "interrupted") {
        const pick = el("input", { type: "file", multiple: "", style: "display:none" });
        pick.addEventListener("change", (e) => resumeJob(j.id, e.target.files));
        const btn = el("a", { href: "#", style: "color:#2563eb;font-size:12px;" }, "重选文件续传");
        btn.addEventListener("click", (e) => { e.preventDefault(); pick.click(); });
        actions.appendChild(btn); actions.appendChild(pick);
      }
      if (j.status === "done") {
        actions.appendChild(linkBtn("查看", "#", (e) => { e.preventDefault(); navigate(`/meetings/${j.meetingId}`); }));
      }
      if (["done", "failed", "interrupted"].includes(j.status)) {
        actions.appendChild(linkBtn("移除", "#", (e) => { e.preventDefault(); removeJob(j.id); }, "#94a3b8"));
      }
      if (actions.children.length) row.appendChild(actions);
      body.appendChild(row);
    }
    tray.appendChild(body);
    const min = document.getElementById("ul-min");
    if (min) min.addEventListener("click", () => {
      const b = document.getElementById("ul-body");
      if (b) b.style.display = b.style.display === "none" ? "" : "none";
    });
  }
  function linkBtn(text, href, onclick, color) {
    const a = el("a", { href, style: `color:${color || "#2563eb"};font-size:12px;` }, text);
    a.addEventListener("click", onclick);
    return a;
  }
  function navigate(url) {
    // 用 htmx boost 跳转以不中断上传；不可用则普通跳转
    if (window.htmx) window.htmx.ajax("GET", url, { target: "#page", select: "#page", swap: "outerHTML" });
    else window.location.href = url;
  }
  function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

  window.uploadManager = { addJob, resumeJob, removeJob };
  if (document.readyState !== "loading") restore();
  else document.addEventListener("DOMContentLoaded", restore);

  // 离开页面时若有上传未完成，提示
  window.addEventListener("beforeunload", (e) => {
    if (state.jobs.some((j) => j.status === "uploading")) { e.preventDefault(); e.returnValue = ""; }
  });
})();
