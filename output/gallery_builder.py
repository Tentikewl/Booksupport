"""Build a static HTML gallery from generated chapter images and entity data."""
from __future__ import annotations
import json
import shutil
from pathlib import Path

import config


_HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Illustrated Edition</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #0d0d0f;
    --surface: #16161a;
    --border: #2a2a30;
    --text: #e0ddd8;
    --muted: #888;
    --accent: #c9a84c;
    --sidebar-w: 300px;
  }}
  body {{ background: var(--bg); color: var(--text); font-family: Georgia, serif; display: flex; min-height: 100vh; }}
  nav {{
    width: 220px; flex-shrink: 0; background: var(--surface);
    border-right: 1px solid var(--border); padding: 1.5rem 1rem;
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
  }}
  nav h2 {{ font-size: .75rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 1rem; }}
  nav a {{ display: block; padding: .4rem .5rem; color: var(--text); text-decoration: none; border-radius: 4px; font-size: .9rem; }}
  nav a:hover, nav a.active {{ background: var(--border); color: var(--accent); }}
  main {{ flex: 1; padding: 2rem; max-width: 1100px; }}
  h1 {{ font-size: 1.6rem; color: var(--accent); margin-bottom: .25rem; }}
  .subtitle {{ color: var(--muted); font-size: .9rem; margin-bottom: 2rem; }}
  .chapter-section {{ margin-bottom: 4rem; }}
  .chapter-title {{ font-size: 1.1rem; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border); padding-bottom: .5rem; margin-bottom: 1.5rem; }}
  .beats-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; }}
  .beat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; cursor: pointer; transition: border-color .2s; }}
  .beat-card:hover {{ border-color: var(--accent); }}
  .beat-card img {{ width: 100%; display: block; aspect-ratio: 16/9; object-fit: cover; }}
  .beat-caption {{ padding: .75rem 1rem; }}
  .beat-caption p {{ font-size: .85rem; color: var(--text); line-height: 1.5; }}
  .beat-caption .mood {{ font-size: .75rem; color: var(--muted); margin-top: .4rem; text-transform: uppercase; letter-spacing: .08em; }}
  aside.entity-sidebar {{
    width: var(--sidebar-w); flex-shrink: 0; background: var(--surface);
    border-left: 1px solid var(--border); padding: 1.5rem 1rem;
    height: 100vh; overflow-y: auto; position: sticky; top: 0;
  }}
  aside.entity-sidebar h2 {{ font-size: .75rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 1rem; }}
  .entity-card {{ border: 1px solid var(--border); border-radius: 6px; padding: .75rem; margin-bottom: .75rem; }}
  .entity-card h3 {{ font-size: .9rem; color: var(--accent); margin-bottom: .25rem; }}
  .entity-card .entity-type {{ font-size: .7rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: .4rem; }}
  .entity-card p {{ font-size: .8rem; line-height: 1.5; color: var(--text); }}
  .entity-card .first-app {{ font-size: .75rem; color: var(--muted); margin-top: .4rem; }}
  /* Lightbox */
  #lightbox {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,.9); z-index: 1000; align-items: center; justify-content: center; flex-direction: column; gap: 1rem; }}
  #lightbox.open {{ display: flex; }}
  #lightbox img {{ max-width: 90vw; max-height: 80vh; border-radius: 6px; }}
  #lightbox p {{ color: var(--text); max-width: 700px; text-align: center; font-size: .9rem; }}
  #lightbox-close {{ position: absolute; top: 1rem; right: 1.5rem; color: var(--muted); font-size: 1.5rem; cursor: pointer; background: none; border: none; }}
</style>
</head>
<body>
"""

_HTML_NAV = """\
<nav>
  <h2>{title}</h2>
  {chapter_links}
  <hr style="border-color:var(--border);margin:1rem 0">
  <a href="#entities">Entity Reference</a>
</nav>
"""

_HTML_LIGHTBOX = """\
<div id="lightbox">
  <button id="lightbox-close" onclick="closeLightbox()">✕</button>
  <img id="lb-img" src="" alt="">
  <p id="lb-caption"></p>
