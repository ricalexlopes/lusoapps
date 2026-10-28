// GET /heatline/api/meet?id=10989&lic=219009,216993  ->  the meet, its programme, and for each chosen
// swimmer their entries and results. Other swimmers' data are never sent.
import ENTRIES from "../_data/entries.js";
import { loadResults, parseMeet, resultsOf, secs } from "../_lib/lenex.js";

export async function onRequestGet({ request }) {
  const u = new URL(request.url);
  const id = u.searchParams.get("id") || "";
  const lics = (u.searchParams.get("lic") || "").split(",").filter(x => /^[\w-]{1,20}$/.test(x)).slice(0, 30);
  if (!/^\d{1,7}$/.test(id)) return json({ error: "bad meet" }, 400);
  const E = ENTRIES[id];
  let P = null, err = "";
  try { const xml = await loadResults(id); if (xml) P = parseMeet(xml); } catch (e) { err = String(e.message || e); }

  const events = {};
  (E ? E.events : []).forEach(e => { events[e.n] = { n: e.n, g: e.g, d: e.d, rc: e.rc, s: e.s, date: e.date, time: e.time }; });
  if (P) Object.values(P.events).forEach(e => { events[e.n] = Object.assign(events[e.n] || {}, e); });

  const swimmers = {};
  for (const lic of lics) {
    const ea = E && E.athletes.find(a => a.lic === lic);
    const pa = P && P.athletes[lic];
    if (!ea && !pa) { swimmers[lic] = { found: false }; continue; }
    swimmers[lic] = {
      found: true,
      name: ea ? ea.first + " " + ea.last : (pa.first + " " + pa.last),
      year: (ea && ea.year) || (pa && pa.year) || null,
      club: (ea && ea.club) || (pa && pa.club) || "",
      entries: ea ? ea.ev.map(x => ({ n: x.n, et: secs(x.et), ep: x.ep, x: x.x })) : [],
      results: pa ? resultsOf(P, lic) : [],
    };
  }
  const meet = P ? P.meet : Object.assign({ name: "", city: "", pool: "", status: "" }, E && E.info);
  if (P) meet.date = Object.values(P.events).map(e => e.date).filter(Boolean).sort()[0] || (E && E.info && E.info.date) || "";
  return json({ id, available: !!P, error: err, fetchedAt: new Date().toISOString(), meet, events, swimmers });
}

function json(o, status = 200) {
  return new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex" } });
}
