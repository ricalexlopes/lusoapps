#!/usr/bin/env python3
"""Heatline season data: the meets of each nation on live.swimrankings.net, and which meets each
licensed swimmer swam in (license -> meet ids). No names or times are stored here; the app reads
the results of the chosen swimmer from the meet itself.

Run daily by .github/workflows/heatline-season.yml. Usage: python3 tools/season.py [NATION ...]
"""
import html, io, json, os, re, sys, urllib.request, zipfile
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
    keep = sorted((m for m in meets.values() if m["to"] >= SEASON_START), key=lambda x: (x["from"], x["id"]))
    data = {"nation": nation, "updated": today, "meets": keep, "idx": {k: sorted(v, key=int) for k, v in sorted(idx.items())}, "done": sorted(done, key=int)}
    os.makedirs(ROOT, exist_ok=True)
    json.dump(data, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    print(nation, len(keep), "meets,", len(done), "indexed,", len(idx), "swimmers")


if __name__ == "__main__":
    for n in (sys.argv[1:] or ["POR"]):
        run(n)
