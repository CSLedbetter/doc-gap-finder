"""Turn output/results.json into a single self-contained page: output/report.html."""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
URL = "https://doc-gap-finder.caseyledbetter.com"
DESCRIPTION = ("100 support tickets checked against a public docs site to find the questions "
               "the docs don't answer, with a drafted article for the biggest gap.")
HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{DESCRIPTION}">
<link rel="canonical" href="{URL}/">
<meta property="og:type" content="website">
<meta property="og:url" content="{URL}/">
<meta property="og:title" content="Support Doc Gap Finder">
<meta property="og:description" content="{DESCRIPTION}">
<meta property="og:image" content="{URL}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
</head>
<body>
"""


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\[CONFIRM: ([^\]]+)\]", r'<span class="confirm">To confirm: \1</span>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def markdown(md: str) -> str:
    """Just enough Markdown for a help article: headings, lists, paragraphs."""
    out, list_tag = [], None
    for line in md.splitlines():
        m_ul, m_ol = re.match(r"^- (.*)", line), re.match(r"^\d+\. (.*)", line)
        tag = "ul" if m_ul else "ol" if m_ol else None
        if list_tag and tag != list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None
        if tag:
            if not list_tag:
                out.append(f"<{tag}>")
                list_tag = tag
            out.append(f"<li>{inline((m_ul or m_ol).group(1))}</li>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if list_tag:
        out.append(f"</{list_tag}>")
    return "\n".join(out)


def main():
    data = json.loads((HERE / "output" / "results.json").read_text())
    index = HERE / "data" / "docs_index.jsonl"
    if index.exists():
        crawled = datetime.fromtimestamp(index.stat().st_mtime, timezone.utc)
        data["crawled_on"] = crawled.strftime("%B %-d, %Y")
    page = (HERE / "report_template.html").read_text()
    page = page.replace("/*DATA*/null", json.dumps(data).replace("</", "<\\/"))
    page = page.replace('/*ARTICLE*/""', json.dumps(markdown(data["article"]["markdown"])).replace("</", "<\\/"))
    (HERE / "output" / "report.html").write_text(page)
    print(f"wrote {HERE / 'output' / 'report.html'}")

    # The same page as a full document for the Vercel site in site/
    site = HERE / "site"
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text(HEAD + page + "\n</body>\n</html>\n")
    print(f"wrote {site / 'index.html'}")


if __name__ == "__main__":
    main()
