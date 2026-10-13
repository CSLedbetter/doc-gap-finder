"""Small BM25 search over the docs snapshot, no extra dependencies.

The analyzer uses this to pull candidate articles for each ticket group
before asking Claude whether any of them actually answers the question.

    python search.py "refund annual plan"
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
STOP = set(
    "a an the and or of to in on for with is are was were be been it this that i my me we our you your "
    "can do does how what why when where which from at by as not no but if so have has had will would "
    "should could just get got any all about into there their they them its it's im i'm".split()
)


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 1]


class DocIndex:
    def __init__(self, path=HERE / "data" / "docs_index.jsonl", k1=1.4, b=0.75):
        self.docs = [json.loads(l) for l in open(path)]
        self.k1, self.b = k1, b
        self.tf, self.len = [], []
        df = Counter()
        for d in self.docs:
            # Titles carry a lot of signal on help centers, so count them three times.
            toks = tokens(d["title"]) * 3 + tokens(d["text"])
            c = Counter(toks)
            self.tf.append(c)
            self.len.append(len(toks))
            df.update(c.keys())
        n = len(self.docs)
        self.avg = sum(self.len) / n
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 5) -> list[dict]:
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [dict(self.docs[i], score=round(s, 2)) for s, i in scores[:k]]


if __name__ == "__main__":
    idx = DocIndex()
    for r in idx.search(" ".join(sys.argv[1:]), k=int(8)):
        print(f"{r['score']:6.1f}  {r['site']:<17} {r['title'][:70]:<70} {r['url']}")
