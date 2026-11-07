"""Glossary candidates: phrases in Sol's replies ([sol_text] in battery logs) ranked by how many
prompts use them and how rare they are in everyday English. Runs on the host, not in Docker:
pip install wordfreq; python evals/term_finder.py test_runs [top_n]"""
import math, re, sys
from collections import Counter
from pathlib import Path
from wordfreq import zipf_frequency, tokenize

STOP = set("""a an the and or but if then so to of in on at by for with from into onto as is are was
were be been it its this that these those you your yours we our i me my they them their he she his her
not no yes do does did can could should would will just also only up down out off over more most less
very than too there here what which who when where how why all any each some one two three first next
make sure set open click press choose select use using go get let it's that's you'll you're don't""".split())

def replies(root: Path):
    """(scenario, reply text). A reply runs from [sol_text] to the next log line."""
    for f in root.rglob("*.log"):
        cur, scen = None, f.name
        for line in f.read_text(errors="ignore").splitlines():
            if line.startswith("SCENARIO:"):
                scen = line.split(":", 1)[1].strip()
            if line.startswith("[sol_text]"):
                if cur: yield scen, "\n".join(cur)
                cur = [line[len("[sol_text]"):]]
            elif cur is not None:
                if line.startswith(("[", "  ", "--", "====", "SCENARIO")):
                    yield scen, "\n".join(cur); cur = None
                else:
                    cur.append(line)
        if cur: yield scen, "\n".join(cur)

pairs = sorted(set((sc, t.strip()) for sc, t in replies(Path(sys.argv[1])) if t.strip()))
texts = [t for _, t in pairs]
df = Counter()       # distinct scenarios (prompts) whose replies use the phrase
seen = {}
for sc, t in pairs:
    toks = [w for w in tokenize(t, "en") if re.fullmatch(r"[a-z][a-z0-9'\-]*", w)]
    grams = set()
    for n in (1, 2, 3):
        for i in range(len(toks) - n + 1):
            g = toks[i:i + n]
            if g[0] in STOP or g[-1] in STOP or len(g[-1]) < 3:
                continue
            grams.add(" ".join(g))
    seen.setdefault(sc, set()).update(grams)
for grams in seen.values():
    df.update(grams)

rows = []
for g, c in df.items():
    if c < 3:
        continue
    z = zipf_frequency(g, "en")          # 0 = unseen in everyday English, 7 = "the"
    score = math.log(c) * (6.0 - min(z, 6.0))
    rows.append((score, c, z, g))
rows.sort(reverse=True)

# drop a shorter phrase when a longer one containing it has nearly the same count
kept = []
for s, c, z, g in rows:
    if any(g in k and kc >= 0.8 * c for _, kc, _, k in kept):
        continue
    kept.append((s, c, z, g))

print(f"{len(texts)} unique replies, {len(seen)} scenarios\n")
print(f"{'prompts':>7}  {'english':>7}  term")
for s, c, z, g in kept[:int(sys.argv[2]) if len(sys.argv) > 2 else 200]:
    print(f"{c:7d}  {z:7.2f}  {g}")
