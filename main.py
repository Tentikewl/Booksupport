#!/usr/bin/env python3
"""Book Companion — CLI entry point."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import config


def cmd_ingest(args: argparse.Namespace) -> None:
    from ingest.epub_parser import load_book
    from ingest.chunker import lumberchunk, fallback_chunk
    from rag.entity_extractor import extract_entities_from_chunk
    from rag.passage_indexer import index_chunk
    from rag.vector_store import reset_collections
    from generation.scene_detector import detect_beats

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"File not found: {input_path}")

    if args.transcribe:
        from ingest.whisper_transcriber import transcribe
        txt_path = input_path.with_suffix(".txt")
        transcribe(input_path, txt_path)
        input_path = txt_path

    print(f"Loading {input_path.name}…")
    chapters = load_book(input_path)
    print(f"  Found {len(chapters)} chapter(s)")

    if args.reset:
        print("Resetting vector store…")
        reset_collections()

    chunk_fn = fallback_chunk if args.fallback_chunker else lumberchunk
    chunk_mode = "fallback" if args.fallback_chunker else "LumberChunker"

    title_slug = args.title.replace(" ", "_")
    state_path = config.DATA_DIR / f"{title_slug}_state.json"
    beats_path = config.DATA_DIR / f"{title_slug}_beats.json"
    state: dict = {}
    all_beats: dict = {}

    for chapter_id, chapter_text in chapters.items():
        print(f"\n[{chapter_id}] Chunking with {chunk_mode}…")
        chunks = chunk_fn(chapter_text, chapter_id)
        print(f"  {len(chunks)} chunk(s)")

        chapter_entity_ids: list[str] = []
        for i, chunk in enumerate(chunks):
            print(f"  Extracting entities from chunk {i + 1}/{len(chunks)}…", end="\r")
            new_entities = extract_entities_from_chunk(chunk)
            chunk_entity_ids = [e["id"] for e in new_entities]
            chapter_entity_ids.extend(chunk_entity_ids)
            index_chunk(chunk, chunk_entity_ids)

        unique_entity_ids = list(set(chapter_entity_ids))
        state[chapter_id] = {
            "n_chunks": len(chunks),
            "entity_ids": unique_entity_ids,
        }
        print(f"  Done — {len(unique_entity_ids)} new entities")

        print(f"  Detecting scene beats…")
        beats = detect_beats(chapter_id, chapter_text, unique_entity_ids)
        all_beats[chapter_id] = beats
        print(f"  {len(beats)} beat(s) above visual strength threshold")

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))
    beats_path.write_text(json.dumps(all_beats, indent=2))
    print(f"\nIngest complete. State saved to {state_path}")
    print(f"Scene beats saved to {beats_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    from rag.prompt_composer import compose_prompt
    from generation.image_generator import generate_chapter_images
    from rag.entity_extractor import get_all_entities

    entities = get_all_entities()
    known_ids = [e["id"] for e in entities]

    title_slug = args.title.replace(" ", "_")
    beats_path = config.DATA_DIR / f"{title_slug}_beats.json"
    output_dir = config.OUTPUT_DIR / title_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load pre-detected beats from ingest if available, otherwise detect live
    if beats_path.exists():
        print(f"Loading pre-detected beats from {beats_path}…")
        all_beats: dict = json.loads(beats_path.read_text())
    else:
        from generation.scene_detector import detect_beats
        from ingest.epub_parser import load_book
        if not args.input:
            sys.exit("--input is required when no pre-detected beats file exists for this title.")
        input_path = Path(args.input)
        if not input_path.exists():
            sys.exit(f"File not found: {input_path}")
        print("No beats file found — detecting from book text…")
        chapters = load_book(input_path)
        all_beats = {
            ch_id: detect_beats(ch_id, ch_text, known_ids)
            for ch_id, ch_text in chapters.items()
        }

    chapter_results: list[dict] = []

    for chapter_id, beats in all_beats.items():
        print(f"\n[{chapter_id}] {len(beats)} beat(s) above visual strength threshold")

        if not beats:
            chapter_results.append({"chapter_id": chapter_id, "images": []})
            continue

        prompts = [compose_prompt(beat) for beat in beats]
        print(f"  Generating {len(beats)} image(s)…")
        images = generate_chapter_images(beats, prompts, chapter_id, output_dir)
        chapter_results.append({"chapter_id": chapter_id, "images": images})

    # Save prompt log for inspection
    log_path = output_dir / "prompts.json"
    log_data = [
        {"chapter": ch["chapter_id"], "beats": ch["images"]}
        for ch in chapter_results
    ]
    log_path.write_text(json.dumps(log_data, indent=2, default=str))

    # Build gallery
    from output.gallery_builder import build_gallery
    gallery_path = build_gallery(args.title, chapter_results, entities, output_dir / "gallery")
    print(f"\nDone! Open {gallery_path} in a browser.")


def cmd_extract_only(args: argparse.Namespace) -> None:
    """Run ingestion pipeline without image generation."""
    args.reset = getattr(args, "reset", False)
    args.transcribe = False
    args.fallback_chunker = getattr(args, "fallback_chunker", False)
    cmd_ingest(args)

    from rag.entity_extractor import get_all_entities
    entities = get_all_entities()
    print(f"\n--- Entity Store Summary ({len(entities)} entities) ---")
    for e in sorted(entities, key=lambda x: x.get("appearance_count", 0), reverse=True)[:20]:
        print(f"  [{e['type']:10s}] {e['name']:30s}  (appearances: {e.get('appearance_count', 1)})")


def cmd_full(args: argparse.Namespace) -> None:
    cmd_ingest(args)
    cmd_generate(args)


def cmd_test_image(_args: argparse.Namespace) -> None:
    """Generate a single test image from a hardcoded beat to verify the pipeline."""
    from generation.image_generator import generate_image

    if not config.REPLICATE_API_TOKEN:
        sys.exit("REPLICATE_API_TOKEN is not set. Export it before running test-image.")

    test_prompt = (
        "Grimdark sci-fi illustration, Warhammer 40K aesthetic, hyper-detailed power armour, "
        "cinematic dramatic lighting, digital art, highly detailed\n\n"
        "[SCENE] A lone Space Marine stands at the edge of a shattered rockcrete parapet overlooking "
        "a burning hive city — smoke pillars rising from collapsed spires, tracer fire arcing through "
        "an ash-choked sky, debris and bodies on the ground far below\n\n"
        "[CHARACTERS PRESENT]\n"
        "- Space Marine: towering superhuman warrior in massive cobalt-blue ceramite power armour, "
        "gold aquila emblem on chest, sealed helmet with glowing red eye-lenses, "
        "white chapter pauldron with skull insignia, bolter held two-handed at rest, "
        "cloak tattered and scorched, standing motionless amid the chaos\n\n"
        "[MOOD] foreboding, resolute, grimdark\n\n"
        "[EXCLUDE] Do not show characters not listed above. Do not add background figures."
    )

    output_dir = config.OUTPUT_DIR / "test"
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "test_image.jpg"

    print("Generating test image…")
    print(f"  Prompt length: {len(test_prompt)} chars")
    result = generate_image(test_prompt, dest)
    print(f"  Saved to: {result}")
    print("Test image generation successful.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="book-companion",
        description="Book Companion — Illustrated Edition Generator",
    )
    parser.add_argument("--input", default=None, help="Path to .epub or .txt book file")
    parser.add_argument("--title", default=None, help="Book title (used for output directory)")
    parser.add_argument("--transcribe", action="store_true", help="Transcribe audio input via Whisper first")
    parser.add_argument("--fallback-chunker", action="store_true", dest="fallback_chunker",
                        help="Use simple recursive splitter instead of LumberChunker (cheaper, less accurate)")
    parser.add_argument("--reset", action="store_true", help="Reset vector store before ingesting (fresh run)")
    parser.add_argument(
        "--mode",
        choices=["full", "extract-only", "generate-only", "test-image"],
        default="full",
        help=(
            "full: ingest + generate (default); "
            "extract-only: ingest and build entity store only; "
            "generate-only: generate images from existing entity store; "
            "test-image: generate one hardcoded test image to verify the pipeline"
        ),
    )

    args = parser.parse_args()

    if args.mode == "test-image":
        cmd_test_image(args)
        return

    if not args.title:
        parser.error("--title is required for mode: " + args.mode)
    if not args.input and args.mode != "generate-only":
        parser.error("--input is required for mode: " + args.mode)

    if args.mode == "extract-only":
        cmd_extract_only(args)
    elif args.mode == "generate-only":
        cmd_generate(args)
    else:
        cmd_full(args)


if __name__ == "__main__":
    main()
