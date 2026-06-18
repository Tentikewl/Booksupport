"""Build a static HTML gallery from generated chapter images and entity data."""
from __future__ import annotations
import base64
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
  }}
  body {{ background: var(--bg); color: var(--text); font-family: Georgia, serif; }}
  header {{
    padding: 1.5rem 1rem 1rem;
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; background: var(--bg); z-index: 10;
  }}
  header h1 {{ font-size: 1.3rem; color: var(--accent); }}
  header p {{ font-size: .8rem; color: var(--muted); margin-top: .2rem; }}
  nav {{
    display: flex; gap: .5rem; flex-wrap: wrap;
    padding: .75rem 1rem; border-bottom: 1px solid var(--border);
    background: var(--bg); overflow-x: auto;
  }}
  nav a {{
    color: var(--muted); text-decoration: none; font-size: .8rem;
    padding: .3rem .6rem; border: 1px solid var(--border); border-radius: 4px;
    white-space: nowrap;
  }}
  nav a:hover {{ color: var(--accent); border-color: var(--accent); }}
  main {{ padding: 1rem; max-width: 900px; margin: 0 auto; }}
  .chapter-section {{ margin-bottom: 3rem; }}
  .chapter-title {{
    font-size: .85rem; letter-spacing: .1em; text-transform: uppercase;
    color: var(--muted); border-bottom: 1px solid var(--border);
    padding-bottom: .5rem; margin-bottom: 1.25rem; margin-top: 2rem;
  }}
  .beats-grid {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.25rem;
  }}
  @media (min-width: 600px) {{
    .beats-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}
  @media (min-width: 900px) {{
    .beats-grid {{ grid-template-columns: repeat(3, 1fr); }}
  }}
  .beat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden; cursor: pointer;
    transition: border-color .2s;
  }}
  .beat-card:hover {{ border-color: var(--accent); }}
  .beat-card img {{ width: 100%; display: block; aspect-ratio: 16/9; object-fit: cover; }}
  .beat-caption {{ padding: .75rem; }}
  .beat-number {{ font-size: .7rem; color: var(--accent); text-transform: uppercase; letter-spacing: .08em; margin-bottom: .3rem; }}
  .beat-caption p {{ font-size: .82rem; color: var(--text); line-height: 1.5; }}
  .beat-mood {{ font-size: .72rem; color: var(--muted); margin-top: .35rem; text-transform: uppercase; letter-spacing: .08em; }}
  .intro-section-title {{ font-size: .78rem; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); margin: 1.5rem 0 .75rem; opacity: .7; }}
  .intro-label {{ color: var(--accent) !important; }}
  /* Lightbox */
  #lightbox {{
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.92); z-index: 1000;
    align-items: center; justify-content: center;
    flex-direction: column; gap: .75rem; padding: 1rem;
  }}
  #lightbox.open {{ display: flex; }}
  #lightbox img {{ max-width: 100%; max-height: 75vh; border-radius: 6px; object-fit: contain; }}
  #lb-caption {{ color: var(--text); max-width: 600px; text-align: center; font-size: .85rem; line-height: 1.5; }}
  #lb-mood {{ color: var(--muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; }}
  #lightbox-close {{
    position: absolute; top: .75rem; right: 1rem;
    color: var(--muted); font-size: 1.5rem; cursor: pointer;
    background: none; border: none; line-height: 1;
  }}
</style>
</head>
<body>
"""

_HTML_LIGHTBOX = """\
<div id="lightbox">
  <button id="lightbox-close" onclick="closeLightbox()">✕</button>
  <img id="lb-img" src="" alt="">
  <p id="lb-caption"></p>
  <p id="lb-mood"></p>
</div>
<script>
  function openLightbox(src, caption, mood) {
    document.getElementById('lb-img').src = src;
    document.getElementById('lb-caption').textContent = caption;
    document.getElementById('lb-mood').textContent = mood;
    document.getElementById('lightbox').classList.add('open');
  }
  function closeLightbox() {
    document.getElementById('lightbox').classList.remove('open');
  }
  document.getElementById('lightbox').addEventListener('click', function(e) {
    if (e.target === this) closeLightbox();
  });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeLightbox();
  });
