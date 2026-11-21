const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isPhone = () => matchMedia("(max-width: 760px)").matches;
const store = {
  get(k, d) { try { const v = localStorage.getItem("shelfie:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("shelfie:" + k, JSON.stringify(v)); } catch {} },
};

// ---------- icons ----------
const P = {
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  star: '<path d="m12 3.5 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/>',
  grid: '<rect x="4" y="4" width="6.5" height="7.5" rx="1"/><rect x="13.5" y="4" width="6.5" height="7.5" rx="1"/><rect x="4" y="14.5" width="6.5" height="5.5" rx="1"/><rect x="13.5" y="14.5" width="6.5" height="5.5" rx="1"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4.5 6h.01M4.5 12h.01M4.5 18h.01" stroke-width="2.4"/>',
  clock: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4.5l3 1.8"/>',
  library: '<path d="M5 4.5h4v15H5zM10.5 4.5h4v15h-4z"/><path d="m16.2 5.4 3.6-1 3.5 13.9-3.6 1z" transform="translate(-1.6 .4)"/>',
  drawer: '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M3.5 12h17M10 8h4M10 16h4"/>',
  inbox: '<path d="M4 13.5 6.5 5h11l2.5 8.5V19H4z"/><path d="M4 13.5h4.5l1 2h5l1-2H20"/>',
  tag: '<path d="M3.5 12.2V4.5h7.7l9 9-7.7 7.7z"/><circle cx="8" cy="9" r="1.3"/>',
  phone: '<rect x="7" y="2.8" width="10" height="18.4" rx="2.4"/><path d="M11 18h2"/>',
  trash: '<path d="M4.5 7h15M10 7V4.5h4V7M6.5 7l.8 12.5h9.4L17.5 7"/>',
  download: '<path d="M12 4v11m-4.5-4.5L12 15l4.5-4.5M5 19.5h14"/>',
  external: '<path d="M14 4.5h5.5V10M19.5 4.5 11 13"/><path d="M18 14v5.5H4.5V6H10"/>',
  folder: '<path d="M3.5 6.5a1.5 1.5 0 0 1 1.5-1.5h4.3l2 2.3H19a1.5 1.5 0 0 1 1.5 1.5v9.2a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5z"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  back: '<path d="M15 5.5 8.5 12l6.5 6.5"/>',
  zoomin: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2M8.5 11h5M11 8.5v5"/>',
  zoomout: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2M8.5 11h5"/>',
  more: '<path d="M6 12h.01M12 12h.01M18 12h.01" stroke-width="2.6"/>',
  sun: '<circle cx="12" cy="12" r="3.8"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>',
  moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>',
  auto: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01" stroke-width="1.9"/>',
  edit: '<path d="M4.5 19.5h4l10-10-4-4-10 10z"/><path d="m13 7 4 4"/>',
  palette: '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.8-.8 1.8-1.7 0-1.3-1-1.6-1-2.6 0-.8.6-1.4 1.5-1.4h2.2a4 4 0 0 0 4-4C20.5 6.6 16.7 3.5 12 3.5z"/><circle cx="7.8" cy="11" r="1"/><circle cx="10.5" cy="7.6" r="1"/><circle cx="15" cy="7.8" r="1"/>',
  spark: '<path d="M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
  send: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
  brain: '<path d="M9 4.5a3 3 0 0 0-3 3 3 3 0 0 0-1.5 5.2A3 3 0 0 0 7 17.5a2.5 2.5 0 0 0 5 .5V6a2 2 0 0 0-3-1.5zM15 4.5a3 3 0 0 1 3 3 3 3 0 0 1 1.5 5.2 3 3 0 0 1-2.5 4.8 2.5 2.5 0 0 1-5 .5"/>',
  image: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.7"/><path d="m20.5 16-5-5-8 8"/>',
  refresh: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3L19.5 9"/><path d="M19.5 4v5h-5"/>',
};
const icon = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;
const hydrateIcons = (root = document) => $$("[data-i]", root).forEach((el) => { if (!el.firstChild) el.innerHTML = icon(el.dataset.i); });

// ---------- api ----------
async function api(path, opts = {}) {
  const init = { ...opts, headers: { ...(opts.headers || {}) } };
  if (opts.json !== undefined) { init.body = JSON.stringify(opts.json); init.headers["content-type"] = "application/json"; delete init.json; }
  const r = await fetch(path, init);
  if (r.status === 401) { location.reload(); throw new Error("not paired"); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
}

// ---------- state ----------
const S = {
  view: store.get("view", { kind: "all" }),
  sort: store.get("sort", "added"),
  layout: store.get("layout", "grid"),
  cats: [], tags: [], stats: {}, docs: [], local: false,
  selected: null, version: -1,
};
const catColor = (name) => (S.cats.find((c) => c.name === name) || {}).color || "#78716C";
const fmtSize = (b) => b < 1024 ? b + " B" : b < 1048576 ? (b / 1024).toFixed(0) + " KB" : b < 1073741824 ? (b / 1048576).toFixed(1) + " MB" : (b / 1073741824).toFixed(2) + " GB";
const fmtDate = (t) => { const d = new Date(t * 1000); const now = new Date(); return d.toLocaleDateString(undefined, d.getFullYear() === now.getFullYear() ? { month: "short", day: "numeric" } : { year: "numeric", month: "short", day: "numeric" }); };
const plural = (n, w) => `${n.toLocaleString()} ${w}${n === 1 ? "" : "s"}`;
const snip = (s) => esc(s).replace(/\u0002/g, "<mark>").replace(/\u0003/g, "</mark>").replace(/\s+/g, " ");

async function loadState() {
  const st = await api("/api/state");
  S.cats = st.categories; S.tags = st.tags; S.stats = st.stats; S.local = st.local; S.version = st.stats.version;
  if (S.view.kind === "drawer" && !S.cats.some((c) => c.name === S.view.value)) S.view = { kind: "all" };
  if (S.view.kind === "tag" && !S.tags.some((t) => t.name === S.view.value)) S.view = { kind: "all" };
  renderRail();
}

async function loadDocs() {
  const p = new URLSearchParams({ sort: S.view.kind === "recent" ? "opened" : S.sort });
  if (S.view.kind === "drawer") p.set("category", S.view.value);
  if (S.view.kind === "tag") p.set("tag", S.view.value);
  if (S.view.kind === "starred") p.set("starred", "true");
  S.docs = await api("/api/docs?" + p);
  renderShelf();
}

async function refresh() {
  await loadState(); await loadDocs();
  // don't yank the detail panel out from under someone typing in it
  if (S.selected && !$("#detail").contains(document.activeElement)) renderDetail();
}

function setView(v) {
  S.view = v; store.set("view", v); S.selected = null; closeDetail();
  renderRail(); loadDocs(); $("#shelf").scrollTop = 0; syncTabbar();
}

// ---------- rail ----------
function renderRail() {
  const v = S.view;
  const lib = [
    { kind: "all", label: "Everything", i: "library", count: S.stats.n },
    { kind: "starred", label: "Starred", i: "star", count: S.stats.starred },
    { kind: "recent", label: "Recently read", i: "clock", count: "" },
  ];
  $("#nav-library").innerHTML = lib.map((x) => `
    <button class="nav-item ${v.kind === x.kind ? "active" : ""}" data-kind="${x.kind}">
      ${icon(x.i)}<span class="label">${x.label}</span><span class="count">${x.count ?? ""}</span>
    </button>`).join("");
  $("#nav-drawers").innerHTML = S.cats.map((c, i) => `
    <div class="nav-item drawer-item ${v.kind === "drawer" && v.value === c.name ? "active" : ""}" role="button" tabindex="0"
         data-drawer="${esc(c.name)}" style="--c:${c.color}">
      <span class="spine"></span><span class="label">${esc(c.name)}</span>
      <span class="count">${c.count}</span>
      ${c.name !== "Inbox" ? `<button class="more" data-more="${esc(c.name)}" title="Drawer options">${icon("more")}</button>` : `<span class="more"></span>`}
    </div>`).join("");
  $("#nav-tags").innerHTML = S.tags.slice(0, 40).map((t) =>
    `<button class="tag ${v.kind === "tag" && v.value === t.name ? "active" : ""}" data-tag="${esc(t.name)}">${esc(t.name)}</button>`).join("");
  $("#tags-head").hidden = !S.tags.length;
  $("#foot-stats").textContent = `${plural(S.stats.n || 0, "doc")} · ${fmtSize(S.stats.size || 0)}`;
  const pair = $("#btn-pair");
  pair.hidden = !S.local;
  pair.innerHTML = `${icon("phone")}<span>Connect iPhone<small>Scan a code, add to Home Screen</small></span>`;
  renderChips();
}

function renderChips() {
  const v = S.view;
  const items = [{ k: "all", n: "All" }, { k: "starred", n: "Starred" }, ...S.cats.map((c) => ({ k: "drawer", n: c.name, c: c.color }))];
  $("#mobile-drawers").innerHTML = items.map((x) => {
    const on = v.kind === x.k && (x.k !== "drawer" || v.value === x.n);
    return `<button class="chip ${on ? "on" : ""}" data-kind="${x.k}" ${x.k === "drawer" ? `data-drawer="${esc(x.n)}"` : ""} style="${x.c ? `--c:${x.c}` : ""}">${esc(x.n)}</button>`;
  }).join("");
}

$("#nav-library").addEventListener("click", (e) => { const b = e.target.closest("[data-kind]"); if (b) setView({ kind: b.dataset.kind }); });
$("#nav-tags").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tag]"); if (!b) return;
  setView(S.view.kind === "tag" && S.view.value === b.dataset.tag ? { kind: "all" } : { kind: "tag", value: b.dataset.tag });
});
$("#nav-drawers").addEventListener("click", (e) => {
  const more = e.target.closest("[data-more]");
  if (more) { e.stopPropagation(); return drawerMenu(more.dataset.more, more); }
  const d = e.target.closest("[data-drawer]"); if (d) setView({ kind: "drawer", value: d.dataset.drawer });
});
$("#nav-drawers").addEventListener("contextmenu", (e) => {
  const d = e.target.closest("[data-drawer]"); if (!d || d.dataset.drawer === "Inbox") return;
  e.preventDefault(); drawerMenu(d.dataset.drawer, { getBoundingClientRect: () => ({ left: e.clientX, right: e.clientX, top: e.clientY, bottom: e.clientY }) });
});
$("#mobile-drawers").addEventListener("click", (e) => {
  const b = e.target.closest("[data-kind]"); if (!b) return;
  setView(b.dataset.kind === "drawer" ? { kind: "drawer", value: b.dataset.drawer } : { kind: b.dataset.kind });
});
// drag a sheet onto a drawer to file it
$("#nav-drawers").addEventListener("dragover", (e) => {
  const d = e.target.closest("[data-drawer]");
  if (!d || !e.dataTransfer.types.includes("application/x-shelfie-doc")) return;
  e.preventDefault(); $$(".drop-hover").forEach((x) => x !== d && x.classList.remove("drop-hover")); d.classList.add("drop-hover");
});
$("#nav-drawers").addEventListener("dragleave", (e) => { const d = e.target.closest("[data-drawer]"); if (d && !d.contains(e.relatedTarget)) d.classList.remove("drop-hover"); });
$("#nav-drawers").addEventListener("drop", async (e) => {
  const d = e.target.closest("[data-drawer]"); const id = e.dataTransfer.getData("application/x-shelfie-doc");
  $$(".drop-hover").forEach((x) => x.classList.remove("drop-hover"));
  if (!d || !id) return;
  e.preventDefault(); e.stopPropagation();
  await moveDoc(+id, d.dataset.drawer);
});

async function moveDoc(id, drawer) {
  const doc = S.docs.find((x) => x.id === id);
  if (doc && doc.category === drawer) return;
  await api(`/api/docs/${id}`, { method: "PATCH", json: { category: drawer } });
  toast(`Filed into <b>${esc(drawer)}</b>`);
  refresh();
}

// new drawer
$("#btn-new-drawer").innerHTML = icon("plus");
$("#btn-new-drawer").addEventListener("click", () => newDrawerInline());
function newDrawerInline() {
  if (isPhone()) return newDrawerModal();
  if ($(".new-drawer")) return $(".new-drawer input").focus();
  const wrap = document.createElement("div");
  wrap.className = "new-drawer";
  wrap.innerHTML = `<input placeholder="Name the drawer, press Enter" maxlength="60">`;
  $("#nav-drawers").append(wrap);
  const inp = $("input", wrap); inp.focus();
  const done = async (save) => {
    const name = inp.value.trim(); wrap.remove();
    if (save && name) { const r = await api("/api/categories", { method: "POST", json: { name } }); await loadState(); setView({ kind: "drawer", value: r.name }); }
  };
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); });
  inp.addEventListener("blur", () => done(true));
}
function newDrawerModal() {
  modal(`<h2>New drawer</h2><p class="lede">A drawer is a folder inside your Shelfie library.</p>
    <input class="field" id="nd-name" placeholder="e.g. Bills, Receipts, School" maxlength="60">
    <div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" id="nd-ok">Create</button></div>`);
  const inp = $("#nd-name"); setTimeout(() => inp.focus(), 50);
  const go = async () => { const name = inp.value.trim(); if (!name) return; const r = await api("/api/categories", { method: "POST", json: { name } }); closeModal(); await loadState(); setView({ kind: "drawer", value: r.name }); };
  $("#nd-ok").onclick = go; inp.onkeydown = (e) => e.key === "Enter" && go();
}

