"""Find documentation gaps from a batch of support tickets.

Pipeline:
  1. Read open tickets from the inbox (inbox.py).
  2. Group them into topics with Claude.
  3. For each topic, pull candidate articles from the docs snapshot with BM25,
     then ask Claude whether each ticket is answered by them:
     covered, partial or missing.
  4. Rank topics by gap size (missing counts 1, partial counts 0.5).
  5. Draft a help article for the biggest gap.
  6. Re-check every uncovered ticket against the draft to get the
     before-and-after number.

    python find_gaps.py             # live: needs ANTHROPIC_API_KEY
    python find_gaps.py --offline   # replays the saved judgments in data/offline_judgments.json

Results go to output/results.json. Run build_report.py to turn them into a page.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from inbox import open_tickets
from search import DocIndex, tokens

HERE = Path(__file__).parent
CONFIG = json.loads((HERE / "config.json").read_text())
SCORE = {"covered": 1.0, "partial": 0.5, "missing": 0.0}

SYSTEM = (
    "You are a senior support operations analyst. You read customer tickets and "
    "public help docs, and you judge strictly: a doc only counts as covering a "
    "ticket if a customer could resolve their question from it without contacting support."
)


# ---------- Claude calls ----------

class Judge:
    """Wraps every model call so the pipeline can also run from saved output."""

    def __init__(self, offline: bool):
        self.offline = offline
        if offline:
            self.saved = json.loads((HERE / "data" / "offline_judgments.json").read_text())
        else:
            import anthropic
            self.client = anthropic.Anthropic()

    def ask(self, step: str, key: str, prompt: str, schema: dict, max_tokens: int = 16000) -> dict:
        if self.offline:
            return self.saved[step][key] if key else self.saved[step]
        resp = self.client.beta.messages.create(
            model=CONFIG["model"],
            max_tokens=max_tokens,
            system=SYSTEM,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"{step} {key}: request was declined")
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)


def obj(props: dict, required=None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


CLUSTER_SCHEMA = obj({"topics": {"type": "array", "items": obj({
    "topic_id": {"type": "string"},
    "label": {"type": "string"},
    "description": {"type": "string"},
    "ticket_ids": {"type": "array", "items": {"type": "string"}},
})}})

VERDICT_SCHEMA = obj({"verdicts": {"type": "array", "items": obj({
    "ticket_id": {"type": "string"},
    "coverage": {"type": "string", "enum": ["covered", "partial", "missing"]},
    "doc_url": {"type": ["string", "null"]},
    "reason": {"type": "string"},
})}})

ARTICLE_SCHEMA = obj({
    "title": {"type": "string"},
    "markdown": {"type": "string"},
    "open_questions": {"type": "array", "items": {"type": "string"}},
})


def fmt_tickets(ts: list[dict]) -> str:
    return "\n\n".join(f"<ticket id=\"{t['id']}\" plan=\"{t['plan']}\">\n{t['subject']}\n{t['body']}\n</ticket>" for t in ts)


# ---------- retrieval ----------

def passages(text: str, query: str, size: int = 900, top: int = 2) -> str:
    """Opening of the doc plus the chunks that best match the query."""
    q = set(tokens(query))
    chunks = [text[i:i + size] for i in range(0, len(text), size)]
    ranked = sorted(range(len(chunks)), key=lambda i: -len(q & set(tokens(chunks[i]))))
    keep = sorted(set([0] + ranked[:top]))
    return " … ".join(chunks[i] for i in keep)


def candidates(index: DocIndex, topic: dict, ts: list[dict], k_per_ticket: int = 4, cap: int = 10) -> list[dict]:
    scores = defaultdict(float)
    docs = {}
    for t in ts:
        for d in index.search(f"{topic['label']} {t['subject']} {t['body']}", k=k_per_ticket):
            scores[d["url"]] += d["score"]
            docs[d["url"]] = d
    query = topic["label"] + " " + " ".join(t["subject"] + " " + t["body"] for t in ts)
    top = sorted(scores, key=lambda u: -scores[u])[:cap]
    return [{"url": u, "title": docs[u]["title"], "site": docs[u]["site"], "excerpt": passages(docs[u]["text"], query)} for u in top]


# ---------- pipeline ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use saved judgments instead of calling the API")
    args = ap.parse_args()
    offline = args.offline or not os.environ.get("ANTHROPIC_API_KEY")
    if offline and not args.offline:
        print("No ANTHROPIC_API_KEY set, so using saved judgments (--offline).", file=sys.stderr)
    judge = Judge(offline)

    tickets = open_tickets()
    by_id = {t["id"]: t for t in tickets}
    index = DocIndex()
    print(f"{len(tickets)} tickets, {len(index.docs)} doc pages", file=sys.stderr)

    # 1. group by topic
    clusters = judge.ask("cluster", None, (
        f"Here are {len(tickets)} support tickets for {CONFIG['product']}.\n"
        "Group them into 10 to 20 topics by the underlying question the customer needs answered, "
        "not by product area. Every ticket goes in exactly one topic. Labels are short and in plain "
        "customer language. Use ids t1, t2, ...\n\n" + fmt_tickets(tickets)
    ), CLUSTER_SCHEMA)["topics"]

    # 2. coverage per topic
    verdicts = {}
    topic_docs = {}
    for topic in clusters:
        ts = [by_id[i] for i in topic["ticket_ids"] if i in by_id]
        docs = candidates(index, topic, ts)
        topic_docs[topic["topic_id"]] = docs
        doc_block = "\n\n".join(f"<doc url=\"{d['url']}\" title=\"{d['title']}\">\n{d['excerpt']}\n</doc>" for d in docs)
        out = judge.ask("coverage", topic["topic_id"], (
            f"Topic: {topic['label']}\n\nThese are the most relevant pages from the public docs:\n\n{doc_block}\n\n"
            f"Tickets:\n\n{fmt_tickets(ts)}\n\n"
            "For each ticket, decide:\n"
            "- covered: a doc answers the customer's actual question well enough to resolve it.\n"
            "- partial: a doc touches the topic but leaves the specific question unanswered, or only answers part.\n"
            "- missing: no doc answers it.\n"
            "Give the single best doc_url (null if missing) and a one-sentence reason naming what is or isn't in the doc."
        ), VERDICT_SCHEMA)
        for v in out["verdicts"]:
            verdicts[v["ticket_id"]] = v

    # 3. rank gaps
    topics = []
    for topic in clusters:
        vs = [verdicts[i] for i in topic["ticket_ids"] if i in verdicts]
        counts = {c: sum(v["coverage"] == c for v in vs) for c in SCORE}
        gap = counts["missing"] + 0.5 * counts["partial"]
        topics.append({**topic, "tickets": len(vs), **counts, "gap_score": gap,
                       "coverage_pct": round(100 * sum(SCORE[v["coverage"]] for v in vs) / max(len(vs), 1)),
                       "docs_checked": [{k: d[k] for k in ("url", "title", "site")} for d in topic_docs[topic["topic_id"]]]})
    topics.sort(key=lambda t: (-t["gap_score"], -t["tickets"]))
    biggest = topics[0]

    # 4. draft the article
    ts = [by_id[i] for i in biggest["ticket_ids"]]
    related = "\n\n".join(f"<doc url=\"{d['url']}\" title=\"{d['title']}\">\n{d['excerpt']}\n</doc>"
                          for d in topic_docs[biggest["topic_id"]][:6])
    article = judge.ask("article", None, (
        f"The biggest documentation gap is \"{biggest['label']}\": {biggest['description']}\n\n"
        f"Customer tickets:\n\n{fmt_tickets(ts)}\n\nRelated existing docs (use them for facts and to link to):\n\n{related}\n\n"
        "Write a help-center article that would let these customers solve this without contacting support. "
        "Answer the questions in the order customers ask them, use the product's own UI names, and keep it scannable. "
        "Only state policy that the existing docs support. Where you need a fact the docs don't give, write it as "
        "[CONFIRM: question] and list it in open_questions so the billing or product team can fill it in."
    ), ARTICLE_SCHEMA)

    # 5. re-check uncovered tickets against the draft
    uncovered = [by_id[i] for i, v in verdicts.items() if v["coverage"] != "covered"]
    recheck = judge.ask("recheck", None, (
        f"A new help article has been drafted:\n\n<doc url=\"new-article\" title=\"{article['title']}\">\n{article['markdown']}\n</doc>\n\n"
        f"Tickets:\n\n{fmt_tickets(uncovered)}\n\n"
        "For each ticket, judge only whether this new article answers it. Treat [CONFIRM] placeholders as if the "
        "team will fill them in with a real answer. Use doc_url \"new-article\" or null."
    ), VERDICT_SCHEMA)["verdicts"]
    now_covered = {v["ticket_id"] for v in recheck if v["coverage"] == "covered"}

    n = len(tickets)
    missing = [i for i, v in verdicts.items() if v["coverage"] == "missing"]
    partial = [i for i, v in verdicts.items() if v["coverage"] == "partial"]
    summary = {
        "tickets": n,
        "doc_pages": len(index.docs),
        "covered": n - len(missing) - len(partial),
        "partial": len(partial),
        "missing": len(missing),
        "missing_pct": round(100 * len(missing) / n),
        "weak_pct": round(100 * (len(missing) + len(partial)) / n),
        "missing_fixed_by_article": len(now_covered & set(missing)),
        "partial_fixed_by_article": len(now_covered & set(partial)),
    }
    summary["missing_after"] = summary["missing"] - summary["missing_fixed_by_article"]
    summary["missing_after_pct"] = round(100 * summary["missing_after"] / n)
    summary["weak_after_pct"] = round(100 * (len(missing) + len(partial) - len(now_covered)) / n)
    summary["share_of_missing_fixed_pct"] = round(100 * summary["missing_fixed_by_article"] / max(len(missing), 1))

    out = {
        "mode": "offline (saved judgments)" if offline else f"live ({CONFIG['model']})",
        "product": CONFIG["product"],
        "doc_sites": [s["name"] for s in CONFIG["doc_sites"]],
        "summary": summary,
        "topics": topics,
        "tickets": [{**t, **{k: verdicts[t["id"]][k] for k in ("coverage", "doc_url", "reason")},
                     "topic_id": next(tp["topic_id"] for tp in topics if t["id"] in tp["ticket_ids"]),
                     "fixed_by_article": t["id"] in now_covered} for t in tickets],
        "article": {**article, "topic_id": biggest["topic_id"]},
    }
    (HERE / "output").mkdir(exist_ok=True)
    (HERE / "output" / "results.json").write_text(json.dumps(out, indent=2))
    s = summary
    print(f"\n{s['missing_pct']}% of tickets ({s['missing']}/{n}) had no matching doc; "
          f"{s['weak_pct']}% had weak or no coverage.")
    print(f"Biggest gap: {biggest['label']} ({biggest['tickets']} tickets).")
    print(f"The draft article covers {s['missing_fixed_by_article']} of the {s['missing']} unanswered tickets "
          f"({s['share_of_missing_fixed_pct']}%), taking no-doc tickets from {s['missing_pct']}% to {s['missing_after_pct']}%.")


if __name__ == "__main__":
    main()