</script>
"""


def _copy_image(src: Path, output_dir: Path) -> str:
    """Copy image into gallery/images/ and return its relative URL."""
    rel = src.relative_to(config.OUTPUT_DIR)
    dest = output_dir / "images" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dest)
    return "images/" + str(rel).replace("\\", "/")


def _img_to_b64(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:image/jpeg;base64,{b64}"


def build_gallery(
    title: str,
    chapter_results: list[dict],
    entities: list[dict],
    output_dir: Path,
    embed: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Nav links
    chapter_links = "\n  ".join(
        f'<a href="#{ch["chapter_id"]}">{ch["chapter_id"].replace("_", " ").title()}</a>'
        for ch in chapter_results
    )

    # Chapter sections
    chapter_sections: list[str] = []
    for ch in chapter_results:
        # Scene beats
        beats_html: list[str] = []
        for i, item in enumerate(ch.get("images", []), 1):
            beat = item["beat"]
            img_path = Path(item["image_path"])
            desc = beat.get("visual_description", "")
            mood = beat.get("mood", "")
            position = beat.get("position", "")
            beat_label = f"Beat {i}"
            if position:
                beat_label += f" · {int(float(position) * 100)}% through chapter"
            src = (_img_to_b64(img_path) if embed else _copy_image(img_path, output_dir)) if img_path.exists() else ""
            beats_html.append(
                f'<div class="beat-card" onclick="openLightbox({json.dumps(src)}, {json.dumps(desc)}, {json.dumps(mood)})">'
                f'<img src="{src}" alt="{_esc(desc)}" loading="lazy">'
                f'<div class="beat-caption">'
                f'<div class="beat-number">{_esc(beat_label)}</div>'
                f'<p>{_esc(desc)}</p>'
                f'<div class="beat-mood">{_esc(mood)}</div>'
                f'</div></div>'
            )

        # Introduction illustrations
        intros_html: list[str] = []
        for item in ch.get("intro_images", []):
            entity = item["entity"]
            img_path = Path(item["image_path"])
            name = entity.get("name", entity.get("id", ""))
            kind = item["kind"]
            is_reintro = item.get("is_reintro", False)
            desc = item.get("change_description", "") if is_reintro else entity.get("canonical_description", "")
            label = f"{'Transformation' if is_reintro else ('Portrait' if kind == 'character' else 'Concept')} — {name}"
            badge = "Transformation" if is_reintro else ("New Character" if kind == "character" else "New " + kind.title())
            src = (_img_to_b64(img_path) if embed else _copy_image(img_path, output_dir)) if img_path.exists() else ""
            intros_html.append(
                f'<div class="beat-card intro-card" onclick="openLightbox({json.dumps(src)}, {json.dumps(label)}, {json.dumps(kind)})">'
                f'<img src="{src}" alt="{_esc(name)}" loading="lazy">'
                f'<div class="beat-caption">'
                f'<div class="beat-number intro-label">{_esc(badge)}</div>'
                f'<p>{_esc(name)}</p>'
                f'<div class="beat-mood">{_esc(desc[:120])}{"…" if len(desc) > 120 else ""}</div>'
                f'</div></div>'
            )

        section_html = (
            f'<section class="chapter-section" id="{ch["chapter_id"]}">'
            f'<h2 class="chapter-title">{ch["chapter_id"].replace("_", " ").title()}</h2>'
        )
        if beats_html:
            section_html += f'<div class="beats-grid">{"".join(beats_html)}</div>'
        if intros_html:
            section_html += (
                f'<h3 class="intro-section-title">Introductions</h3>'
                f'<div class="beats-grid">{"".join(intros_html)}</div>'
            )
        section_html += '</section>'
        chapter_sections.append(section_html)

    total_images = sum(len(ch.get("images", [])) for ch in chapter_results)

    html = (
        _HTML_HEAD.format(title=_esc(title))
        + f'<header><h1>{_esc(title)}</h1>'
        + f'<p>Illustrated Edition &mdash; {len(chapter_results)} chapter(s) &middot; {total_images} illustration(s)</p></header>'
        + f'<nav>{chapter_links}</nav>'
        + f'<main>{"".join(chapter_sections)}</main>'
        + _HTML_LIGHTBOX
        + "</body></html>"
    )

    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"Gallery written to {index_path}")
    return index_path


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
