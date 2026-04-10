#!/usr/bin/env python3
"""Import existing memory files into ChromaDB."""
import json
import os
import sys
from pathlib import Path

# Add src to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / "src"))

from chroma_client import chroma_client
from remember_engine import manual_remember


# Memory files to import (excluding sensitive ones)
# Customize this path for your setup
MEMORY_DIR = Path.home() / ".claude" / "projects" / "your-project" / "memory"
EXCLUDE_FILES = {
    "private.md",  # Add sensitive files to exclude
}

# Additional sensitive patterns to exclude from content
EXCLUDE_PATTERNS = [
    "那些图",
    "rating:",
    "NSFW",
]


def should_exclude_file(filename: str) -> bool:
    """Check if file should be excluded."""
    return filename in EXCLUDE_FILES


def should_exclude_content(content: str) -> bool:
    """Check if content contains sensitive patterns."""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in content.lower():
            return True
    return False


def split_into_chunks(content: str, max_chunk_size: int = 2000) -> list[str]:
    """Split content into semantic chunks."""
    chunks = []
    paragraphs = content.split("\n\n")

    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)
        if para_size > max_chunk_size:
            # Split long paragraph by sentences
            sentences = para.replace(". ", ".\n").split("\n")
            for sent in sentences:
                if current_size + len(sent) > max_chunk_size and current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0
                current_chunk.append(sent)
                current_size += len(sent)
        elif current_size + para_size > max_chunk_size:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def import_file(filepath: Path) -> int:
    """Import a single memory file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading {filepath}: {e}", file=sys.stderr)
        return 0

    if should_exclude_content(content):
        print(f"  Skipping (sensitive content): {filepath.name}")
        return 0

    chunks = split_into_chunks(content)
    imported = 0

    for chunk in chunks:
        if len(chunk.strip()) < 50:  # Skip too short chunks
            continue
        try:
            if manual_remember(chunk):
                imported += 1
        except Exception as e:
            print(f"  Error importing chunk: {e}", file=sys.stderr)

    return imported


def main():
    """Main import function."""
    print("=" * 60)
    print("Memory System - Import existing memory files")
    print("=" * 60)

    if not MEMORY_DIR.exists():
        print(f"Error: Memory directory not found: {MEMORY_DIR}")
        print("Please update MEMORY_DIR in this script to your memory files location.")
        sys.exit(1)

    # Initialize ChromaDB
    print("\n[1/3] Initializing ChromaDB...")
    _ = chroma_client.collection
    print("  ChromaDB initialized")

    # Find files to import
    print(f"\n[2/3] Scanning memory files: {MEMORY_DIR}")
    files = list(MEMORY_DIR.glob("*.md"))
    if not files:
        print("  No .md files found")
        sys.exit(0)

    excluded = [f for f in files if should_exclude_file(f.name)]
    to_import = [f for f in files if not should_exclude_file(f.name)]

    print(f"  Found {len(files)} .md files")
    if excluded:
        print(f"  Excluding {len(excluded)} sensitive files: {[f.name for f in excluded]}")
    print(f"  Will import {len(to_import)} files")

    # Import files
    print("\n[3/3] Importing memories...")
    total_imported = 0
    for filepath in to_import:
        print(f"  Importing: {filepath.name}...", end=" ", flush=True)
        count = import_file(filepath)
        print(f"Imported {count} memories")
        total_imported += count

    print(f"\nDone! Imported {total_imported} memories to ChromaDB.")
    print("=" * 60)


if __name__ == "__main__":
    main()
