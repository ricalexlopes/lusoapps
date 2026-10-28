# Build heatline/data/min-POR.json from the TAC annex of the FPN 2026/2027 regulation (pdftotext -layout output).
import json, re, sys
txt = open(sys.argv[1]).read()
COLS = ["SEN", "SUB21", "JUN", "JUN1", "JUVA_JUL", "JUVB_JUL", "JUVA_MAR", "JUVB_MAR", "INFA", "INFB", "JUVA_ZON", "JUVB_ZON", "INFA_ZON", "INFB_ZON"]
STK = {"L": "FREE", "C": "BACK", "B": "BREAST", "M": "FLY", "E": "MEDLEY"}
def secs(v):
    p = [float(x) for x in v.split(":")]; s = 0
    for x in p: s = s * 60 + x
    return round(s, 2)
a = txt.index("4. Anexos"); body = txt[a:]
pools = {"50m": body[body.index("Piscina Longa |"):body.index("Piscina Curta |")], "25m": body[body.index("Piscina Curta |"):]}
T = {}  # (g, pool, s, d) -> {col: secs}
for pool, part in pools.items():
    g = None
    for line in part.splitlines():
        if "MASCULINOS" in line: g = "M"; continue
        if "FEMININOS" in line: g = "F"; continue
        if "MISTO" in line: g = None; continue
        m = re.match(r"^\s*(\d+)\s+([LCBME])\s+(.*)$", line)
        if not g or not m: continue
        vals = m.group(3).split()
        if len(vals) not in (4, 14): print("??", line); continue
        T[(g, pool, STK[m.group(2)], int(m.group(1)))] = {COLS[i]: secs(v) for i, v in enumerate(vals)}
W = {
 "zinf": {"label": "Zonais", "where": "26-28 fev 2027 · Cantanhede / Sines", "from": "2026-01-01", "to": "2027-02-16"},
 "ninf": {"label": "Nacionais", "where": "Reguengos de Monsaraz, 23-25 jul 2027", "from": "2026-10-01", "to": "2027-07-13"},
 "zjuv": {"label": "Zonais", "where": "4-6 dez 2026 · Bragança / Leiria", "from": "2025-10-01", "to": "2026-11-22"},
 "njuvm": {"label": "CN abril", "where": "Jamor, 2-4 abr 2027", "from": "2026-01-01", "to": "2027-03-23"},
 "njuvj": {"label": "CN julho", "where": "Coimbra, 29 jul-1 ago 2027", "from": "2026-01-01", "to": "2027-07-20"},
 "njs": {"label": "Nacionais", "where": "Tomar dez 2026 · Coimbra abr e jul 2027", "from": "2025-10-01", "to": "2027-07-20"},
}
CATS = [
 ("INFB", "Infantil B", [2014], [("zinf", "INFB_ZON"), ("ninf", "INFB")]),
 ("INFA", "Infantil A", [2013], [("zinf", "INFA_ZON"), ("ninf", "INFA")]),
 ("JUVB", "Juvenil B", [2012], [("zjuv", "JUVB_ZON"), ("njuvm", "JUVB_MAR"), ("njuvj", "JUVB_JUL")]),
 ("JUVA", "Juvenil A", [2011], [("zjuv", "JUVA_ZON"), ("njuvm", "JUVA_MAR"), ("njuvj", "JUVA_JUL")]),
 ("JUN1", "Júnior 1.º ano", [2010], [("njs", "JUN1")]),
 ("JUN", "Júnior", [2009], [("njs", "JUN")]),
 ("SEN", "Sénior", list(range(1930, 2009)), [("njs", "SEN")]),
]
cats, times = [], {}
for g in ("M", "F"):
    for cid, label, years, cols in CATS:
        k = cid + "_" + g
        cats.append({"id": k, "label": label + (" · Masc." if g == "M" else " · Fem."), "g": g, "years": years,
                     "cols": [dict(W[w], k=c) for w, c in cols]})
        rows = []
        for (gg, pool, s, d), v in sorted(T.items(), key=lambda x: (x[0][1], ["FREE","BACK","BREAST","FLY","MEDLEY"].index(x[0][2]), x[0][3])):
            if gg != g: continue
            vals = {c: v.get(c) for _, c in cols}
            if any(x is not None for x in vals.values()):
                rows.append({"pool": pool, "s": s, "d": d, "rc": 1, "v": vals})
        times[k] = rows
out = {"source": "FPN – Regulamento das Competições Nacionais NP 2026/2027 (23 jul 2026), Anexo TAC", "cats": cats, "times": times}
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, separators=(",", ":"))
print(len(T), "rows;", {k: len(v) for k, v in times.items()})