</div>
<script>
  function openLightbox(src, caption) {
    document.getElementById('lb-img').src = src;
    document.getElementById('lb-caption').textContent = caption;
    document.getElementById('lightbox').classList.add('open');
  }
  function closeLightbox() {
    document.getElementById('lightbox').classList.remove('open');
  }
  document.getElementById('lightbox').addEventListener('click', function(e) {
    if (e.target === this) closeLightbox();
  });
</script>
"""


def build_gallery(
    title: str,
    chapter_results: list[dict],
    entities: list[dict],
    output_dir: Path,
) -> Path:
    """
    Build a static HTML gallery.

    chapter_results: list of {chapter_id, images: [{beat, image_path, filename}]}
    entities: from entity_extractor.get_all_entities()
    output_dir: where to write index.html and copy images
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Copy images into gallery folder
    for ch in chapter_results:
        ch_images_dir = images_dir / ch["chapter_id"]
        ch_images_dir.mkdir(exist_ok=True)
        for item in ch.get("images", []):
            src = Path(item["image_path"])
            if src.exists():
                dest = ch_images_dir / item["filename"]
                shutil.copy2(src, dest)
                item["gallery_path"] = f"images/{ch['chapter_id']}/{item['filename']}"

    # Build nav links
    chapter_links = "\n  ".join(
        f'<a href="#{ch["chapter_id"]}">{ch["chapter_id"].replace("_", " ").title()}</a>'
        for ch in chapter_results
    )

    # Build chapter sections
    chapter_sections: list[str] = []
    for ch in chapter_results:
        beats_html: list[str] = []
        for item in ch.get("images", []):
            beat = item["beat"]
            gpath = item.get("gallery_path", item["image_path"])
            desc = beat.get("visual_description", "")
            mood = beat.get("mood", "")
            beats_html.append(
                f'<div class="beat-card" onclick="openLightbox(\'{gpath}\', \'{_esc(desc)}\')">'
                f'<img src="{gpath}" alt="{_esc(desc)}" loading="lazy">'
                f'<div class="beat-caption"><p>{_esc(desc)}</p>'
                f'<div class="mood">{_esc(mood)}</div></div></div>'
            )
        chapter_sections.append(
            f'<section class="chapter-section" id="{ch["chapter_id"]}">'
            f'<h2 class="chapter-title">{ch["chapter_id"].replace("_", " ").title()}</h2>'
            f'<div class="beats-grid">{"".join(beats_html)}</div></section>'
        )

    # Build entity cards (characters first, then locations, then objects)
    def sort_key(e: dict) -> int:
        return {"character": 0, "location": 1, "object": 2, "faction": 3}.get(e["type"], 4)

    sorted_entities = sorted(entities, key=sort_key)
    entity_cards: list[str] = []
    for e in sorted_entities:
        aliases = ", ".join(e.get("aliases", []))
        alias_str = f" ({aliases})" if aliases else ""
        notes = "; ".join(e.get("visual_notes", []))
        entity_cards.append(
            f'<div class="entity-card">'
            f'<h3>{_esc(e["name"])}{_esc(alias_str)}</h3>'
            f'<div class="entity-type">{e["type"]}</div>'
            f'<p>{_esc(e["canonical_description"])}'
            f'{(" — " + _esc(notes)) if notes else ""}</p>'
            f'<div class="first-app">First appears: {e.get("first_appearance", "unknown")}</div>'
            f'</div>'
        )

    html = (
        _HTML_HEAD.format(title=_esc(title))
        + _HTML_NAV.format(title=_esc(title), chapter_links=chapter_links)
        + "<main>"
        + f'<h1>{_esc(title)}</h1>'
        + f'<p class="subtitle">Illustrated Edition — {len(chapter_results)} chapter(s) · {sum(len(ch.get("images", [])) for ch in chapter_results)} illustration(s)</p>'
        + "".join(chapter_sections)
        + "</main>"
        + f'<aside class="entity-sidebar"><h2>Entity Reference</h2><div id="entities">{"".join(entity_cards)}</div></aside>'
        + _HTML_LIGHTBOX
        + "</body></html>"
    )

    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"Gallery written to {index_path}")
    return index_path


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
