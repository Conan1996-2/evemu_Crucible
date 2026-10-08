#!/usr/bin/env python3

import gzip
import shutil
import tempfile
from pathlib import Path

# --- CONFIG ---
SOURCE_DIR = Path.cwd()

REMOVE_TEXT = [
    b"PAGE_CHECKSUM=0",
    b"TRANSACTIONAL=0",
]


def clean_sql_file(file_path):
    """Remove unwanted text from a SQL file."""
    with open(file_path, "rb") as f:
        content = f.read()

    original_content = content

    for text in REMOVE_TEXT:
        content = content.replace(text, b"")

    if content != original_content:
        with open(file_path, "wb") as f:
            f.write(content)

    return content != original_content


def process_file(file_path, temp_root):
    """Process a SQL file or a gzip-compressed SQL file."""
    is_gz = file_path.suffix.lower() == ".gz"

    # Only process SQL files and compressed SQL files.
    if is_gz:
        if not file_path.name.lower().endswith(".sql.gz"):
            return
        relative_path = file_path.relative_to(SOURCE_DIR)
        temp_file = temp_root / relative_path.with_suffix("")
    else:
        if file_path.suffix.lower() != ".sql":
            return
        relative_path = file_path.relative_to(SOURCE_DIR)
        temp_file = temp_root / relative_path

    temp_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Extract compressed files or copy ordinary SQL files.
        if is_gz:
            with gzip.open(file_path, "rb") as src:
                with open(temp_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(file_path, temp_file)

        changed = clean_sql_file(temp_file)

        if is_gz:
            # Build the replacement gzip before deleting the original.
            replacement = temp_file.with_name(temp_file.name + ".gz.tmp")

            with open(temp_file, "rb") as src:
                with gzip.open(replacement, "wb") as dst:
                    shutil.copyfileobj(src, dst)

            # Verify the replacement can be decompressed.
            with gzip.open(replacement, "rb") as check:
                while check.read(1024 * 1024):
                    pass

            replacement_final = temp_file.with_name(temp_file.name + ".gz")

            # The replacement is in the temporary directory.
            # Copy it beside the original, then replace the original atomically.
            staged_original = file_path.with_name(file_path.name + ".tmp")

            try:
                shutil.copy2(replacement, staged_original)
                staged_original.replace(file_path)
            except Exception:
                if staged_original.exists():
                    staged_original.unlink()
                raise

        else:
            # Replace the ordinary SQL file only after processing succeeds.
            staged_original = file_path.with_name(file_path.name + ".tmp")
            shutil.copy2(temp_file, staged_original)
            staged_original.replace(file_path)

        status = "modified" if changed else "unchanged"
        print(f"[{status}] {file_path}")

    except Exception as exc:
        print(f"[ERROR] {file_path}: {exc}")


def main():
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"Directory does not exist: {SOURCE_DIR}")

    # Create a separate temporary workspace outside the source directory.
    with tempfile.TemporaryDirectory(prefix="sql_cleaner_") as temp_dir:
        temp_root = Path(temp_dir)

        # Collect paths before processing so the scan isn't affected by
        # temporary files created alongside the originals.
        files = sorted(
            p for p in SOURCE_DIR.rglob("*")
            if p.is_file()
            and not p.name.endswith(".tmp")
            and (
                p.suffix.lower() == ".sql"
                or p.name.lower().endswith(".sql.gz")
            )
        )

        print(f"Found {len(files)} SQL files.")

        for file_path in files:
            process_file(file_path, temp_root)

    print("Done. Temporary files have been cleaned up.")


if __name__ == "__main__":
    main()