const SWATCHES = ["#C2410C", "#D9481E", "#B7791F", "#A16207", "#4D7C0F", "#15803D", "#0F766E", "#0E7490", "#1D4ED8", "#4338CA", "#7C3AED", "#A21CAF", "#BE185D", "#9F1239", "#57534E", "#1B1A17"];
function drawerMenu(name, anchor) {
  menu(anchor, [
    { i: "edit", t: "Rename drawer", fn: () => renameDrawer(name) },
    { i: "palette", t: "Change colour", fn: () => recolorDrawer(name) },
    "-",
    { i: "trash", t: "Delete drawer…", danger: true, fn: () => deleteDrawer(name) },
  ]);
}
function renameDrawer(name) {
  modal(`<h2>Rename drawer</h2><p class="lede">The folder on disk is renamed too.</p>
    <input class="field" id="rd-name" value="${esc(name)}" maxlength="60">
    <div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" id="rd-ok">Rename</button></div>`);
  const inp = $("#rd-name"); setTimeout(() => { inp.focus(); inp.select(); }, 50);
  const go = async () => {
    try {
      const r = await api(`/api/categories/${encodeURIComponent(name)}`, { method: "PATCH", json: { name: inp.value.trim() } });
      closeModal(); if (S.view.kind === "drawer" && S.view.value === name) S.view = { kind: "drawer", value: r.name }; store.set("view", S.view); refresh();
    } catch (e) { toast(esc(e.message)); }
  };
  $("#rd-ok").onclick = go; inp.onkeydown = (e) => e.key === "Enter" && go();
}
function recolorDrawer(name) {
  const cur = catColor(name);
  modal(`<h2>${esc(name)}</h2><p class="lede">Pick a colour for this drawer’s tabs.</p>
    <div class="swatches">${SWATCHES.map((c) => `<button class="swatch-btn ${c === cur ? "on" : ""}" style="--c:${c}" data-c="${c}"></button>`).join("")}</div>
    <div class="modal-actions"><button class="btn" data-close>Done</button></div>`);
  $(".swatches").onclick = async (e) => {
    const b = e.target.closest("[data-c]"); if (!b) return;
    $$(".swatch-btn").forEach((x) => x.classList.toggle("on", x === b));
    await api(`/api/categories/${encodeURIComponent(name)}`, { method: "PATCH", json: { color: b.dataset.c } });
    refresh();
  };
}
function deleteDrawer(name) {
  const c = S.cats.find((x) => x.name === name);
  modal(`<h2>Delete “${esc(name)}”?</h2>
    <p>${c && c.count ? `Its ${plural(c.count, "document")} will be moved to your <b>Inbox</b> — nothing is lost.` : "This drawer is empty."}</p>
    <div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn danger" id="dd-ok">Delete drawer</button></div>`);
  $("#dd-ok").onclick = async () => {
    await api(`/api/categories/${encodeURIComponent(name)}`, { method: "DELETE" });
    closeModal(); if (S.view.kind === "drawer" && S.view.value === name) S.view = { kind: "all" }; refresh();
  };
}

// ---------- shelf ----------
function renderShelf() {
  const v = S.view;
  const totalPages = S.docs.reduce((a, d) => a + d.pages, 0);
  const totalSize = S.docs.reduce((a, d) => a + d.size, 0);
  let eyebrow = "The archive", title = "Everything", color = "";
  if (v.kind === "starred") { eyebrow = "Kept close"; title = "Starred"; }
  if (v.kind === "recent") { eyebrow = "Reading history"; title = "Recently <em>read</em>"; }
  if (v.kind === "tag") { eyebrow = "Tagged"; title = "#" + esc(v.value); }
  if (v.kind === "drawer") {
    const i = S.cats.findIndex((c) => c.name === v.value);
    eyebrow = `Drawer ${String(i + 1).padStart(2, "0")}`; title = esc(v.value); color = catColor(v.value);
  }
  $("#eyebrow").innerHTML = `<span class="swatch" style="${color ? `--c:${color}` : ""}"></span>${eyebrow}`;
  $("#shelf-title").innerHTML = title;
  $("#shelf-meta").textContent = `${plural(S.docs.length, "document")} · ${plural(totalPages, "page")} · ${fmtSize(totalSize)}`;
  $("#sort").value = S.sort;
  $("#sort").closest(".sort").hidden = v.kind === "recent";
  $$("#view-toggle button").forEach((b) => b.classList.toggle("on", b.dataset.view === S.layout));
  renderDocs();
}

