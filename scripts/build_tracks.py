#!/usr/bin/env python3
"""Inject the compact topic tracks into index.html.

The site is a single self-contained page: every guide page lives in an
embedded JSON blob that the tiny SPA renders. This script reads the track
markdown from docs/track-*/, renders it the same way the main guide was
rendered, and rewrites three things in place:

  1. the JSON blob        - pages, sections (flagged track:true), order
  2. the hero tracks list - between <!--TRACKS--> and <!--/TRACKS-->
  3. nothing else         - the SPA handles tracks generically

Re-running is safe: previous track entries are replaced, not duplicated.

    pip install markdown
    python3 scripts/build_tracks.py
"""
import io, json, os, re, sys

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "index.html")

# page order inside each track is editorial, not alphabetical
TRACKS = {
    "track-graph": {
        "title": "Knowledge graphs",
        "blurb": "Graphs as agent memory: GraphRAG, extraction pipelines, "
                 "stores, and where plain wikilinks are enough.",
        "order": ["why-graphs", "graphrag", "building-graphs-with-llms",
                  "graph-stores", "tools", "resources"],
    },
    "track-jev": {
        "title": "Jev engineering",
        "blurb": "Building with System One models: typed decisions with "
                 "confidence scores instead of generated text. A week old "
                 "and moving fast.",
        "order": ["system-one-models", "what-jev-is-good-for",
                  "jev-in-an-agent-stack", "getting-started", "resources"],
    },
    "track-harness": {
        "title": "Agent harnesses",
        "blurb": "The machinery around the model: loops, tools, context "
                 "engineering, permissions, and the current landscape.",
        "order": ["what-a-harness-is", "claude-code-as-harness",
                  "context-engineering", "tools-and-mcp",
                  "harness-landscape", "resources"],
    },
    "track-evals": {
        "title": "Eval engineering",
        "blurb": "Measurement as the discipline of AI products: golden sets, "
                 "judges that do not lie, agent trajectories, CI.",
        "order": ["why-evals", "designing-evals", "llm-as-judge",
                  "agent-evals", "tooling", "resources"],
    },
}

MD = markdown.Markdown(extensions=["fenced_code", "tables"])


def render_page(sec, fname):
    path = os.path.join(ROOT, "docs", sec, fname + ".md")
    src = io.open(path, encoding="utf-8").read().strip()
    lines = src.split("\n")
    if not lines[0].startswith("# "):
        raise SystemExit(f"{path}: first line must be an H1 title")
    title = lines[0][2:].strip()
    body = "\n".join(lines[1:]).strip()
    MD.reset()
    html = MD.convert(body)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
    links = []
    for href, label in re.findall(r'href="([^"]+\.md)"[^>]*>(.*?)</a>', html):
        to = sec + "/" + href.replace("./", "").replace(".md", "")
        links.append({"to": to, "label": re.sub(r"<[^>]+>", "", label)})
    return {
        "id": f"{sec}/{fname}",
        "path": f"docs/{sec}/{fname}.md",
        "section": sec,
        "section_title": TRACKS[sec]["title"],
        "title": title,
        "html": html,
        "headings": headings,
        "words": len(text.split()),
        "text": text[:4000],
        "links": links,
    }


def main():
    s = io.open(INDEX, encoding="utf-8").read()
    i = s.find('application/json">') + len('application/json">')
    j = s.find("</script>", i)
    D = json.loads(s[i:j])

    # replace any previous track entries
    D["pages"] = [p for p in D["pages"] if not p["section"].startswith("track-")]
    D["sections"] = {k: v for k, v in D["sections"].items()
                     if not k.startswith("track-")}
    D["order"] = {k: v for k, v in D["order"].items()
                  if not k.startswith("track-")}

    cards = []
    for sec, meta in TRACKS.items():
        missing = [f for f in meta["order"]
                   if not os.path.exists(os.path.join(ROOT, "docs", sec, f + ".md"))]
        if missing:
            print(f"skip {sec}: missing {', '.join(missing)}")
            continue
        pages = [render_page(sec, f) for f in meta["order"]]
        D["pages"].extend(pages)
        D["sections"][sec] = {"title": meta["title"], "blurb": meta["blurb"],
                              "track": True}
        D["order"][sec] = [p["id"] for p in pages]
        cards.append(
            f'<article><h3><a href="#{pages[0]["id"]}">{meta["title"]}</a></h3>'
            f'<p>{meta["blurb"]}</p>'
            f'<div class="pg">{len(pages)} pages</div></article>')
        print(f"{sec}: {len(pages)} pages, "
              f"{sum(p['words'] for p in pages)} words")

    s = s[:i] + json.dumps(D, ensure_ascii=False) + s[j:]

    block = ('<!--TRACKS--><div class="trkhead"><h2>tracks</h2>'
             '<p>Compact deep-dives beside the main guide: the moving parts '
             'of building with agents, a page at a time.</p></div>'
             '<div class="seclist tracklist">' + "".join(cards)
             + "</div><!--/TRACKS-->")
    if "<!--TRACKS-->" in s:
        s = re.sub(r"<!--TRACKS-->.*?<!--/TRACKS-->", lambda m: block, s,
                   flags=re.S)
    else:
        raise SystemExit("no <!--TRACKS--> marker in index.html; add one "
                         "after the seclist in the hero")
    io.open(INDEX, "w", encoding="utf-8", newline="\n").write(s)
    print("index.html rewritten")


if __name__ == "__main__":
    main()
