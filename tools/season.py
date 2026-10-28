#!/usr/bin/env python3
"""Heatline season data: the meets of each nation on live.swimrankings.net, and which meets each
licensed swimmer swam in (license -> meet ids). No names or times are stored here; the app reads
the results of the chosen swimmer from the meet itself.

Run daily by .github/workflows/heatline-season.yml. Usage: python3 tools/season.py [NATION ...]
"""
import html, io, json, os, re, subprocess, sys, tempfile, urllib.request, zipfile
from datetime import date

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "heatline", "data")
UA = {"User-Agent": "Heatline/1.0 (+https://lusoapps.com/heatline/)"}
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
SEASON_START = "2026-09-01"


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def dates(txt):
    """'7 - 8 Nov 2026', '30 Oct - 1 Nov 2026', '31 Oct 2026', '30 Dec 2026 - 2 Jan 2027' -> (from, to)"""
    t = re.sub(r"\s+", " ", txt).strip()
    m = re.match(r"(\d+)(?: (\w{3}))?(?: (\d{4}))?(?: - (\d+)(?: (\w{3}))?)? (\d{4})?$", t) or re.match(r"(\d+) (\w{3}) (\d{4})$", t)
    parts = re.findall(r"(\d+)(?: (\w{3}))?(?: (\d{4}))?", t)
    # parts like [('7','',''), ('8','Nov','2026')] or [('30','Oct',''),('1','Nov','2026')]
    end = parts[-1]
    y2, m2, d2 = int(end[2]), MON[end[1]], int(end[0])
    st = parts[0]
    m1 = MON[st[1]] if st[1] else m2
    y1 = int(st[2]) if st[2] else (y2 - 1 if m1 > m2 else y2)
    return f"{y1:04d}-{m1:02d}-{int(st[0]):02d}", f"{y2:04d}-{m2:02d}-{d2:02d}"


def meets_of(nation):
    s = get(f"https://live.swimrankings.net/?nation={nation}").decode("utf-8", "replace")
    out = []
    for cls, row in re.findall(r'<tr class="(upcoming|live|finished|running|current)">(.*?)</tr>', s, re.S):
        mid = re.search(r'href="/(\d+)/"', row)
        name = re.search(r'<span class="name">(.*?)</span>', row, re.S)
        dl = re.search(r'<span class="dateLong">(.*?)</span>', row, re.S)
        city = re.search(r'<td class="tdCity">.*?</span>(.*?)<span class="nation">', row, re.S)
        course = re.search(r'<span class="course">(.*?)</span>', row)
        if not (mid and name and dl):
            continue
        f, t = dates(html.unescape(re.sub("<[^>]+>", "", dl.group(1))))
        out.append({"id": mid.group(1), "name": html.unescape(name.group(1)).strip(), "city": html.unescape(city.group(1)).strip() if city else "",
                    "course": course.group(1) if course else "", "from": f, "to": t, "status": cls})
    return out


def licenses_in(meet_id):
    try:
        raw = get(f"https://live.swimrankings.net/{meet_id}/results.lxf")
        z = zipfile.ZipFile(io.BytesIO(raw))
        xml = z.read(z.namelist()[0]).decode("utf-8", "replace")
    except Exception:
        return None
    return sorted(set(re.findall(r'<ATHLETE [^>]*?license="([^"]+)"', xml)))


# --- entry lists (EntryList_N.pdf, Splash Meet Manager) -----------------------------------
STK = {"livres": "FREE", "freestyle": "FREE", "libre": "FREE", "costas": "BACK", "backstroke": "BACK", "espalda": "BACK",
       "bruços": "BREAST", "brucos": "BREAST", "breaststroke": "BREAST", "braza": "BREAST", "mariposa": "FLY", "butterfly": "FLY",
       "estilos": "MEDLEY", "medley": "MEDLEY"}
HEAD = re.compile(r"(?:Prova|Event|Prueba|Evento)\s+(\d+)\s+(Femin\w*\.?|Masc\w*\.?|Misto|Mixto|Mixed|Women|Men|Girls|Boys|Mujeres|Hombres)[^,]*,\s*(\d+)\s*(?:x\s*(\d+))?\s*m\s+(\S+)", re.I)
ROW = re.compile(r"^\s*(\d+)\s+(.+?,\s*[^\d]+?)\s*(\d{2})\s+(\d{1,2}\s*-\s*\d{1,2}|\d{1,2}\s*\+|[A-Z]{2,4}(?: [A-Z])?|Open|ABS)\s*(\d{4,8})\s+(.+?)\s*(\d{0,2}:?\d{1,2}\.\d{2}|NT)?\s*(EXH)?\s*(25m|50m)?\s*$")


def pdf_text(raw):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(raw); f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout


