// Read a LENEX results file (.lxf = zip with one XML file) from live.swimrankings.net.
// Only the swimmers asked for are returned; nobody else's results leave the server.

// --- zip -------------------------------------------------------------------
async function inflateRaw(bytes) {
  const ds = new DecompressionStream("deflate-raw");
  const out = new Response(new Blob([bytes]).stream().pipeThrough(ds));
  return new Uint8Array(await out.arrayBuffer());
}

export async function unzipFirst(buf) {
  const u8 = new Uint8Array(buf);
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  let eocd = -1;
  for (let i = u8.length - 22; i >= Math.max(0, u8.length - 66000); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a zip file");
  const cd = dv.getUint32(eocd + 16, true);
  if (dv.getUint32(cd, true) !== 0x02014b50) throw new Error("bad zip directory");
  const method = dv.getUint16(cd + 10, true);
  const csize = dv.getUint32(cd + 20, true);
  const local = dv.getUint32(cd + 42, true);
  const nlen = dv.getUint16(local + 26, true), xlen = dv.getUint16(local + 28, true);
  const start = local + 30 + nlen + xlen;
  const data = u8.subarray(start, start + csize);
  const raw = method === 0 ? data : await inflateRaw(data);
  return new TextDecoder("utf-8").decode(raw);
}

// Fetch and unzip a meet's results file. null when there are no results yet.
export async function loadResults(id) {
  const r = await fetch(`https://live.swimrankings.net/${id}/results.lxf`, {
    cf: { cacheTtl: 45, cacheEverything: true },
    headers: { "User-Agent": "Heatline/1.0 (+https://lusoapps.com/heatline/)" },
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`swimrankings ${r.status}`);
  const buf = await r.arrayBuffer();
  if (buf.byteLength < 100) return null;
  try { return await unzipFirst(buf); } catch (e) { return null; }
}

// --- tiny XML helpers ------------------------------------------------------
function attrs(tag) {
  const o = {};
  for (const m of tag.matchAll(/([\w.]+)="([^"]*)"/g)) o[m[1]] = m[2]
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
  return o;
}
export function secs(t) { // "00:01:15.04" or "1:15.04" or "31.25" -> seconds
  if (!t) return null;
  const p = t.split(":").map(parseFloat);
  let v = 0; for (const x of p) v = v * 60 + x;
  return v > 0 ? Math.round(v * 100) / 100 : null;
}
function splitsOf(block) {
  return [...block.matchAll(/<SPLIT [^>]*>/g)].map(m => attrs(m[0])).map(a => ({ d: +a.distance, t: secs(a.swimtime) }));
}

// --- main ------------------------------------------------------------------
export function parseMeet(xml) {
  const mt = attrs((xml.match(/<MEET [^>]*>/) || [""])[0]);
  const pool = mt.course === "LCM" ? "50m" : "25m";
  const meet = { name: mt.name || "", city: mt.city || "", nation: mt.nation || "", pool, status: mt.status || "" };

  const events = {}, heats = {};
  for (const s of xml.matchAll(/<SESSION ([^>]*)>([\s\S]*?)<\/SESSION>/g)) {
    const date = attrs(s[1]).date;
    for (const e of s[2].matchAll(/<EVENT ([^>]*)>([\s\S]*?)<\/EVENT>/g)) {
      const ea = attrs(e[1]);
      const st = attrs((e[2].match(/<SWIMSTYLE [^>]*>/) || [""])[0]);
      events[ea.eventid] = {
        n: +ea.number, g: ea.gender || "", d: +st.distance, rc: +st.relaycount || 1, s: st.stroke || "",
        date, time: (ea.daytime || "").slice(0, 5), done: ea.status === "OFFICIAL" || ea.status === "FINISHED",
      };
      for (const h of e[2].matchAll(/<HEAT [^>]*>/g)) { const ha = attrs(h[0]); heats[ha.heatid] = +ha.number; }
    }
  }
  const place = {};
  for (const r of xml.matchAll(/<RANKING [^>]*>/g)) { const a = attrs(r[0]); if (+a.place > 0) place[a.resultid] = +a.place; }

  // athletes and relays, club by club
  const athletes = {}, relays = [];
  for (const c of xml.matchAll(/<CLUB ([^>]*)>([\s\S]*?)<\/CLUB>/g)) {
    const club = attrs(c[1]).name || attrs(c[1]).shortname || "";
    for (const am of c[2].matchAll(/<ATHLETE ([^>]*)>([\s\S]*?)<\/ATHLETE>/g)) {
      const a = attrs(am[1]);
      const key = a.license || "id" + a.athleteid;
      athletes[key] = { lic: key, aid: a.athleteid, first: a.firstname || "", last: a.lastname || "", year: +(a.birthdate || "").slice(0, 4) || null, g: a.gender || "", club, body: am[2] };
    }
    for (const rl of c[2].matchAll(/<RELAY ([^>]*)>([\s\S]*?)<\/RELAY>/g)) relays.push({ team: attrs(rl[1]).name || club, body: rl[2] });
  }
  return { meet, events, heats, place, athletes, relays };
}

// The results of one swimmer (individual and relay legs).
export function resultsOf(P, lic) {
  const ath = P.athletes[lic];
  if (!ath) return [];
  const out = [];
  for (const r of ath.body.matchAll(/<RESULT ([^>]*?)(?:\/>|>([\s\S]*?)<\/RESULT>)/g)) {
    const a = attrs(r[1]); const ev = P.events[a.eventid]; if (!ev) continue;
    out.push({
      n: ev.n, relay: false, time: a.status ? null : secs(a.swimtime), st: a.status || "",
      place: P.place[a.resultid] || null, pts: a.points ? +a.points : null,
      heat: P.heats[a.heatid] || null, lane: a.lane ? +a.lane : null,
      et: secs(a.entrytime), ep: a.entrycourse === "LCM" ? "50m" : a.entrycourse === "SCM" ? "25m" : null,
      splits: splitsOf(r[2] || ""),
    });
  }
  for (const rl of P.relays) {
    for (const r of rl.body.matchAll(/<RESULT ([^>]*?)>([\s\S]*?)<\/RESULT>/g)) {
      const pos = [...r[2].matchAll(/<RELAYPOSITION [^>]*>/g)].map(m => attrs(m[0])).find(p => p.athleteid === ath.aid);
      if (!pos) continue;
      const a = attrs(r[1]); const ev = P.events[a.eventid]; if (!ev) continue;
      const sp = splitsOf(r[2]); const k = +pos.number; const leg = ev.d;
      const at = d => d === 0 ? 0 : (sp.find(s => s.d === d) || {}).t;
      const end = k === ev.rc ? secs(a.swimtime) : at(k * leg);
      const st0 = at((k - 1) * leg);
      out.push({
        n: ev.n, relay: true, team: rl.team, leg: k, time: a.status ? null : secs(a.swimtime), st: a.status || "",
        legTime: !a.status && end != null && st0 != null ? Math.round((end - st0) * 100) / 100 : null,
        place: P.place[a.resultid] || null, heat: P.heats[a.heatid] || null, lane: a.lane ? +a.lane : null, splits: [],
      });
    }
  }
  return out.sort((x, y) => x.n - y.n);
}

// Accent- and case-insensitive text for name search.
export function norm(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim(); }
