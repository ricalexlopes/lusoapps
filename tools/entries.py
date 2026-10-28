# Build the entries file of a live.swimrankings.net meet from its EntryList_N.pdf files.
# usage: python3 entries.py MEETID PDFDIR OUT.json
import json, re, subprocess, sys, glob, os
meet, d, out = sys.argv[1], sys.argv[2], sys.argv[3]
STROKE = {"Livres": "FREE", "Costas": "BACK", "Bruços": "BREAST", "Mariposa": "FLY", "Estilos": "MEDLEY"}
row = re.compile(r"^\s*(\d+)\s+(.+?,\s*[^\d]+?)\s*(\d{2})\s+([A-Z]{3}(?: [A-Z])?)\s+(\d{3,7})?\s*(.+?)\s*(\d{0,2}:?\d{1,2}\.\d{2}|NT)?\s*(EXH)?\s*(25m|50m)?\s*$")
ath, events = {}, []
for f in sorted(glob.glob(os.path.join(d, "e*.pdf")), key=lambda x: int(re.findall(r"\d+", os.path.basename(x))[0])):
    t = subprocess.run(["pdftotext", "-layout", f, "-"], capture_output=True, text=True).stdout
    h = re.search(r"Prova\s+(\d+)\s+(Femin\.|Masc\.|Misto)[^,]*,\s*(\d+)\s*x?\s*(\d+)?m\s+(\S+)", t)
    if not h: print("no header", f); continue
    num = int(h.group(1)); g = "F" if h.group(2).startswith("F") else "M" if h.group(2).startswith("M") else "X"
    relay = h.group(4) is not None
    dist = int(h.group(4) if relay else h.group(3)); cnt = int(h.group(3)) if relay else 1
    tm = re.search(r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{1,2}:\d{2})", t)
    ev = {"n": num, "g": g, "d": dist, "rc": cnt, "s": STROKE.get(h.group(5), h.group(5)), "date": f"{tm.group(3)}-{tm.group(2)}-{tm.group(1)}", "time": tm.group(4)}
    events.append(ev)
    if relay: continue
    for line in t.splitlines():
        m = row.match(line)
        if not m: continue
        name, yy, grp, lic, club, et, exh, pool = m.group(2), int(m.group(3)), m.group(4), m.group(5), m.group(6).strip(), m.group(7), m.group(8), m.group(9)
        if not lic: continue
        first, last = [x.strip() for x in name.split(",", 1)]
        a = ath.setdefault(lic, {"lic": lic, "first": first, "last": last.title(), "year": (1900 if yy > 40 else 2000) + yy, "g": g, "grp": grp, "club": club, "ev": []})
        a["ev"].append({"n": num, "et": None if et in (None, "NT") else et, "ep": pool, "x": 1 if exh else 0})
json.dump({"meet": meet, "events": events, "athletes": list(ath.values())}, open(out, "w"), ensure_ascii=False, separators=(",", ":"))
print(len(events), "events,", len(ath), "athletes,", sum(len(a["ev"]) for a in ath.values()), "entries")
