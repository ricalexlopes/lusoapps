// GET /heatline/api/search?meet=10989&q=ric  ->  up to 12 swimmers whose name matches, from the entry list
// and, once the meet has started, from the results file. Name, birth year and club only.
import ENTRIES from "../_data/entries.js";
import { loadResults, parseMeet, norm } from "../_lib/lenex.js";

export async function onRequestGet({ request }) {
  const u = new URL(request.url);
  const id = u.searchParams.get("meet") || "", q = norm(u.searchParams.get("q"));
  if (!/^\d{1,7}$/.test(id)) return json({ error: "bad meet" }, 400);
  if (q.length < 3) return json({ swimmers: [] });
  const words = q.split(" ");
  const found = new Map();
  const add = (a) => {
    const full = norm(a.first + " " + a.last);
    if (words.every(w => full.split(" ").some(p => p.startsWith(w))) && !found.has(a.lic))
      found.set(a.lic, { lic: a.lic, name: (a.first + " " + a.last).trim(), year: a.year || null, club: a.club || "", g: a.g || "", grp: a.grp || "" });
  };
  const E = ENTRIES[id];
  if (E) E.athletes.forEach(add);
  try {
    const xml = await loadResults(id);
    if (xml) Object.values(parseMeet(xml).athletes).forEach(a => add({ ...a, last: titleCase(a.last) }));
  } catch (e) {}
  const list = [...found.values()].sort((a, b) => a.name.localeCompare(b.name)).slice(0, 12);
  return json({ swimmers: list });
}

function titleCase(s) { return s && s === s.toUpperCase() ? s.toLowerCase().replace(/(^|[\s-])\p{L}/gu, m => m.toUpperCase()) : s; }
function json(o, status = 200) {
  return new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex" } });
}
