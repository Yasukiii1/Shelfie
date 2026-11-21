// Shelfie tools for pi. These are the ONLY tools the assistant gets: pi runs with its built-in
// read/write/edit/bash tools disabled. Every call goes through Shelfie's own API, which only
// knows about the library folder, so the model can read and create in the library and nowhere
// else, and there is no delete tool at all.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const BASE = (process.env.SHELFIE_URL || "http://127.0.0.1:8642").replace(/\/$/, "");

async function call(path: string, init: RequestInit = {}): Promise<any> {
  const r = await fetch(BASE + path, {
    ...init,
    headers: { "content-type": "application/json", ...(init.headers || {}) },
  });
  const body = await r.text();
  if (!r.ok) {
    let msg = body;
    try { msg = JSON.parse(body).detail ?? body; } catch {}
    throw new Error(`Shelfie said: ${msg}`);
  }
  return body ? JSON.parse(body) : {};
}

const text = (t: string, details: Record<string, unknown> = {}) => ({ content: [{ type: "text" as const, text: t }], details });
const line = (d: any) =>
  `#${d.id} "${d.title}" — drawer: ${d.category}; ${d.pages || "?"} pages${d.tags?.length ? "; tags: " + d.tags.join(", ") : ""}${d.favorite ? "; starred" : ""}`;

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "shelfie_list",
    label: "List library",
    description: "List the drawers (categories) and the PDF documents in the Shelfie library. Optionally filter by drawer, tag or starred.",
    promptSnippet: "List drawers and documents in the library",
    parameters: Type.Object({
      drawer: Type.Optional(Type.String({ description: "Only documents in this drawer" })),
      tag: Type.Optional(Type.String({ description: "Only documents with this tag" })),
      starred: Type.Optional(Type.Boolean({ description: "Only starred documents" })),
    }),
    async execute(_id, p) {
      const st = await call("/api/state");
      const q = new URLSearchParams();
      if (p.drawer) q.set("category", p.drawer);
      if (p.tag) q.set("tag", p.tag);
      if (p.starred) q.set("starred", "true");
      const docs = await call("/api/docs?" + q);
      const drawers = st.categories.map((c: any) => `${c.name} (${c.count})`).join(", ");
      const list = docs.slice(0, 300).map(line).join("\n");
      return text(`Drawers: ${drawers}\n\n${docs.length} document(s):\n${list || "(none)"}${docs.length > 300 ? "\n…more not shown, filter by drawer" : ""}`,
        { count: docs.length });
    },
  });

  pi.registerTool({
    name: "shelfie_search",
    label: "Search library",
    description: "Full-text search across titles, tags and the text inside every PDF in the library. Returns matching documents with a snippet.",
    promptSnippet: "Search inside all PDFs in the library",
    parameters: Type.Object({
      query: Type.String({ description: "Words to search for" }),
      limit: Type.Optional(Type.Number({ description: "Max results (default 10)" })),
    }),
    async execute(_id, p) {
      const docs = await call("/api/docs?q=" + encodeURIComponent(p.query));
      const top = docs.slice(0, Math.max(1, Math.min(p.limit ?? 10, 30)));
      if (!top.length) return text(`No documents match "${p.query}".`, { ids: [] });
      const out = top.map((d: any) => {
        const s = (d.snippet || "").replace(/\u0002|\u0003/g, "").replace(/\s+/g, " ").trim();
        return `${line(d)}\n   …${s}…`;
      }).join("\n");
      return text(out, { ids: top.map((d: any) => d.id) });
    },
  });

  pi.registerTool({
    name: "shelfie_read",
    label: "Read PDF",
    description: "Read the text of one PDF in the library by its id. Read long documents in page ranges (about 10 pages at a time).",
    promptSnippet: "Read the text of a PDF by id, a page range at a time",
    promptGuidelines: [
      "Use shelfie_search or shelfie_list first to find a document id, then shelfie_read to read it.",
      "Call shelfie_read with from_page/to_page ranges for long PDFs instead of reading everything at once.",
    ],
    parameters: Type.Object({
      id: Type.Number({ description: "Document id" }),
      from_page: Type.Optional(Type.Number({ description: "First page (default 1)" })),
      to_page: Type.Optional(Type.Number({ description: "Last page (default from_page + 9)" })),
    }),
    async execute(_id, p) {
      const from = Math.max(1, p.from_page ?? 1);
      const to = Math.max(from, p.to_page ?? from + 9);
      const r = await call(`/api/docs/${p.id}/text?start=${from}&end=${to}`);
      const head = `"${r.title}" (#${r.id}, drawer ${r.category}) — pages ${r.start}–${r.end} of ${r.pages}${r.truncated ? " (text truncated; read a smaller range)" : ""}`;
      return text(`${head}\n\n${r.text || "(no extractable text on these pages — it may be a scanned image)"}`, { id: r.id, start: r.start, end: r.end });
    },
  });

  pi.registerTool({
    name: "shelfie_create_pdf",
    label: "Create PDF",
    description: "Create a NEW PDF document in the library from Markdown (# headings, - lists, paragraphs). Never overwrites an existing file. Use for summaries, notes, study sheets, comparisons.",
    promptSnippet: "Create a new PDF document in a drawer",
    parameters: Type.Object({
      title: Type.String({ description: "Document title (also the file name)" }),
      content: Type.String({ description: "Body in simple Markdown" }),
      drawer: Type.Optional(Type.String({ description: "Drawer to file it in (default Inbox). Created if missing." })),
    }),
    async execute(_id, p) {
      const d = await call("/api/agent/create", { method: "POST", body: JSON.stringify({ title: p.title, content: p.content, drawer: p.drawer || "Inbox" }) });
      return text(`Created ${line(d)}`, { id: d.id });
    },
  });

  pi.registerTool({
    name: "shelfie_create_drawer",
    label: "Create drawer",
    description: "Create a new drawer (category folder) in the library.",
    parameters: Type.Object({ name: Type.String({ description: "Drawer name" }) }),
    async execute(_id, p) {
      const r = await call("/api/categories", { method: "POST", body: JSON.stringify({ name: p.name }) });
      return text(`Drawer "${r.name}" is ready.`, {});
    },
  });

  pi.registerTool({
    name: "shelfie_organize",
    label: "Organize",
    description: "File a document into a drawer and/or add tags or a star. Cannot delete or rename anything.",
    parameters: Type.Object({
      id: Type.Number({ description: "Document id" }),
      drawer: Type.Optional(Type.String({ description: "Move into this drawer (created if missing)" })),
      add_tags: Type.Optional(Type.Array(Type.String(), { description: "Tags to add" })),
      star: Type.Optional(Type.Boolean({ description: "Star (true) or unstar (false)" })),
    }),
    async execute(_id, p) {
      const cur = await call(`/api/docs/${p.id}`);
      const patch: Record<string, unknown> = {};
      if (p.drawer) patch.category = p.drawer;
      if (p.add_tags?.length) patch.tags = [...cur.tags, ...p.add_tags];
      if (p.star !== undefined) patch.favorite = p.star;
      const d = await call(`/api/docs/${p.id}`, { method: "PATCH", body: JSON.stringify(patch) });
      return text(`Updated ${line(d)}`, { id: d.id });
    },
  });
}
