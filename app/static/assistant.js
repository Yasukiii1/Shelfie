const X = window.Shelfie;
const { S, api, icon, esc, catColor, isPhone, store, toast } = X;
const $ = (s, el = document) => el.querySelector(s);

const BASE_W = 392;
const A = {
  items: [], nodes: [], busy: false, model: "offline", modelName: "", thinking: "low", command: "",
  ws: null, retry: 0, open: false, docs: new Map(), ctxDismissed: null, statusT: null,
  chat: null, stick: true, thinkOpen: new Map(), attach: [], width: store.get("assistWidth", BASE_W),
};

// ---------- doc lookup (for citation chips and tool labels) ----------
async function loadDocIndex() {
  try { (await api("/api/docs?sort=title")).forEach((d) => A.docs.set(d.id, d)); } catch {}
}
const docTitle = (id) => A.docs.get(+id)?.title;

// ---------- markdown (escape first, then a small safe subset) ----------
function md(src) {
  const blocks = [];
  let s = esc(src).replace(/```[\w-]*\n?([\s\S]*?)(```|$)/g, (_, code) => { blocks.push(`<pre>${code}</pre>`); return `\u0000${blocks.length - 1}\u0000`; });
  const cite = (_, _t, id, rest) => chip(id) + (rest.trim() ? ` <span class="pg">(${rest.replace(/^,\s*/, "")})</span>` : "");
  const inline = (t) => t
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/(?:&quot;|“)([^“”]{1,140}?)(?:&quot;|”)\s*\(#(\d+)([^)]{0,30})\)/g, cite)
    .replace(/<b>(?:&quot;)?([^<]{1,140}?)(?:&quot;)?<\/b>\s*\(#(\d+)([^)]{0,30})\)/g, cite)
    .replace(/(^|[\s(])#(\d+)\b/g, (m, pre, id) => (A.docs.has(+id) ? pre + chip(id) : m));
  const out = [];
  let list = null, table = null;
  const flushTable = () => {
    if (!table) return;
    const rows = table.filter((r) => !r.every((c) => /^:?-{2,}:?$/.test(c) || !c));
    out.push(`<div class="md-table"><table>${rows.map((r, i) => `<tr>${r.map((c) => i === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</table></div>\n\n`);
    table = null;
  };
  for (const line of s.split("\n")) {
    if (/^\s*\|.*\|\s*$/.test(line)) { (table ??= []).push(line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim())); continue; }
    flushTable();
    const li = line.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)/);
    if (li) {
      const type = li[1] ? "ol" : "ul";
      if (!list || list.type !== type) { if (list) out.push(`</${list.type}>`); list = { type }; out.push(`<${type}>`); }
      out.push(`<li>${inline(li[2])}</li>`); continue;
    }
    if (list) { out.push(`</${list.type}>`); list = null; }
    const h = line.match(/^#{1,4}\s+(.*)/);
    if (h) { out.push(`\n\n<h4>${inline(h[1])}</h4>\n\n`); continue; }
    if (/^\u0000\d+\u0000$/.test(line.trim())) { out.push(`\n\n${line.trim()}\n\n`); continue; }
    if (!line.trim()) { out.push("\n\n"); continue; }
    out.push(inline(line) + "<br>");
  }
  flushTable();
  if (list) out.push(`</${list.type}>`);
  return out.join("").split(/\n\n+/).map((p) => p.replace(/(<br>)+$/, "").trim()).filter(Boolean)
    .map((p) => (/^<(ul|ol|h4|pre|div)|^\u0000/.test(p) ? p : `<p>${p}</p>`)).join("")
    .replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[+i]);
}
function chip(id) {
  const d = A.docs.get(+id);
  const t = d ? d.title : `#${id}`;
  return `<span class="docref" data-doc="${+id}" style="--c:${d ? catColor(d.category) : "var(--accent)"}" title="Open">${esc(t.length > 42 ? t.slice(0, 40) + "…" : t)}</span>`;
}

// ---------- item rendering (one DOM node per item, updated in place) ----------
const TOOL = {
  shelfie_list: (a) => ({ i: "library", t: a.drawer ? `Looked in <b>${esc(a.drawer)}</b>` : a.tag ? `Looked for <b>#${esc(a.tag)}</b>` : "Looked through the library" }),
  shelfie_search: (a) => ({ i: "search", t: `Searched <b>“${esc(a.query || "")}”</b>` }),
  shelfie_read: (a) => ({ i: "library", t: `Read <b>${esc(docTitle(a.id) || "#" + a.id)}</b> · p. ${a.from_page || 1}–${a.to_page || (a.from_page || 1) + 9}`, doc: a.id, page: a.from_page || 1 }),
  shelfie_create_pdf: (a, it) => ({ i: "plus", t: `Created <b>${esc(a.title || "a PDF")}</b> in ${esc(a.drawer || "Inbox")}`, created: true, doc: it.details?.id }),
  shelfie_create_drawer: (a) => ({ i: "drawer", t: `Made the drawer <b>${esc(a.name || "")}</b>` }),
  shelfie_organize: (a) => ({ i: "tag", t: `Filed <b>${esc(docTitle(a.id) || "#" + a.id)}</b>${a.drawer ? ` → ${esc(a.drawer)}` : ""}${a.add_tags?.length ? ` · ${a.add_tags.map((t) => "#" + esc(t)).join(" ")}` : ""}${a.star ? " · starred" : ""}`, doc: a.id }),
};

function itemHTML(it, i) {
  if (it.kind === "user") return `<div class="msg-user">${esc(it.text)}</div>`;
  if (it.kind === "error") return `<div class="msg-err">${esc(it.text)}</div>`;
  if (it.kind === "tool") {
    const f = (TOOL[it.name] || (() => ({ i: "info", t: esc(it.name) })))(it.args || {}, it);
    const cls = ["tool", it.status, f.created && it.status === "done" ? "created" : "", f.doc && it.status === "done" ? "clickable" : ""].join(" ");
    return `<div class="${cls}" ${f.doc ? `data-doc="${f.doc}" data-page="${f.page || 1}"` : ""} title="${esc(it.summary || "")}">
      ${it.status === "running" ? '<span class="spin"></span>' : icon(it.status === "error" ? "x" : f.i)}<span class="tl">${f.t}</span></div>`;
  }
  if (it.kind === "convert") {
    const pct = it.status === "done" ? 100 : Math.min(95, ((it.page || 1) - 1) / it.pages * 100 + (it.tokens || 0) / 60 / it.pages);
    return `<div class="conv ${it.status}" ${it.doc ? `data-doc="${it.doc}"` : ""}>
      <div class="conv-thumbs">${(it.thumbs || []).slice(0, 4).map((t) => `<img src="${t}" alt="">`).join("")}</div>
      <div class="conv-body">
        <div class="conv-t">${it.status === "done" ? `${icon("plus")} <b>${esc(it.docTitle || "New PDF")}</b>` : esc(it.title || "Photos → PDF")}</div>
        <div class="conv-s">${esc(it.stage || "")}${it.status === "running" && it.tokens ? ` · ${it.tokens.toLocaleString()} tokens` : ""}${it.status === "done" ? ` · filed in ${esc(it.drawer)}` : ""}</div>
        ${it.warning ? `<div class="conv-warn">⚠ ${esc(it.warning)}</div>` : ""}
        ${it.status === "running" ? `<div class="conv-bar"><i style="width:${pct.toFixed(0)}%"></i></div>` : ""}
      </div></div>`;
  }
  // assistant message: thinking + body, filled by updateAssistant()
  return `<div class="msg-ai"><details class="think" hidden><summary>${icon("brain")}<span class="th-l"></span></summary><div class="tb"></div></details><div class="body"></div></div>`;
}

function updateAssistant(node, it, i) {
  const live = i === A.items.length - 1 && A.busy;
  const det = node.querySelector(".think"), tb = node.querySelector(".tb"), body = node.querySelector(".body");
  const th = (it.thinking || "").trim();
  det.hidden = !th;
  if (th) {
    // user's choice wins; otherwise open while thinking, close once the answer starts
    const user = A.thinkOpen.get(i);
    const want = user ?? (live && !it.text);
    if (det.open !== want) det.open = want;
    det.querySelector(".th-l").textContent = live && !it.text ? "Thinking…" : "Thought it through";
    if (tb.textContent !== th) {
      const follow = tb.scrollHeight - tb.scrollTop - tb.clientHeight < 24;
      tb.textContent = th;
      if (follow) tb.scrollTop = tb.scrollHeight;
    }
  }
  body.innerHTML = (it.text ? md(it.text) : "") + (live && (it.text || !th) ? '<span class="cursor"></span>' : "");
}

function buildNode(it, i) {
  const wrap = document.createElement("div");
  wrap.innerHTML = itemHTML(it, i);
  const node = wrap.firstElementChild;
  node.dataset.i = i;
  if (it.kind === "assistant") {
    // remember the user's own open/close choice (summary click happens before the toggle)
    node.querySelector(".think summary").addEventListener("click", (e) => { A.thinkOpen.set(i, !e.currentTarget.parentElement.open); });
    updateAssistant(node, it, i);
  }
  return node;
}

function setNode(i) {
  const it = A.items[i], old = A.nodes[i];
  if (!it) return;
  if (old && it.kind === "assistant" && old.classList.contains("msg-ai")) { updateAssistant(old, it, i); return; }
  const node = buildNode(it, i);
  if (old) old.replaceWith(node); else $("#as-log").append(node);
  A.nodes[i] = node;
}

function renderAll() {
  const log = $("#as-log");
  A.nodes = [];
  if (!A.items.length) {
    log.innerHTML = `<div class="as-welcome"><h3>Ask your <em>library</em>.</h3>
      <p>${esc(A.modelName || "Your local model")} reads the PDFs in Shelfie, finds things inside them, and writes new documents for you. It never sees anything outside this library.</p>
      <div class="as-sugg">
        <button>What’s in my Inbox, and where should each file go?</button>
        <button>Summarise the newest document in five bullet points.</button>
        <button>Find everything that mentions an invoice or payment.</button>
        <button data-photo>${icon("image")} Turn photos of a worksheet into a real PDF</button>
      </div></div>`;
    return;
  }
  log.replaceChildren();
  A.items.forEach((_, i) => setNode(i));
  log.scrollTop = log.scrollHeight;
}
function stickToBottom() { if (A.stick) { const log = $("#as-log"); log.scrollTop = log.scrollHeight; } }
$("#as-log").addEventListener("scroll", () => { const l = $("#as-log"); A.stick = l.scrollHeight - l.scrollTop - l.clientHeight < 40; }, { passive: true });

let pend = new Set(), raf = 0, rafT = 0;
function queue(i) {
  pend.add(i);
  if (!raf) { raf = requestAnimationFrame(flush); rafT = setTimeout(flush, 80); } // timer covers hidden/background windows
}
function flush() {
  if (!raf) return;
  cancelAnimationFrame(raf); clearTimeout(rafT); raf = 0;
  if ($(".as-welcome") && A.items.length) { $("#as-log").replaceChildren(); A.nodes = []; for (let i = 0; i < A.items.length; i++) pend.add(i); }
  [...pend].sort((a, b) => a - b).forEach(setNode); pend.clear();
  stickToBottom();
}

function renderState() {
  $("#as-dot").className = "dot " + A.model;
  $("#as-model").textContent = A.model === "online" ? `${A.modelName} · local` : A.model === "loading" ? "model loading…" : "model offline";
  $("#as-think").innerHTML = `${icon("brain")}${A.thinking === "off" ? "No think" : A.thinking}`;
  const send = $("#as-send");
  send.classList.toggle("stop", A.busy && !A.attach.length);
  send.innerHTML = icon(A.busy && !A.attach.length ? "stop" : "send");
  send.title = A.busy ? "Stop" : "Send (Enter)";
  const ct = $("#as-chat-title");
  ct.hidden = !A.chat; ct.textContent = A.chat?.title || "";
  const off = $("#as-offline");
  if (A.model === "online") { off.hidden = true; return; }
  off.hidden = false;
  off.innerHTML = A.model === "loading"
    ? `<b>Loading your model…</b><br>This takes about 15–30 seconds. The panel switches on by itself.`
    : `<b>Your model isn’t running.</b><br>Start llama-server to chat with your library.${S.local ? `<code>${esc(A.command || "")}</code><button class="btn primary" id="as-start">${icon("spark")} Start model</button>` : "<br>Start it on your computer."}`;
  $("#as-start")?.addEventListener("click", async () => { await api("/api/agent/model/start", { method: "POST" }); A.model = "loading"; renderState(); pollStatus(); });
}

// ---------- history ----------
async function showHistory(on = $("#as-history").hidden) {
  const box = $("#as-history");
  $("#as-hist").classList.toggle("on", on);
  if (!on) { box.hidden = true; return; }
  const { chats } = await api("/api/agent/chats");
  const day = (t) => {
    const d = new Date(t * 1000), now = new Date();
    const diff = Math.floor((new Date(now.toDateString()) - new Date(d.toDateString())) / 864e5);
    return diff === 0 ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : diff === 1 ? "Yesterday" : diff < 7 ? d.toLocaleDateString([], { weekday: "long" }) : d.toLocaleDateString([], { day: "numeric", month: "short" });
  };
  box.innerHTML = `<div class="h-head"><span>Chats</span><button class="icon-btn sm" data-h-close>${icon("x")}</button></div>
    <button class="h-new" data-h-new>${icon("plus")} New chat</button>
    ${chats.length ? chats.map((c) => `<div class="h-item ${A.chat?.id === c.id ? "on" : ""}" data-chat="${esc(c.id)}">
      <div class="h-t">${esc(c.title)}</div><div class="h-m">${day(c.updated)} · ${c.messages} message${c.messages === 1 ? "" : "s"}</div>
      <button class="h-del" data-del="${esc(c.id)}" title="Delete this chat">${icon("trash")}</button></div>`).join("")
      : `<div class="h-empty">No saved chats yet. Chats are saved automatically.</div>`}`;
  box.hidden = false;
}
$("#as-history").addEventListener("click", async (e) => {
  if (e.target.closest("[data-h-close]")) return showHistory(false);
  if (e.target.closest("[data-h-new]")) { send({ type: "new" }); return showHistory(false); }
  const del = e.target.closest("[data-del]");
  if (del) {
    e.stopPropagation();
    const row = del.closest(".h-item");
    if (!row.classList.contains("confirm")) { row.classList.add("confirm"); del.innerHTML = "Delete?"; setTimeout(() => { row.classList.remove("confirm"); del.innerHTML = icon("trash"); }, 2500); return; }
    await api(`/api/agent/chats/${encodeURIComponent(del.dataset.del)}`, { method: "DELETE" });
    return showHistory(true);
  }
  const row = e.target.closest("[data-chat]");
  if (row) { send({ type: "open_chat", id: row.dataset.chat }); showHistory(false); }
});

// ---------- context (what the user is looking at) ----------
function currentContext() {
  const d = X.viewerDoc || (S.selected ? S.docs.find((x) => x.id === S.selected) : null);
  if (!d || A.ctxDismissed === d.id) return null;
  return d;
}
let ctxKey = "";
function renderContext() {
  const d = currentContext(); const el = $("#as-context");
  const key = d ? d.id + "" : "";
  if (key === ctxKey) return; ctxKey = key;
  if (!d) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<span>About</span>${chip(d.id)}<button type="button" id="as-ctx-x" title="Don't include">✕</button>`;
  $("#as-ctx-x").onclick = () => { A.ctxDismissed = d.id; renderContext(); };
}
setInterval(() => { if (A.open) renderContext(); }, 700);

// ---------- photo attachments (→ real PDF) ----------
function renderAttach() {
  const el = $("#as-attach");
  el.hidden = !A.attach.length;
  el.innerHTML = A.attach.map((f, i) => `<div class="att"><img src="${f.url}" alt=""><button type="button" data-rm="${i}" title="Remove">×</button></div>`).join("") +
    (A.attach.length ? `<div class="att-note">${A.attach.length} photo${A.attach.length > 1 ? "s" : ""} → one PDF · into <select id="as-drawer">${S.cats.map((c) => `<option ${c.name === (S.view.kind === "drawer" ? S.view.value : "Inbox") ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
      <label class="lens" title="Cleans and sharpens the photo, and reads the text with OCR first so blurry words come out right"><input type="checkbox" id="as-lens" ${store.get("lens", true) ? "checked" : ""}> Text Lens</label></div>` : "");
  $("#as-lens")?.addEventListener("change", (e) => store.set("lens", e.target.checked));
  $("#as-input").placeholder = A.attach.length ? "Press Enter to rebuild these pages as a PDF" : (isPhone() ? "Ask about your PDFs, or paste a photo…" : "Ask about your PDFs… (paste a photo here)");
  renderState();
}
function addPhotos(files) {
  for (const f of files) if (f.type.startsWith("image/") || /\.(heic|heif|jpe?g|png|webp)$/i.test(f.name)) A.attach.push({ file: f, url: URL.createObjectURL(f) });
  renderAttach();
}
$("#as-attach").addEventListener("click", (e) => { const b = e.target.closest("[data-rm]"); if (!b) return; URL.revokeObjectURL(A.attach[+b.dataset.rm].url); A.attach.splice(+b.dataset.rm, 1); renderAttach(); });
async function sendPhotos(drawer) {
  const files = A.attach.map((a) => a.file);
  const note = $("#as-input").value.trim();
  $("#as-input").value = ""; autosize();
  const fd = new FormData(); files.forEach((f) => fd.append("files", f, f.name)); fd.append("category", drawer || $("#as-drawer")?.value || "Inbox"); fd.append("lens", store.get("lens", true) ? "1" : "0"); if (note) fd.append("note", note);
  A.attach.forEach((a) => URL.revokeObjectURL(a.url)); A.attach = []; renderAttach();
  const r = await fetch("/api/convert", { method: "POST", body: fd });
  if (!r.ok) { let m = "Conversion failed"; try { m = (await r.json()).detail; } catch {} toast(esc(m), 5000); }
}
X.convertPhotos = async (files, drawer) => { A.attach = []; addPhotos(files); toggle(true); await sendPhotos(drawer); };
$("#as-clip").onclick = () => $("#as-file").click();
$("#as-file").addEventListener("change", (e) => { addPhotos([...e.target.files]); e.target.value = ""; $("#as-input").focus(); });
$("#assistant").addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); e.stopPropagation(); $("#assistant").classList.add("drop"); } });
$("#assistant").addEventListener("dragleave", (e) => { if (!$("#assistant").contains(e.relatedTarget)) $("#assistant").classList.remove("drop"); });
$("#assistant").addEventListener("drop", (e) => {
  $("#assistant").classList.remove("drop");
  const imgs = [...e.dataTransfer.files].filter((f) => f.type.startsWith("image/"));
  if (!imgs.length) return;
  e.preventDefault(); e.stopPropagation(); addPhotos(imgs);
}, true);

// ---------- socket ----------
function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/agent/ws`);
  A.ws = ws;
  ws.onopen = () => { A.retry = 0; };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.op === "reset") { A.items = m.items; A.chat = m.chat ?? null; A.thinkOpen.clear(); A.stick = true; renderAll(); renderState(); return; }
    if (m.op === "chat") { A.chat = m.chat; renderState(); return; }
    if (m.op === "chats") { if (!$("#as-history").hidden) showHistory(true); return; }
    if (m.op === "push") { A.items.push(m.item); queue(A.items.length - 1); if (m.item.kind === "tool") loadDocIndex(); if (A.items.length > 1) queue(A.items.length - 2); }
    else if (m.op === "append") { const it = A.items[m.i]; if (it) { it[m.field] = (it[m.field] || "") + m.delta; queue(m.i); } }
    else if (m.op === "set") {
      A.items[m.i] = m.item; queue(m.i);
      const done = m.item.status === "done";
      if (done && (m.item.kind === "convert" || /create|organize/.test(m.item.name || ""))) { loadDocIndex(); X.refresh(); }
    }
    else if (m.op === "state") {
      const was = A.busy;
      A.busy = m.busy; A.model = m.model; A.modelName = m.model_name; A.thinking = m.thinking;
      if ("chat" in m) A.chat = m.chat;
      renderState();
      if (was !== A.busy && A.items.length) queue(A.items.length - 1); // drop the cursor
    }
  };
  ws.onclose = () => { A.ws = null; setTimeout(connect, Math.min(8000, 500 * 2 ** A.retry++)); };
}
const send = (o) => A.ws?.readyState === 1 && A.ws.send(JSON.stringify(o));

async function pollStatus() {
  clearTimeout(A.statusT);
  try {
    const st = await api("/api/agent/status");
    Object.assign(A, { model: st.model, modelName: st.model_name, command: st.command, busy: st.busy, thinking: st.thinking, chat: st.chat });
    renderState();
  } catch {}
  A.statusT = setTimeout(pollStatus, A.open ? (A.model === "online" ? 15000 : 3000) : 30000);
}

// ---------- actions ----------
function submit(text) {
  if (A.attach.length) return sendPhotos();
  text = (text ?? $("#as-input").value).trim();
  if (!text || A.busy) return;
  const d = currentContext();
  const context = d ? `[Shelfie context: the user is looking at document #${d.id} "${d.title}" (drawer ${d.category}, ${d.pages} pages). "this" probably refers to it.]` : "";
  A.stick = true;
  send({ type: "prompt", text, context });
  $("#as-input").value = ""; autosize();
}
function autosize() { const t = $("#as-input"); t.style.height = "auto"; t.style.height = Math.min(160, t.scrollHeight) + "px"; }

// ---------- open / close: width snaps once, the panel itself slides on the GPU ----------
function applyWidth(w) {
  A.width = Math.round(Math.max(BASE_W * 0.5, Math.min(BASE_W * 1.5, w)));
  document.documentElement.style.setProperty("--assist", A.width + "px");
}
applyWidth(A.width);
let closeT = 0;
function toggle(force) {
  const el = $("#assistant");
  A.open = force ?? !A.open;
  clearTimeout(closeT);
  $("#btn-ask").classList.toggle("on", A.open);
  if (!isPhone()) store.set("assistant", A.open);
  if (A.open) {
    el.classList.add("open");
    document.body.classList.toggle("as-open", !isPhone());
    void el.offsetWidth; // commit the closed state so the slide-in transition runs
    el.classList.add("shown");
    pollStatus(); ctxKey = "-"; renderContext();
    setTimeout(() => !isPhone() && $("#as-input").focus(), 230);
  } else {
    el.classList.remove("shown");
    closeT = setTimeout(() => { el.classList.remove("open"); document.body.classList.remove("as-open"); window.dispatchEvent(new Event("resize")); }, 200);
  }
  if (A.open) window.dispatchEvent(new Event("resize"));
}
X.toggleAssistant = toggle;

// ---------- drag the left edge to resize (½× … 1.5×) ----------
(() => {
  const h = $("#as-resize"); let startX = 0, startW = 0;
  h.addEventListener("pointerdown", (e) => {
    if (isPhone()) return;
    startX = e.clientX; startW = A.width; h.setPointerCapture(e.pointerId);
    document.body.classList.add("resizing");
  });
  h.addEventListener("pointermove", (e) => {
    if (!h.hasPointerCapture(e.pointerId)) return;
    applyWidth(startW + (startX - e.clientX));
  });
  const end = (e) => {
    if (!h.hasPointerCapture(e.pointerId)) return;
    h.releasePointerCapture(e.pointerId); document.body.classList.remove("resizing");
    store.set("assistWidth", A.width); window.dispatchEvent(new Event("resize"));
  };
  h.addEventListener("pointerup", end); h.addEventListener("pointercancel", end);
  h.addEventListener("dblclick", () => { applyWidth(BASE_W); store.set("assistWidth", BASE_W); window.dispatchEvent(new Event("resize")); });
})();

$("#btn-ask").onclick = () => toggle();
$("#as-close").innerHTML = icon(isPhone() ? "back" : "x");
$("#as-close").onclick = () => toggle(false);
$("#as-new").innerHTML = icon("edit");
$("#as-hist").innerHTML = icon("clock");
$("#as-clip").innerHTML = icon("image");
$("#as-hist").onclick = () => showHistory();
$("#as-new").onclick = () => { send({ type: "new" }); A.ctxDismissed = null; showHistory(false); };
$("#as-think").onclick = () => {
  const L = ["off", "low", "medium", "high"];
  send({ type: "thinking", level: L[(L.indexOf(A.thinking) + 1) % L.length] });
};
$("#as-form").addEventListener("submit", (e) => { e.preventDefault(); A.busy && !A.attach.length ? send({ type: "abort" }) : submit(); });
$("#as-input").addEventListener("input", autosize);
$("#as-input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } });
// ---------- paste photos into the chat box only (Ctrl+V / ⌘V / long-press → Paste) ----------
$("#as-input").addEventListener("paste", async (e) => {
  e.stopPropagation(); // the app-wide paste (Import sheet) must not see chat-box pastes
  const imgs = X.clip.fromEvent(e.clipboardData).filter((f) => f.type.startsWith("image/"));
  if (imgs.length) { e.preventDefault(); addPhotos(imgs); return; }
  if (X.clip.kind(e.clipboardData) === "text") return; // ordinary text paste
  e.preventDefault(); // browser "Copy Image" (html) or Files app copy (file list): fetch the real image
  const native = (await X.clip.native()).filter((f) => f.type.startsWith("image/"));
  if (native.length) addPhotos(native);
  else if (window.pywebview?.api) X.toast("No image found on the clipboard. Copy the image itself, or use the image button.", 3500);
});
$("#as-log").addEventListener("click", (e) => {
  if (e.target.closest("[data-photo]")) return $("#as-file").click();
  const sug = e.target.closest(".as-sugg button"); if (sug) return submit(sug.textContent);
  if (e.target.closest("summary")) return;
  const ref = e.target.closest("[data-doc]");
  if (ref && ref.dataset.doc) X.openViewer(+ref.dataset.doc, +(ref.dataset.page || 1));
});
$("#as-context").addEventListener("click", (e) => { const r = e.target.closest(".docref"); if (r) X.openViewer(+r.dataset.doc); });

// ---------- boot ----------
loadDocIndex().then(() => { if (!A.items.length) renderAll(); });
renderAll();
renderState();
connect();
pollStatus();
if (!isPhone() && store.get("assistant", false)) toggle(true);
