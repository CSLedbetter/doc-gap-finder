"""Build a searchable snapshot of any public docs site from its sitemap.

Works on any site that publishes a sitemap.xml. Point it at your own help
center by editing config.json, or pass --sitemap on the command line.

    python crawl_docs.py                      # uses the sites in config.json
    python crawl_docs.py --sitemap https://help.example.com/sitemap.xml
"""

import argparse
import concurrent.futures as cf
import json
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).parent
UA = {"User-Agent": "doc-gap-finder/1.0 (+portfolio project)"}


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def sitemap_urls(sitemap: str) -> list[str]:
    xml = fetch(sitemap)
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
    # A sitemap index points at more sitemaps, so follow them.
    if "<sitemapindex" in xml:
        out = []
        for child in locs:
            out.extend(sitemap_urls(child))
        return out
    return locs


def extract(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    title = re.split(r"\s+[|\-–]\s+", title)[0]
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "svg", "form"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(" ", strip=True)
    # Help-center boilerplate that adds noise to search.
    text = re.split(r"Did this answer your question\?", text)[0]
    return title, re.sub(r"\s+", " ", text)


def crawl_site(site: dict, workers: int) -> list[dict]:
    urls = sitemap_urls(site["sitemap"])
    inc = re.compile(site.get("include", ".*"))
    exc = re.compile(site["exclude"]) if site.get("exclude") else None
    urls = sorted({u for u in urls if inc.search(u) and not (exc and exc.search(u))})
    print(f"{site['name']}: {len(urls)} pages", file=sys.stderr)

    def one(url):
        try:
            title, text = extract(fetch(url))
            return {"site": site["name"], "url": url, "title": title, "text": text[:20000]}
        except Exception as e:  # keep going if one page fails
            print(f"  skip {url}: {e}", file=sys.stderr)
            return None

    with cf.ThreadPoolExecutor(workers) as pool:
        return [d for d in pool.map(one, urls) if d and len(d["text"]) > 80]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=HERE / "config.json")
    ap.add_argument("--sitemap", help="crawl one sitemap instead of the config")
    ap.add_argument("--include", default=".*")
    ap.add_argument("--out", default=HERE / "data" / "docs_index.jsonl")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if args.sitemap:
        sites = [{"name": "docs", "sitemap": args.sitemap, "include": args.include}]
    else:
        sites = json.loads(Path(args.config).read_text())["doc_sites"]

    docs = []
    for site in sites:
        docs.extend(crawl_site(site, args.workers))
    with open(args.out, "w") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")
    print(f"wrote {len(docs)} pages to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