function renderDocs() {
  const el = $("#docs");
  el.className = "docs " + S.layout;
  if (!S.docs.length) { el.innerHTML = emptyState(); return; }
  if (S.layout === "grid") {
    el.innerHTML = S.docs.map((d, n) => `
      <div class="sheet ${d.pages > 1 ? "multi" : ""} ${S.selected === d.id ? "selected" : ""}" tabindex="0" draggable="true"
           data-id="${d.id}" style="--c:${catColor(d.category)};--n:${Math.min(n, 30)}">
        ${S.view.kind === "drawer" ? "" : `<span class="ftab">${esc(d.category)}</span>`}
        <div class="paper ${d.processing ? "loading" : ""}">
          ${d.processing ? `<div class="ph"></div>` : `<img loading="lazy" src="${d.thumb}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ph'}))">`}
          <button class="star ${d.favorite ? "on" : ""}" data-star="${d.id}" title="Star">${icon("star")}</button>
          ${d.pages ? `<span class="pp">${d.pages} pp</span>` : ""}
        </div>
        <div class="s-title">${esc(d.title)}</div>
        <div class="s-meta">${fmtDate(d.added)} · ${fmtSize(d.size)}</div>
        ${d.tags.length ? `<div class="s-tags">${d.tags.slice(0, 3).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
      </div>`).join("");
  } else {
    el.innerHTML = `<div class="ledger-head"><span></span><span>Title</span><span class="hide-sm">Drawer</span><span class="hide-sm">Pages</span><span class="hide-sm">Size</span><span class="hide-sm">Added</span><span></span></div>` +
      S.docs.map((d, n) => `
      <div class="row ${S.selected === d.id ? "selected" : ""}" tabindex="0" draggable="true" data-id="${d.id}" style="--c:${catColor(d.category)};--n:${Math.min(n, 40)}">
        <span class="mini" style="${d.processing ? "" : `background-image:url('${d.thumb}')`}"></span>
        <span style="min-width:0"><div class="r-title">${esc(d.title)}</div>${d.tags.length ? `<div class="r-sub">${d.tags.map((t) => "#" + esc(t)).join("  ")}</div>` : ""}</span>
        <span class="r-cat hide-sm">${esc(d.category)}</span>
        <span class="r-num hide-sm">${d.pages || "—"}</span>
        <span class="r-num hide-sm">${fmtSize(d.size)}</span>
        <span class="r-num hide-sm">${fmtDate(d.added)}</span>
        <button class="star ${d.favorite ? "on" : ""}" data-star="${d.id}" title="Star">${icon("star")}</button>
      </div>`).join("");
  }
}

function emptyState() {
  const v = S.view;
  const msg = v.kind === "starred" ? ["Nothing starred yet", "Tap the star on any document to keep it here."]
    : v.kind === "recent" ? ["Nothing read yet", "Documents you open show up here."]
    : v.kind === "drawer" ? ["This drawer is empty", isPhone() ? "Tap + to add PDFs to this drawer." : "Drop PDFs anywhere on this window, or drag sheets onto the drawer in the sidebar."]
    : ["Your archive is empty", isPhone() ? "Tap + to add your first PDFs." : "Drop PDFs anywhere on this window, or use Add PDFs. They’re stored as plain files in your Shelfie folder."];
  return `<div class="empty"><div class="stack"><i></i><i></i><i></i></div><h3>${msg[0]}</h3><p>${msg[1]}</p>
    ${v.kind === "starred" || v.kind === "recent" ? "" : `<button class="btn primary" data-act="add">${icon("plus")} Add PDFs</button>`}</div>`;
}

const docsEl = $("#docs");
let pressTimer = null, longPressed = false;
docsEl.addEventListener("click", (e) => {
  if (e.target.closest('[data-act="add"]')) return pickFiles();
  const star = e.target.closest("[data-star]");
  if (star) { e.stopPropagation(); return toggleStar(+star.dataset.star); }
  const card = e.target.closest("[data-id]"); if (!card) return;
  if (longPressed) { longPressed = false; return; }
  const id = +card.dataset.id;
  if (isPhone()) return openViewer(id);
  select(id);
});
docsEl.addEventListener("dblclick", (e) => { const c = e.target.closest("[data-id]"); if (c && !e.target.closest("[data-star]")) openViewer(+c.dataset.id); });
docsEl.addEventListener("keydown", (e) => {
  const c = e.target.closest("[data-id]"); if (!c) return;
  if (e.key === "Enter") openViewer(+c.dataset.id);
  if (e.key === " ") { e.preventDefault(); select(+c.dataset.id); }
});
docsEl.addEventListener("contextmenu", (e) => {
  const c = e.target.closest("[data-id]"); if (!c || isPhone()) return;
  e.preventDefault(); const id = +c.dataset.id; select(id); docMenu(id, { getBoundingClientRect: () => ({ left: e.clientX, right: e.clientX, top: e.clientY, bottom: e.clientY }) });
});
// long-press on phone → details sheet
docsEl.addEventListener("touchstart", (e) => {
  const c = e.target.closest("[data-id]"); if (!c) return;
  longPressed = false;
  pressTimer = setTimeout(() => { longPressed = true; navigator.vibrate?.(10); select(+c.dataset.id); }, 480);
}, { passive: true });
["touchend", "touchmove", "touchcancel"].forEach((ev) => docsEl.addEventListener(ev, () => clearTimeout(pressTimer), { passive: true }));
docsEl.addEventListener("dragstart", (e) => {
  const c = e.target.closest("[data-id]"); if (!c) return;
  e.dataTransfer.setData("application/x-shelfie-doc", c.dataset.id); e.dataTransfer.effectAllowed = "move";
});

function docMenu(id, anchor) {
  const d = S.docs.find((x) => x.id === id); if (!d) return;
  menu(anchor, [
    { i: "library", t: "Read", fn: () => openViewer(id) },
    S.local && { i: "external", t: "Open in system viewer", fn: () => api(`/api/docs/${id}/open-external`, { method: "POST" }) },
    S.local && { i: "folder", t: "Show in Files", fn: () => api(`/api/docs/${id}/open-external?reveal=true`, { method: "POST" }) },
    { i: "star", t: d.favorite ? "Unstar" : "Star", fn: () => toggleStar(id) },
    "-",
    { i: "trash", t: "Move to trash", danger: true, fn: () => trashDoc(id) },
  ].filter(Boolean));
}

async function toggleStar(id) {
  const d = S.docs.find((x) => x.id === id) || (await api(`/api/docs/${id}`));
  await api(`/api/docs/${id}`, { method: "PATCH", json: { favorite: !d.favorite } });
  await refresh();
  if (!$("#viewer").hidden && V.doc?.id === id) { V.doc.favorite = !d.favorite; $("#v-star").classList.toggle("on", V.doc.favorite); }
}

async function trashDoc(id) {
  const d = S.docs.find((x) => x.id === id);
  await api(`/api/docs/${id}`, { method: "DELETE" });
  if (S.selected === id) closeDetail();
  toast(`Moved <b>${esc(d?.title || "document")}</b> to Shelfie’s trash`);
  refresh();
}

$("#sort").addEventListener("change", (e) => { S.sort = e.target.value; store.set("sort", S.sort); loadDocs(); });
$("#view-toggle").addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (!b) return; S.layout = b.dataset.view; store.set("layout", S.layout); renderShelf(); });
$('#view-toggle [data-view="grid"]').innerHTML = icon("grid");
$('#view-toggle [data-view="list"]').innerHTML = icon("list");

// ---------- detail panel ----------
function select(id) {
  S.selected = id;
  $$("#docs [data-id]").forEach((c) => c.classList.toggle("selected", +c.dataset.id === id));
  renderDetail(); openDetail();
}
function openDetail() {
  const el = $("#detail"); el.classList.add("open"); el.setAttribute("aria-hidden", "false");
  if (isPhone() && !$(".scrim")) { const s = document.createElement("div"); s.className = "scrim"; s.onclick = closeDetail; document.body.append(s); }
}
function closeDetail() {
  detailShownId = null;
  const el = $("#detail"); el.classList.remove("open"); el.setAttribute("aria-hidden", "true"); $(".scrim")?.remove();
  S.selected = null; $$("#docs .selected").forEach((c) => c.classList.remove("selected"));
}

// ---------- shared: drawer cabinet (sliding selector) ----------
function cabinetHTML(selected, id = "") {
  return `<div class="cabinet" ${id ? `id="${id}"` : ""} role="radiogroup">
    <span class="cab-ind"></span>
    ${S.cats.map((x) => `<button type="button" role="radio" aria-checked="${x.name === selected}" class="cab ${x.name === selected ? "on" : ""}" style="--c:${x.color}" data-name="${esc(x.name)}"><i></i>${esc(x.name)}</button>`).join("")}
    <button type="button" class="cab cab-new" data-new title="New drawer">${icon("plus")}</button>
  </div>`;
}
function placeCabinet(el, animate = true) {
  const on = el.querySelector(".cab.on"), ind = el.querySelector(".cab-ind");
  if (!on || !ind) { if (ind) ind.style.opacity = 0; return; }
  if (!animate) ind.style.transition = "none";
  ind.style.opacity = 1;
  ind.style.setProperty("--c", on.style.getPropertyValue("--c"));
  ind.style.transform = `translate3d(${on.offsetLeft}px, ${on.offsetTop}px, 0)`;
  ind.style.width = on.offsetWidth + "px"; ind.style.height = on.offsetHeight + "px";
  if (!animate) { void ind.offsetWidth; ind.style.transition = ""; }
  const sc = on.offsetLeft - el.clientWidth / 2 + on.offsetWidth / 2;
  el.scrollTo({ left: sc, behavior: animate ? "smooth" : "auto" });
}
function bindCabinet(el, onPick) {
  requestAnimationFrame(() => placeCabinet(el, false)); setTimeout(() => placeCabinet(el, false), 60);
  el.addEventListener("click", async (e) => {
    const b = e.target.closest(".cab"); if (!b) return;
    let name = b.dataset.name;
    if (b.dataset.new !== undefined) {
      name = (prompt("Name the new drawer") || "").trim(); if (!name) return;
      name = (await api("/api/categories", { method: "POST", json: { name } })).name;
      await loadState();
      const tmp = document.createElement("div"); tmp.innerHTML = cabinetHTML(name);
      el.replaceChildren(...tmp.firstElementChild.children); placeCabinet(el, false);
    }
    el.querySelectorAll(".cab").forEach((x) => { x.classList.toggle("on", x.dataset.name === name); x.setAttribute("aria-checked", x.dataset.name === name); });
    placeCabinet(el);
    onPick(name);
  });
}
const callNo = (d) => `${(d.category || "INB").replace(/[^A-Za-z0-9]/g, "").slice(0, 3).toUpperCase() || "DOC"}·${String(d.id).padStart(4, "0")}`;
function relTime(t) {
  if (!t) return "never";
  const s = Date.now() / 1000 - t;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return new Date(t * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
function holdToConfirm(btn, ms, onDone) {
  let t = 0;
  const start = (e) => { e.preventDefault(); btn.classList.add("holding"); btn.style.setProperty("--hold", ms + "ms"); t = setTimeout(() => { btn.classList.remove("holding"); btn.classList.add("done"); onDone(); }, ms); };
  const stop = () => { clearTimeout(t); btn.classList.remove("holding"); };
  btn.addEventListener("pointerdown", start); ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => btn.addEventListener(ev, stop));
  btn.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && !e.repeat) start(e); });
  btn.addEventListener("keyup", stop);
}

// ---------- detail panel: a library catalog card ----------
let detailShownId = null;
async function renderDetail() {
  const id = S.selected; if (id == null) return;
  let d = S.docs.find((x) => x.id === id);
  if (!d) { try { d = await api(`/api/docs/${id}`); } catch { return closeDetail(); } }
  const c = catColor(d.category);
  const fresh = detailShownId !== id; detailShownId = id;
  const stack = Math.min(3, Math.max(0, (d.pages || 1) - 1));
  $("#detail").innerHTML = `<div class="detail-inner dcard ${fresh ? "enter" : ""}" style="--c:${c}">
    <div class="dc-top s1">
      <span class="dc-call" title="Catalog number">${callNo(d)}</span>
      <button class="icon-btn sm" id="d-close" title="Close (Esc)">${icon("x")}</button>
    </div>
    <div class="dc-stage s2" id="d-stage">
      <div class="dc-cover" id="d-cover" title="Read">
        ${Array.from({ length: stack }, (_, i) => `<span class="dc-sheet" style="--i:${i + 1}"></span>`).join("")}
        <div class="dc-page" style="${d.processing ? "" : `background-image:url('${d.thumb}')`}">${d.processing ? `<span class="dc-wait">Indexing…</span>` : ""}</div>
        <span class="dc-tab">${esc(d.category)}</span>
        <button class="dc-star ${d.favorite ? "on" : ""}" id="d-star" title="${d.favorite ? "Unstar" : "Star"}">${icon("star")}</button>
        <span class="dc-glare"></span>
      </div>
    </div>
    <div class="s3">
      <textarea class="dc-title" id="d-title" rows="1" spellcheck="false" aria-label="Title">${esc(d.title)}</textarea>
      <div class="dc-titlehint">${icon("edit")} click to rename · the file is renamed too</div>
    </div>
    <div class="dc-stats s4">
      <div><b>${d.pages || "–"}</b><span>${d.pages === 1 ? "page" : "pages"}</span></div>
      <div><b>${fmtSize(d.size).split(" ")[0]}</b><span>${fmtSize(d.size).split(" ")[1] || ""}</span></div>
      <div><b>${relTime(d.opened).replace(/ ago$/, "")}</b><span>${d.opened ? (/ago$/.test(relTime(d.opened)) ? "since read" : "last read") : "not read yet"}</span></div>
    </div>
    <section class="dc-sec s5"><div class="dc-label">Drawer</div>${cabinetHTML(d.category, "d-cab")}</section>
    <section class="dc-sec s6"><div class="dc-label">Tags</div>
      <div class="tag-edit dc-tags" id="d-tags">
        ${d.tags.map((t) => `<span class="tag">${esc(t)}<button data-rm="${esc(t)}" title="Remove">×</button></span>`).join("")}
        <input id="d-tag-in" placeholder="${d.tags.length ? "add…" : "Add a tag, press Enter"}" list="tag-list"></div>
      <datalist id="tag-list">${S.tags.map((t) => `<option value="${esc(t.name)}">`).join("")}</datalist>
    </section>
    <div class="dc-actions s7">
      <button class="dc-read" id="d-read"><span>Read</span><span class="dc-arrow">${icon("back")}</span></button>
      <div class="dc-round">
        ${S.local ? `<button id="d-reveal">${icon("folder")}<span>Files</span></button><button id="d-ext">${icon("external")}<span>Open</span></button>` : ""}
        <a href="/api/docs/${d.id}/file?download=true" download>${icon("download")}<span>Save</span></a>
      </div>
    </div>
    <dl class="dc-ledger s8">
      <div><dt>Added</dt><dd>${new Date(d.added * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</dd></div>
      ${d.opened ? `<div><dt>Last read</dt><dd>${new Date(d.opened * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</dd></div>` : ""}
      <div><dt>File</dt><dd><button class="dc-path" id="d-path" title="Copy path">${esc(d.path)}</button></dd></div>
    </dl>
    <button class="dc-trash s9" id="d-trash"><span class="dc-fill"></span>${icon("trash")}<span class="dc-tl">Hold to move to trash</span></button>
  </div>`;
  const ta = $("#d-title");
  const fit = () => { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + "px"; }; fit();
  ta.oninput = fit;
  ta.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); ta.blur(); } if (e.key === "Escape") { ta.value = d.title; ta.blur(); } };
  ta.onblur = async () => { const t = ta.value.trim(); if (t && t !== d.title) { await api(`/api/docs/${d.id}`, { method: "PATCH", json: { title: t } }); toast("Renamed"); refresh(); } };
  $("#d-close").onclick = closeDetail;
  $("#d-read").onclick = () => openViewer(d.id);
  $("#d-cover").onclick = (e) => { if (!e.target.closest("#d-star")) openViewer(d.id); };
  $("#d-star").onclick = (e) => { e.stopPropagation(); const b = e.currentTarget; b.classList.add("burst"); b.classList.toggle("on"); setTimeout(() => toggleStar(d.id), 380); };
  holdToConfirm($("#d-trash"), 1100, () => trashDoc(d.id));
  if ($("#d-reveal")) $("#d-reveal").onclick = () => api(`/api/docs/${d.id}/open-external?reveal=true`, { method: "POST" });
  if ($("#d-ext")) $("#d-ext").onclick = () => api(`/api/docs/${d.id}/open-external`, { method: "POST" });
  $("#d-path").onclick = async () => { try { await navigator.clipboard.writeText(`${S.stats.root}/${d.path}`); toast("Path copied"); } catch { toast(esc(`${S.stats.root}/${d.path}`)); } };
  bindCabinet($("#d-cab"), (name) => { $(".dcard").style.setProperty("--c", catColor(name)); $(".dc-tab").textContent = name; moveDoc(d.id, name); });
  // the cover tilts toward the pointer
  const stage = $("#d-stage"), cover = $("#d-cover");
  stage.onpointermove = (e) => {
    const r = stage.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
    cover.style.setProperty("--ry", `${x * 14}deg`); cover.style.setProperty("--rx", `${-y * 12}deg`);
    cover.style.setProperty("--gx", `${(x + .5) * 100}%`); cover.style.setProperty("--gy", `${(y + .5) * 100}%`);
  };
  stage.onpointerleave = () => { cover.style.setProperty("--ry", "0deg"); cover.style.setProperty("--rx", "0deg"); };
  const saveTags = async (tags) => { await api(`/api/docs/${d.id}`, { method: "PATCH", json: { tags } }); await refresh(); await renderDetail(); $("#d-tag-in")?.focus(); };
  const tin = $("#d-tag-in");
  tin.onkeydown = (e) => {
    if ((e.key === "Enter" || e.key === ",") && tin.value.trim()) { e.preventDefault(); saveTags([...d.tags, tin.value.trim()]); }
    if (e.key === "Backspace" && !tin.value && d.tags.length) saveTags(d.tags.slice(0, -1));
  };
  $("#d-tags").onclick = (e) => { const b = e.target.closest("[data-rm]"); if (b) saveTags(d.tags.filter((t) => t !== b.dataset.rm)); else tin.focus(); };
}

// ---------- viewer ----------
const V = { doc: null, pdf: null, zoom: 1, rendered: new Map(), lib: null, pages: [], queue: [], busy: false, task: null, width: 0 };
async function openViewer(id, page = 1) {
  let d = S.docs.find((x) => x.id === id) || (await api(`/api/docs/${id}`));
  V.doc = { ...d };
  const vw = $("#viewer"); vw.hidden = false; vw.style.setProperty("--c", catColor(d.category));
  $("#v-title").textContent = d.title; $("#v-page").textContent = "";
  $("#v-star").classList.toggle("on", !!d.favorite);
  $("#v-ext").hidden = !S.local;
  $("#v-pages").innerHTML = `<div class="v-loading">Opening…</div>`;
  history.pushState({ viewer: id }, "");
  try {
    V.lib ??= await import("/vendor/pdf.min.mjs");
    V.lib.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.min.mjs";
    V.pdf = await V.lib.getDocument({ url: `/api/docs/${id}/file`, isEvalSupported: false }).promise;
  } catch (e) {
    $("#v-pages").innerHTML = `<div class="v-loading">Couldn’t open this PDF (${esc(e.message)}).</div>`; return;
  }
  V.zoom = 1; await layoutPages();
  if (page > 1) { const P = V.pages[Math.min(page, V.pdf.numPages) - 1]; $("#v-pages").scrollTop = P.top - 12; schedule(); }
  setTimeout(refresh, 600); // "recently read"
}
// Pages are laid out once with known positions; scrolling only does arithmetic, and a small
// queue renders the pages nearest the viewport one at a time, dropping far-away canvases.
async function layoutPages(keepPosition = false) {
  const wrap = $("#v-pages");
  const prevRatio = keepPosition ? wrap.scrollTop / Math.max(1, wrap.scrollHeight - wrap.clientHeight) : 0;
  if (V.task) { V.task.cancel?.(); V.task = null; }
  V.rendered.clear(); V.queue = []; V.busy = false;
  const first = await V.pdf.getPage(1);
  const base = first.getViewport({ scale: 1 });
  V.base = base;
  const avail = Math.min(wrap.clientWidth - (isPhone() ? 0 : 48), 980);
  V.scale = (avail / base.width) * V.zoom;
  V.width = wrap.clientWidth;
  const frag = document.createDocumentFragment();
  V.pages = [];
  const gap = isPhone() ? 10 : 16, padTop = isPhone() ? 12 : 24;
  let top = padTop;
  for (let n = 1; n <= V.pdf.numPages; n++) {
    const w = base.width * V.scale, h = base.height * V.scale;
    const pg = document.createElement("div"); pg.className = "v-pg"; pg.dataset.n = n;
    pg.style.width = w + "px"; pg.style.height = h + "px";
    pg.innerHTML = `<span class="n">${n}</span>`;
    frag.append(pg);
    V.pages.push({ n, el: pg, top, h });
    top += h + gap;
  }
  wrap.replaceChildren(frag);
  if (keepPosition) wrap.scrollTop = prevRatio * (wrap.scrollHeight - wrap.clientHeight);
  schedule();
}
function visibleRange() {
  const wrap = $("#v-pages"), y0 = wrap.scrollTop, y1 = y0 + wrap.clientHeight;
  const P = V.pages; let lo = 0, hi = P.length - 1;
  while (lo < hi) { const m = (lo + hi) >> 1; if (P[m].top + P[m].h < y0) lo = m + 1; else hi = m; }
  let last = lo; while (last + 1 < P.length && P[last + 1].top < y1) last++;
  let cur = lo; const mid = y0 + wrap.clientHeight / 3;
  for (let i = lo; i <= last; i++) if (P[i].top <= mid) cur = i;
  return { first: lo, last, cur };
}
let schedRaf = 0;
function schedule() {
  if (schedRaf || !V.pdf || !V.pages?.length) return;
  schedRaf = requestAnimationFrame(() => {
    schedRaf = 0;
    if (!V.pdf) return;
    const { first, last, cur } = visibleRange();
    $("#v-page").textContent = `${cur + 1} / ${V.pdf.numPages}`;
    const want = [];
    for (let i = first; i <= last; i++) want.push(i);
    for (let d = 1; d <= 3; d++) { if (last + d < V.pages.length) want.push(last + d); if (first - d >= 0) want.push(first - d); }
    V.queue = want.filter((i) => !V.rendered.has(i));
    // free memory far away from the viewport
    for (const i of [...V.rendered.keys()]) if (i < first - 6 || i > last + 8) dropPage(i);
    pump();
  });
}
async function pump() {
  if (V.busy || !V.queue.length || !V.pdf) return;
  V.busy = true;
  const i = V.queue.shift();
  const P = V.pages[i], pdf = V.pdf;
  try {
    const page = await pdf.getPage(P.n);
    if (pdf !== V.pdf) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const vp = page.getViewport({ scale: V.scale * dpr });
    const canvas = document.createElement("canvas"); canvas.width = Math.floor(vp.width); canvas.height = Math.floor(vp.height);
    V.task = page.render({ canvasContext: canvas.getContext("2d", { alpha: false }), viewport: vp });
    await V.task.promise;
    V.task = null;
    if (pdf !== V.pdf) return;
    P.el.querySelector("canvas")?.remove(); P.el.prepend(canvas);
    V.rendered.set(i, true);
  } catch {} finally {
    V.busy = false;
    if (pdf === V.pdf) { if (V.queue.length) setTimeout(pump, 0); }
  }
}
function dropPage(i) {
  V.rendered.delete(i);
  const c = V.pages[i]?.el.querySelector("canvas"); if (c) { c.width = c.height = 0; c.remove(); }
}
$("#v-pages").addEventListener("scroll", schedule, { passive: true });
function closeViewer(fromPop) {
  if ($("#viewer").hidden) return;
  $("#viewer").hidden = true; V.task?.cancel?.(); V.pdf?.destroy(); V.pdf = null; V.pages = []; $("#v-pages").innerHTML = "";
  if (!fromPop && history.state?.viewer) history.back();
}
window.addEventListener("popstate", () => closeViewer(true));
async function zoomBy(f) {
  V.zoom = Math.max(.4, Math.min(4, V.zoom * f)); await layoutPages(true);
}
$("#v-back").innerHTML = icon(isPhone() ? "back" : "x"); $("#v-zoomin").innerHTML = icon("zoomin"); $("#v-zoomout").innerHTML = icon("zoomout");
$("#v-star").innerHTML = icon("star"); $("#v-ext").innerHTML = icon("external"); $("#v-dl").innerHTML = icon("download"); $("#v-info").innerHTML = icon("info");
$("#v-back").onclick = () => closeViewer();
$("#v-zoomin").onclick = () => zoomBy(1.2); $("#v-zoomout").onclick = () => zoomBy(1 / 1.2);
$("#v-star").onclick = () => toggleStar(V.doc.id);
$("#v-ext").onclick = () => api(`/api/docs/${V.doc.id}/open-external`, { method: "POST" });
$("#v-dl").onclick = () => { const a = document.createElement("a"); a.href = `/api/docs/${V.doc.id}/file?download=true`; a.download = ""; document.body.append(a); a.click(); a.remove(); };
$("#v-info").onclick = () => { const id = V.doc.id; closeViewer(); select(id); };
let resizeT; window.addEventListener("resize", () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => { if (V.pdf && Math.abs($("#v-pages").clientWidth - V.width) > 24) layoutPages(true); }, 250);
});
// smooth keyboard paging inside the reader
document.addEventListener("keydown", (e) => {
  if ($("#viewer").hidden || e.target.matches("input, textarea")) return;
  const wrap = $("#v-pages"), h = wrap.clientHeight;
  const by = { ArrowDown: 80, ArrowUp: -80, PageDown: h * .9, PageUp: -h * .9, " ": e.shiftKey ? -h * .9 : h * .9 }[e.key];
  if (by) { e.preventDefault(); wrap.scrollBy({ top: by, behavior: "smooth" }); }
  if (e.key === "Home") wrap.scrollTo({ top: 0, behavior: "smooth" });
  if (e.key === "End") wrap.scrollTo({ top: wrap.scrollHeight, behavior: "smooth" });
});

// ---------- command palette ----------
const PAL = { items: [], idx: 0, t: null, seq: 0 };
function openPalette() {
  $("#palette").hidden = false; const q = $("#palette-q"); q.value = ""; q.focus();
  renderPaletteResults(null);
}
function closePalette() { $("#palette").hidden = true; syncTabbar(); }
$("#palette-close").innerHTML = icon("x");
$("#palette-close").onclick = closePalette;
$("#palette").addEventListener("click", (e) => { if (e.target.id === "palette") closePalette(); });
$("#palette-q").addEventListener("input", (e) => {
  clearTimeout(PAL.t); const q = e.target.value.trim();
  PAL.t = setTimeout(async () => {
    const seq = ++PAL.seq;
    if (!q) return renderPaletteResults(null);
    const res = await api("/api/docs?q=" + encodeURIComponent(q));
    if (seq === PAL.seq) renderPaletteResults(res, q);
  }, 120);
});
$("#palette-q").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { PAL.idx = Math.min(PAL.items.length - 1, PAL.idx + 1); hiPal(); e.preventDefault(); }
  if (e.key === "ArrowUp") { PAL.idx = Math.max(0, PAL.idx - 1); hiPal(); e.preventDefault(); }
  if (e.key === "Enter" && PAL.items[PAL.idx]) { const id = PAL.items[PAL.idx].id; closePalette(); openViewer(id); }
  if (e.key === "Escape") closePalette();
});
$("#palette-results").addEventListener("click", (e) => {
  const b = e.target.closest("[data-pid]"); if (!b) return;
  closePalette();
  if (b.dataset.drawer) setView({ kind: "drawer", value: b.dataset.drawer }); else openViewer(+b.dataset.pid);
});
function renderPaletteResults(res, q) {
  const box = $("#palette-results");
  if (res === null) {
    const recent = [...S.docs].sort((a, b) => b.opened - a.opened).filter((d) => d.opened).slice(0, 5);
    PAL.items = recent; PAL.idx = 0;
    box.innerHTML = (recent.length ? `<div class="d-label" style="padding:10px 10px 4px">Recently read</div>` + recent.map(palItem).join("") : "") +
      `<div class="d-label" style="padding:12px 10px 4px">Drawers</div>` +
      S.cats.map((c) => `<button class="p-item" data-pid="d" data-drawer="${esc(c.name)}" style="--c:${c.color}"><span class="mini" style="background:var(--c)"></span><span><div class="t">${esc(c.name)}</div><div class="m">${plural(c.count, "document")}</div></span></button>`).join("") +
      (isPhone() ? "" : `<div class="p-hint"><span>↑↓ move</span><span>↵ open</span><span>esc close</span><span style="margin-left:auto">searches the text inside every PDF</span></div>`);
    hiPal(); return;
  }
  PAL.items = res; PAL.idx = 0;
  box.innerHTML = res.length ? res.slice(0, 50).map(palItem).join("") : `<div class="p-empty">Nothing matches “${esc(q)}”.</div>`;
  hiPal();
}
function palItem(d) {
  return `<button class="p-item" data-pid="${d.id}" style="--c:${catColor(d.category)}">
    <span class="mini" style="${d.processing ? "" : `background-image:url('${d.thumb}')`}"></span>
    <span style="min-width:0"><div class="t">${esc(d.title)}</div>
      <div class="m"><span class="c">${esc(d.category)}</span><span>${d.pages} pp</span>${d.tags.map((t) => `<span>#${esc(t)}</span>`).join("")}</div>
      ${d.snippet && d.snippet.includes("\u0002") ? `<div class="s">${snip(d.snippet)}</div>` : ""}</span></button>`;
}
function hiPal() { $$("#palette-results [data-pid]:not([data-drawer])").forEach((b, i) => b.classList.toggle("on", i === PAL.idx)); }
$("#btn-search").onclick = openPalette;

// ---------- adding files ----------
function pickFiles() { $("#file-input").click(); }
$("#btn-add").onclick = pickFiles;
$("#file-input").addEventListener("change", (e) => { const files = [...e.target.files]; e.target.value = ""; if (files.length) upload(files, currentDrawer()); });
const currentDrawer = () => (S.view.kind === "drawer" ? S.view.value : "Inbox");

function upload(files, drawer) {
  const images = files.filter((f) => f.type.startsWith("image/") || /\.(heic|heif|jpe?g|png|webp)$/i.test(f.name));
  if (images.length) window.Shelfie.convertPhotos(images, drawer);
  files = files.filter((f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name));
  if (!files.length) { if (!images.length) toast("Only PDFs and photos of pages can be added"); return; }
  const t = toast(`Filing ${plural(files.length, "PDF")} into <b>${esc(drawer)}</b> <span class="bar"><i></i></span>`, 0);
  const fd = new FormData(); files.forEach((f) => fd.append("files", f, f.name)); fd.append("category", drawer);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) $(".bar i", t).style.width = (e.loaded / e.total) * 100 + "%"; };
  xhr.onload = () => {
    t.remove();
    if (xhr.status !== 200) return toast("Upload failed");
    const n = JSON.parse(xhr.responseText).added.length;
    toast(`Filed ${plural(n, "PDF")} into <b>${esc(drawer)}</b>`, 3000, drawer !== currentDrawer() && S.view.kind !== "all" ? { label: "View", fn: () => setView({ kind: "drawer", value: drawer }) } : null);
    refresh();
  };
  xhr.onerror = () => { t.remove(); toast("Upload failed — is Shelfie running?"); };
  xhr.send(fd);
}

// drop anywhere → "File it." overlay with drawer targets
let dragDepth = 0;
const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
window.addEventListener("dragenter", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault(); dragDepth++;
  if (dragDepth === 1) {
    $("#drop-default").textContent = currentDrawer();
    $("#drop-targets").innerHTML = S.cats.map((c) => `<div class="drop-target" data-drawer="${esc(c.name)}" style="--c:${c.color}">${esc(c.name)}<small>${plural(c.count, "doc")}</small></div>`).join("");
    $("#drop").hidden = false;
  }
});
window.addEventListener("dragover", (e) => {
  if (!hasFiles(e)) return; e.preventDefault();
  const t = e.target.closest?.(".drop-target"); $$(".drop-target").forEach((x) => x.classList.toggle("hover", x === t));
});
window.addEventListener("dragleave", (e) => { if (!hasFiles(e)) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $("#drop").hidden = true; });
window.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return; e.preventDefault(); dragDepth = 0; $("#drop").hidden = true;
  const t = e.target.closest?.(".drop-target");
  upload([...e.dataTransfer.files], t ? t.dataset.drawer : currentDrawer());
});

// ---------- clipboard helpers (shared with the Librarian chat box) ----------
const stamp = () => { const d = new Date(); return `${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })} ${d.toTimeString().slice(0, 5).replace(":", ".")}`; };
const clip = {
  fromEvent(dt) {
    if (!dt) return [];
    const out = [];
    for (const it of dt.items || []) if (it.kind === "file") { const f = it.getAsFile(); if (f) out.push(f); }
    if (!out.length) out.push(...(dt.files || []));
    let n = 0;
    return out.filter((f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name) || f.type.startsWith("image/"))
      .map((f) => (f.name && !/^image\.\w+$/.test(f.name)) ? f
        : new File([f], `Pasted ${f.type.startsWith("image/") ? "photo" : "PDF"} ${stamp()}${n++ ? ` (${n})` : ""}.${(f.type.split("/")[1] || "png").replace("jpeg", "jpg")}`, { type: f.type }));
  },
  // Is this paste ordinary text, or should we fetch an image/file from the system clipboard?
  // WebKitGTK often reports an image copy only as text/html (browsers) or text/uri-list (Files app).
  kind(dt) {
    const types = [...(dt?.types || [])];
    if (!types.includes("text/plain")) return "native";
    const t = (dt.getData("text/plain") || "").trim();
    if (/^(file:\/\/|\/)[^\n]*\.(png|jpe?g|webp|gif|bmp|heic|tiff?|pdf)$/im.test(t)) return "native"; // a copied file path
    return "text";
  },
  // desktop window only: files copied in the Files app, or an image, straight from the system clipboard
  async native() {
    const api = window.pywebview?.api;
    if (!api?.clipboard_files) return [];
    try {
      const list = await api.clipboard_files();
      return (list || []).map((r, i) => {
        const bin = atob(r.data), buf = new Uint8Array(bin.length);
        for (let k = 0; k < bin.length; k++) buf[k] = bin.charCodeAt(k);
        return new File([buf], r.name || `Pasted photo ${stamp()}${i ? ` (${i + 1})` : ""}.png`, { type: r.type });
      });
    } catch { return []; }
  },
};

// ---------- Import sheet ("new arrivals"): paste PDFs or photos anywhere in the library ----------
const IMP = { open: false, items: [], drawer: "Inbox", tags: [], star: false, combine: true, lens: true, title: "" };
const isPdf = (f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const stem = (n) => n.replace(/\.[^.]+$/, "").replace(/[_]+/g, " ").trim();

async function pdfInfo(file) {
  try {
    V.lib ??= await import("/vendor/pdf.min.mjs");
    V.lib.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.min.mjs";
    const pdf = await V.lib.getDocument({ data: new Uint8Array(await file.arrayBuffer()), isEvalSupported: false }).promise;
    const page = await pdf.getPage(1);
    const vp = page.getViewport({ scale: 1 }); const sc = 320 / vp.width;
    const v2 = page.getViewport({ scale: sc });
    const cv = document.createElement("canvas"); cv.width = v2.width; cv.height = v2.height;
    await page.render({ canvasContext: cv.getContext("2d"), viewport: v2 }).promise;
    const n = pdf.numPages; pdf.destroy();
    return { pages: n, thumb: cv.toDataURL("image/jpeg", .85) };
  } catch { return { pages: 0, thumb: "" }; }
}

function openImport(files) {
  files = files.filter((f) => isPdf(f) || f.type.startsWith("image/"));
  if (!files.length) return;
  if (!IMP.open) Object.assign(IMP, { items: [], drawer: currentDrawer(), tags: [], star: false, combine: true, lens: store.get("lens", true), title: "" });
  for (const f of files) {
    const it = { file: f, pdf: isPdf(f), name: stem(f.name), thumb: isPdf(f) ? "" : URL.createObjectURL(f), pages: isPdf(f) ? 0 : 1, key: Math.random().toString(36).slice(2) };
    IMP.items.push(it);
    if (it.pdf) pdfInfo(f).then((r) => { Object.assign(it, r); const el = $(`.imp-card[data-k="${it.key}"]`); if (el) el.outerHTML = impCard(it, IMP.items.indexOf(it), false); });
  }
  if (!IMP.open) buildImport(); else renderImportBody(true);
}

function impCard(it, i, deal = true) {
  return `<div class="imp-card ${it.pdf ? "is-pdf" : "is-photo"} ${deal ? "deal" : ""}" data-k="${it.key}" style="--i:${i};--r:${((i * 37) % 9) - 4}deg">
    <div class="imp-paper">${it.thumb ? `<img src="${it.thumb}" alt="">` : `<span class="imp-load"></span>`}
      <span class="imp-badge">${it.pdf ? `PDF${it.pages ? ` · ${it.pages} pp` : ""}` : `${icon("image")} Photo`}</span>
      <button class="imp-x" data-rm="${it.key}" title="Remove">${icon("x")}</button></div>
    <input class="imp-name" data-name="${it.key}" value="${esc(it.name)}" spellcheck="false" ${!it.pdf && IMP.combine && IMP.items.filter((x) => !x.pdf).length > 1 ? "disabled title=\"Named below: these photos become one PDF\"" : ""}>
  </div>`;
}

function buildImport() {
  IMP.open = true;
  const wrap = document.createElement("div");
  wrap.className = "imp-wrap"; wrap.id = "import";
  wrap.innerHTML = `<div class="imp" role="dialog" aria-label="Import">
    <header class="imp-head">
      <div><div class="imp-eyebrow" id="imp-count"></div><h2>File <em>these</em> away.</h2></div>
      <button class="icon-btn" data-imp-close title="Cancel (Esc)">${icon("x")}</button>
    </header>
    <div class="imp-desk" id="imp-desk"></div>
    <div class="imp-opts">
      <section><div class="dc-label">Drawer</div>${cabinetHTML(IMP.drawer, "imp-cab")}</section>
      <section class="imp-row">
        <div class="imp-tagbox"><div class="dc-label">Tags</div><div class="tag-edit" id="imp-tags"><input id="imp-tag-in" placeholder="Add tags, press Enter" list="tag-list-imp"></div>
          <datalist id="tag-list-imp">${S.tags.map((t) => `<option value="${esc(t.name)}">`).join("")}</datalist></div>
        <button class="imp-star" id="imp-star" type="button">${icon("star")}<span>Star</span></button>
      </section>
      <section class="imp-photos" id="imp-photos"></section>
    </div>
    <footer class="imp-foot">
      <span class="imp-hint">Esc to cancel · Ctrl+V adds more</span>
      <button class="btn" data-imp-close>Cancel</button>
      <button class="btn primary imp-go" id="imp-go"></button>
    </footer>
  </div>`;
  document.body.append(wrap);
  void wrap.offsetWidth; wrap.classList.add("in");
  bindCabinet($("#imp-cab"), (n) => { IMP.drawer = n; renderImportFoot(); });
  wrap.addEventListener("click", (e) => {
    if (e.target === wrap || e.target.closest("[data-imp-close]")) return closeImport();
    const rm = e.target.closest("[data-rm]");
    if (rm && rm.closest(".imp-card")) {
      const k = rm.dataset.rm, card = rm.closest(".imp-card");
      card.classList.add("gone");
      setTimeout(() => { IMP.items = IMP.items.filter((x) => x.key !== k); IMP.items.length ? renderImportBody(false) : closeImport(); }, 220);
    }
  });
  wrap.addEventListener("input", (e) => {
    const k = e.target.dataset.name; if (k) { const it = IMP.items.find((x) => x.key === k); if (it) it.name = e.target.value; }
    if (e.target.id === "imp-title") IMP.title = e.target.value;
  });
  wrap.addEventListener("change", (e) => {
    if (e.target.id === "imp-combine") { IMP.combine = e.target.checked; renderImportBody(false); }
    if (e.target.id === "imp-lens") { IMP.lens = e.target.checked; store.set("lens", IMP.lens); }
  });
  $("#imp-star").onclick = (e) => { IMP.star = !IMP.star; const b = e.currentTarget; b.classList.toggle("on", IMP.star); if (IMP.star) { b.classList.remove("burst"); void b.offsetWidth; b.classList.add("burst"); } };
  const tin = $("#imp-tag-in");
  const drawTags = () => { $$("#imp-tags .tag").forEach((t) => t.remove()); tin.insertAdjacentHTML("beforebegin", IMP.tags.map((t) => `<span class="tag">${esc(t)}<button type="button" data-tag-rm="${esc(t)}">×</button></span>`).join("")); };
  tin.onkeydown = (e) => {
    if ((e.key === "Enter" || e.key === ",") && tin.value.trim()) { e.preventDefault(); const t = tin.value.trim().toLowerCase().replace(/[\s,]+/g, "-"); if (!IMP.tags.includes(t)) IMP.tags.push(t); tin.value = ""; drawTags(); }
    if (e.key === "Backspace" && !tin.value && IMP.tags.length) { IMP.tags.pop(); drawTags(); }
  };
  $("#imp-tags").onclick = (e) => { const b = e.target.closest("[data-tag-rm]"); if (b) { IMP.tags = IMP.tags.filter((t) => t !== b.dataset.tagRm); drawTags(); } else tin.focus(); };
  $("#imp-go").onclick = submitImport;
  renderImportBody(true);
}

function renderImportBody(deal) {
  const desk = $("#imp-desk"); if (!desk) return;
  const known = new Set($$(".imp-card", desk).map((c) => c.dataset.k));
  desk.innerHTML = IMP.items.map((it, i) => impCard(it, i, deal && !known.has(it.key))).join("");
  const photos = IMP.items.filter((x) => !x.pdf);
  const pdfs = IMP.items.length - photos.length;
  $("#imp-count").textContent = `New arrivals · ${pdfs ? `${pdfs} PDF${pdfs > 1 ? "s" : ""}` : ""}${pdfs && photos.length ? " + " : ""}${photos.length ? `${photos.length} photo${photos.length > 1 ? "s" : ""}` : ""}`;
  const box = $("#imp-photos");
  box.hidden = !photos.length;
  if (photos.length) {
    if (!IMP.title) IMP.title = photos[0].name;
    box.innerHTML = `<div class="imp-ph-head">${icon("spark")}<div><b>Photos become real PDFs.</b><span>Your local model redraws each page as text and drawings. The photo itself is never stored.</span></div></div>
      <div class="imp-ph-opts">
        ${photos.length > 1 ? `<label class="imp-switch"><input type="checkbox" id="imp-combine" ${IMP.combine ? "checked" : ""}><i></i>Combine ${photos.length} photos into one PDF</label>` : ""}
        <label class="imp-switch"><input type="checkbox" id="imp-lens" ${IMP.lens ? "checked" : ""}><i></i>Text Lens</label>
      </div>
      ${photos.length > 1 && IMP.combine ? `<input class="imp-title" id="imp-title" value="${esc(IMP.title)}" placeholder="Name for the combined PDF">` : ""}`;
  }
  renderImportFoot();
}
function renderImportFoot() {
  const photos = IMP.items.filter((x) => !x.pdf).length, pdfs = IMP.items.length - photos;
  const docs = pdfs + (photos ? (IMP.combine ? 1 : photos) : 0);
  const btn = $("#imp-go"); if (!btn) return;
  btn.innerHTML = `File ${docs} ${docs === 1 ? "document" : "documents"} into <b>${esc(IMP.drawer)}</b> ${icon("back")}`;
}
function closeImport() {
  const w = $("#import"); if (!w) return;
  IMP.open = false; w.classList.remove("in"); w.classList.add("out");
  IMP.items.forEach((x) => !x.pdf && x.thumb && setTimeout(() => URL.revokeObjectURL(x.thumb), 1000));
  setTimeout(() => w.remove(), 260);
}

async function submitImport() {
  const go = $("#imp-go"); go.disabled = true;
  const pdfs = IMP.items.filter((x) => x.pdf), photos = IMP.items.filter((x) => !x.pdf);
  const tags = IMP.tags.join(","), star = IMP.star ? "1" : "", drawer = IMP.drawer;
  // the cards fly into their drawer in the sidebar
  const target = $(`#nav-drawers [data-drawer="${CSS.escape(drawer)}"]`)?.getBoundingClientRect();
  $$(".imp-card").forEach((c, i) => {
    const r = c.getBoundingClientRect();
    const tx = target ? target.left + 30 - (r.left + r.width / 2) : 0, ty = target ? target.top + target.height / 2 - (r.top + r.height / 2) : innerHeight;
    c.style.setProperty("--tx", tx + "px"); c.style.setProperty("--ty", ty + "px"); c.style.setProperty("--d", i * 60 + "ms");
    c.classList.add("fly");
  });
  $("#import").classList.add("filing");
  setTimeout(() => { if (target) { const row = $(`#nav-drawers [data-drawer="${CSS.escape(drawer)}"]`); row?.classList.add("gulp"); setTimeout(() => row?.classList.remove("gulp"), 600); } }, 520);
  try {
    if (pdfs.length) {
      const fd = new FormData();
      pdfs.forEach((x) => fd.append("files", x.file, x.file.name));
      fd.append("category", drawer); fd.append("titles", JSON.stringify(pdfs.map((x) => x.name.trim())));
      fd.append("tags", tags); fd.append("star", star);
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      if (!r.ok) throw new Error("Upload failed");
    }
    const send = async (group, title) => {
      const fd = new FormData();
      group.forEach((x) => fd.append("files", x.file, x.file.name));
      Object.entries({ category: drawer, lens: IMP.lens ? "1" : "0", title, tags, star }).forEach(([k, v]) => fd.append(k, v));
      const r = await fetch("/api/convert", { method: "POST", body: fd });
      if (!r.ok) { let m = "Couldn't start the conversion"; try { m = (await r.json()).detail; } catch {} throw new Error(m); }
    };
    if (photos.length) {
      if (IMP.combine || photos.length === 1) await send(photos, (photos.length > 1 ? IMP.title : photos[0].name).trim());
      else for (const p of photos) await send([p], p.name.trim());
    }
    setTimeout(closeImport, 700);
    const parts = [];
    if (pdfs.length) parts.push(`${plural(pdfs.length, "PDF")} filed`);
    if (photos.length) parts.push(`${plural(photos.length, "photo")} being rebuilt`);
    toast(`${parts.join(" · ")} in <b>${esc(drawer)}</b>`, 3200, photos.length ? { label: "Watch", fn: () => window.Shelfie.toggleAssistant(true) } : null);
    refresh();
  } catch (e) {
    $("#import")?.classList.remove("filing"); $$(".imp-card").forEach((c) => c.classList.remove("fly")); go.disabled = false;
    toast(esc(e.message), 5000);
  }
}

// paste a PDF or photos anywhere outside a text field → Import sheet (the chat box handles its own pastes)
let lastImportPaste = 0;
document.addEventListener("paste", async (e) => {
  if (e.target.closest?.("input, textarea, [contenteditable], #assistant")) return;
  if (!$("#modal").hidden) return;
  const files = clip.fromEvent(e.clipboardData);
  if (files.length) { e.preventDefault(); lastImportPaste = Date.now(); openImport(files); return; }
  if (clip.kind(e.clipboardData) === "text") return;
  e.preventDefault(); lastImportPaste = Date.now();
  const native = await clip.native();
  if (native.length) openImport(native);
  else if (window.pywebview?.api) toast("No PDF or image found on the clipboard");
});
// WebKitGTK may not fire "paste" when nothing is focused: read the system clipboard ourselves
document.addEventListener("keydown", async (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "v" || e.shiftKey || e.altKey) return;
  if (e.target.closest?.("input, textarea, [contenteditable], #assistant") || !$("#modal").hidden) return;
  if (!window.pywebview?.api?.clipboard_files) return;
  await new Promise((r) => setTimeout(r, 250));
  if (Date.now() - lastImportPaste < 800) return;
  const native = await clip.native();
  if (native.length && Date.now() - lastImportPaste > 800) { lastImportPaste = Date.now(); openImport(native); }
});

// ---------- pair iPhone ----------
$("#btn-pair").onclick = async () => {
  const p = await api("/api/pairing");
  if (!p.links.length) return modal(`<h2>No network found</h2><p>Connect this computer to Wi-Fi, then try again.</p><div class="modal-actions"><button class="btn" data-close>OK</button></div>`);
  let cur = 0;
  const draw = () => {
    const l = p.links[cur];
    modal(`<h2>Shelfie on your iPhone</h2><p class="lede">Your library stays on this computer; the iPhone opens it over your network.</p>
      ${p.links.length > 1 ? `<div class="pair-tabs">${p.links.map((x, i) => `<button class="d-drawer ${i === cur ? "on" : ""}" style="--c:var(--ink)" data-li="${i}">${x.tailscale ? "Tailscale (anywhere)" : "Home Wi-Fi"} · ${esc(x.address)}</button>`).join("")}</div>` : ""}
      <div class="pair-grid"><div class="pair-qr">${l.qr}</div>
      <ol class="steps">
        <li><span>Put the iPhone on the <b>same Wi-Fi</b> as this computer${l.tailscale ? " (or turn on Tailscale on both)" : ""}.</span></li>
        <li><span>Open the <b>Camera</b>, point it at the code, tap the link. It opens in Safari.</span></li>
        <li><span>Tap <b>Share</b> → <b>Add to Home Screen</b> → <b>Add</b>. Shelfie now has its own icon and opens full screen.</span></li>
      </ol></div>
      <div class="pair-url">${esc(l.url)}</div>
      <div class="modal-actions"><button class="btn" id="pair-reset" title="Signs out every paired phone">Unpair all phones</button><button class="btn primary" data-close>Done</button></div>`);
    $$("[data-li]").forEach((b) => (b.onclick = () => { cur = +b.dataset.li; draw(); }));
    $("#pair-reset").onclick = async () => { await api("/api/pairing/reset", { method: "POST" }); toast("All phones signed out. Scan the new code to pair again."); $("#btn-pair").click(); };
  };
  draw();
};

// ---------- theme ----------
const THEMES = ["auto", "light", "dark"];
function applyTheme(t) {
  if (t === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  $("#btn-theme").innerHTML = icon(t === "auto" ? "auto" : t === "light" ? "sun" : "moon");
  $("#btn-theme").title = `Theme: ${t}`;
}
let theme = store.get("theme", "auto"); applyTheme(theme);
$("#btn-theme").onclick = () => { theme = THEMES[(THEMES.indexOf(theme) + 1) % 3]; store.set("theme", theme); applyTheme(theme); };

// ---------- phone tab bar ----------
function syncTabbar() {
  const k = !$("#palette").hidden ? "search" : S.view.kind === "starred" ? "starred" : "library";
  $$("#tabbar [data-tab]").forEach((b) => b.classList.toggle("on", b.dataset.tab === k));
}
$("#tabbar").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tab]"); if (!b) return;
  const t = b.dataset.tab;
  if (t === "library") setView({ kind: "all" });
  if (t === "starred") setView({ kind: "starred" });
  if (t === "ask") window.Shelfie.toggleAssistant(true);
  if (t === "search") { openPalette(); syncTabbar(); }
  if (t === "add") pickFiles();
  if (t === "drawers") drawersSheet();
});
function drawersSheet() {
  modal(`<h2>Drawers</h2><p class="lede">${plural(S.stats.n || 0, "document")} across ${plural(S.cats.length, "drawer")}.</p>
    <div class="rail-section">${S.cats.map((c) => `
      <div class="nav-item drawer-item" style="--c:${c.color};grid-template-columns:22px 1fr auto auto" data-go="${esc(c.name)}">
        <span class="spine"></span><span class="label">${esc(c.name)}</span><span class="count">${c.count}</span>
        ${c.name !== "Inbox" ? `<button class="icon-btn sm" data-m="${esc(c.name)}">${icon("more")}</button>` : "<span></span>"}
      </div>`).join("")}</div>
    <div class="modal-actions"><button class="btn" id="ds-new">${icon("plus")} New drawer</button><button class="btn primary" data-close>Done</button></div>`);
  $("#modal-body").onclick = (e) => {
    const m = e.target.closest("[data-m]"); if (m) { e.stopPropagation(); return drawerMenu(m.dataset.m, m); }
    const g = e.target.closest("[data-go]"); if (g) { closeModal(); setView({ kind: "drawer", value: g.dataset.go }); }
  };
  $("#ds-new").onclick = () => { closeModal(); newDrawerModal(); };
}