def entries_of(meet_id):
    page = get(f"https://live.swimrankings.net/{meet_id}/").decode("utf-8", "replace")
    files = sorted(set(re.findall(r'href="(EntryList_\d+\.pdf)"', page)), key=lambda x: int(re.findall(r"\d+", x)[0]))
    if not files:
        return None
    ath, events = {}, []
    for fn in files:
        try:
            t = pdf_text(get(f"https://live.swimrankings.net/{meet_id}/{fn}"))
        except Exception:
            continue
        h = HEAD.search(t)
        if not h:
            continue
        num = int(h.group(1)); gw = h.group(2).lower()
        g = "F" if gw[0] in "fwgm" and not gw.startswith(("masc", "men", "mix", "mis")) else "M" if gw.startswith(("masc", "men", "boys", "hom")) else "X"
        if gw.startswith(("muj", "wom", "girl", "fem")): g = "F"
        relay = h.group(4) is not None
        dist = int(h.group(4)) if relay else int(h.group(3)); cnt = int(h.group(3)) if relay else 1
        st = STK.get(h.group(5).lower().strip(".,"), h.group(5))
        tm = re.search(r"(\d{2})/(\d{2})/(\d{4})(?:\s*-\s*(\d{1,2}:\d{2}))?", t)
        ev = {"n": num, "g": g, "d": dist, "rc": cnt, "s": st, "date": f"{tm.group(3)}-{tm.group(2)}-{tm.group(1)}" if tm else "", "time": (tm.group(4) or "") if tm else ""}
        events.append(ev)
        if relay:
            continue
        for line in t.splitlines():
            m = ROW.match(line)
            if not m:
                continue
            name, yy, grp, lic, club, et, exh, pool = m.group(2), int(m.group(3)), re.sub(r"\s+", " ", m.group(4)), m.group(5), m.group(6).strip(), m.group(7), m.group(8), m.group(9)
            first, last = [x.strip() for x in name.split(",", 1)]
            a = ath.setdefault(lic, {"lic": lic, "first": first, "last": last.title(), "year": (1900 if yy > 40 else 2000) + yy, "g": g, "grp": grp, "club": club, "ev": []})
            if not any(e["n"] == num for e in a["ev"]):
                a["ev"].append({"n": num, "et": None if et in (None, "NT") else et, "ep": pool, "x": 1 if exh else 0})
    if not ath:
        return None
    return {"meet": meet_id, "events": sorted(events, key=lambda e: e["n"]), "athletes": list(ath.values())}


def run(nation):
    path = os.path.join(ROOT, f"{nation}.json")
    old = json.load(open(path)) if os.path.exists(path) else {"nation": nation, "meets": [], "idx": {}, "done": []}
    meets = {m["id"]: m for m in old["meets"]}
    for m in meets_of(nation):
        meets[m["id"]] = m
    today = date.today().isoformat()
    done = set(old.get("done", []))
    idx = {k: set(v) for k, v in old.get("idx", {}).items()}
    for m in sorted(meets.values(), key=lambda x: x["from"]):
        if m["to"] < SEASON_START or m["id"] in done:
            continue
        finished = m["status"] == "finished" or m["to"] < today
        if not finished and m["from"] > today:
            continue
        lic = licenses_in(m["id"])
        if lic is None:
            continue
        for l in lic:
            idx.setdefault(l, set()).add(m["id"])
        if finished:
            done.add(m["id"])
    # entry lists of the meets of the next 3 weeks (they change until the meet starts)
    edir = os.path.join(ROOT, "entries"); os.makedirs(edir, exist_ok=True)
    soon = (date.fromordinal(date.today().toordinal() + 21)).isoformat()
    eidx = {}
    for m in meets.values():
        if m["to"] < today or m["from"] > soon:
            continue
        try:
            E = entries_of(m["id"])
        except Exception as e:
            print("entries failed", m["id"], e); E = None
        if not E:
            continue
        E["info"] = {"name": m["name"], "city": m["city"], "date": m["from"], "to": m["to"]}
        json.dump(E, open(os.path.join(edir, m["id"] + ".json"), "w"), ensure_ascii=False, separators=(",", ":"))
        for a in E["athletes"]:
            eidx.setdefault(a["lic"], []).append(m["id"])
    for f in os.listdir(edir):  # drop entry lists of past meets
        mid = f.split(".")[0]
        if mid in meets and meets[mid]["to"] < today:
            os.remove(os.path.join(edir, f))
    keep = sorted((m for m in meets.values() if m["to"] >= SEASON_START), key=lambda x: (x["from"], x["id"]))
    data = {"nation": nation, "updated": today, "meets": keep, "idx": {k: sorted(v, key=int) for k, v in sorted(idx.items())}, "done": sorted(done, key=int), "eidx": {k: sorted(v, key=int) for k, v in sorted(eidx.items())}}
    os.makedirs(ROOT, exist_ok=True)
    json.dump(data, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    print(nation, len(keep), "meets,", len(done), "indexed,", len(idx), "swimmers")


if __name__ == "__main__":
    for n in (sys.argv[1:] or ["POR"]):
        run(n)