// ---------- modal / menu / toast ----------
function modal(html) { $("#modal-body").onclick = null; $("#modal-body").innerHTML = html; $("#modal").hidden = false; }
function closeModal() { $("#modal").hidden = true; $("#modal-body").innerHTML = ""; }
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal" || e.target.closest("[data-close]")) closeModal(); });

function menu(anchor, items) {
  const m = $("#menu");
  m.innerHTML = items.map((x, i) => x === "-" ? "<hr>" : `<button data-mi="${i}" class="${x.danger ? "danger" : ""}">${icon(x.i)}${esc(x.t)}</button>`).join("");
  m.hidden = false;
  const r = anchor.getBoundingClientRect(); const mw = m.offsetWidth, mh = m.offsetHeight;
  m.style.left = Math.min(r.left, innerWidth - mw - 8) + "px";
  m.style.top = (r.bottom + mh + 8 > innerHeight ? Math.max(8, r.top - mh - 4) : r.bottom + 4) + "px";
  m.onclick = (e) => { const b = e.target.closest("[data-mi]"); if (!b) return; m.hidden = true; items[+b.dataset.mi].fn(); };
}
document.addEventListener("mousedown", (e) => { if (!e.target.closest("#menu")) $("#menu").hidden = true; });

function toast(html, ms = 2600, action = null) {
  const t = document.createElement("div"); t.className = "toast"; t.innerHTML = html;
  if (action) { const b = document.createElement("button"); b.textContent = action.label; b.onclick = () => { action.fn(); t.remove(); }; t.append(b); }
  $("#toasts").append(t);
  if (ms) setTimeout(() => t.remove(), ms);
  return t;
}

// ---------- keyboard ----------
document.addEventListener("keydown", (e) => {
  const typing = e.target.matches("input, textarea, select");
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "j") { e.preventDefault(); window.Shelfie.toggleAssistant(); return; }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#palette").hidden ? openPalette() : closePalette(); return; }
  if (e.key === "Escape") {
    if (!$("#menu").hidden) return ($("#menu").hidden = true);
    if (IMP.open) return closeImport();
    if (!$("#modal").hidden) return closeModal();
    if (!$("#palette").hidden) return closePalette();
    if (!$("#viewer").hidden) return closeViewer();
    if (S.selected) return closeDetail();
  }
  if (typing) return;
  if (!$("#viewer").hidden) {
    if (e.key === "+" || e.key === "=") zoomBy(1.2);
    if (e.key === "-") zoomBy(1 / 1.2);
    return;
  }
  if (e.key === "/") { e.preventDefault(); openPalette(); }
  if ((e.key === "Delete") && S.selected) trashDoc(S.selected);
});

// ---------- live updates (files added on disk or from the other device) ----------
async function poll() {
  try {
    const v = await api("/api/version");
    if (v.version !== S.version) { S.version = v.version; await refresh(); }
  } catch {}
  setTimeout(poll, document.hidden ? 15000 : 3000);
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });

// ---------- bridge for assistant.js ----------
window.Shelfie = {
  S, api, icon, esc, catColor, fmtSize, plural, isPhone, store, toast, refresh, select,
  clip, openImport, openViewer, setView, get viewerDoc() { return $("#viewer").hidden ? null : V.doc; },
  toggleAssistant: () => {},
};

// ---------- boot ----------
hydrateIcons();
if (S.layout !== "grid" && S.layout !== "list") S.layout = "grid";
refresh().then(() => { syncTabbar(); setTimeout(poll, 3000); });
