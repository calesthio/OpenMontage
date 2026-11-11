"""Convert SketchUp SKP files or ZIP archives containing one SKP to GLB.

Install the optional dependencies once with:
    python -m pip install -r requirements-skp-converter.txt

Conversion itself runs locally, preserves repeated component instances, and
does not use network services.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


class ConversionError(Exception):
    """Raised when the input cannot be converted safely."""


def _extract_skp_from_zip(archive_path: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [
                item for item in archive.infolist()
                if not item.is_dir() and PurePosixPath(item.filename).suffix.lower() == ".skp"
            ]
            if len(members) != 1:
                raise ConversionError(
                    f"Expected exactly one .skp model in {archive_path.name}; found {len(members)}."
                )

            member = members[0]
            if member.flag_bits & 0x1:
                raise ConversionError("Encrypted ZIP archives are not supported.")

            with archive.open(member) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
    except zipfile.BadZipFile as exc:
        raise ConversionError(f"Invalid ZIP archive: {archive_path}") from exc

    return destination


def convert(
    input_path: Path,
    output_path: Path,
    *,
    embed_textures: bool = True,
    overwrite: bool = False,
) -> Path:
    source = input_path.expanduser().resolve()
    target = output_path.expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input file not found: {source}")
    if source.suffix.lower() == ".skb":
        raise ConversionError("A .skb file is only a SketchUp backup; use the .skp model or its ZIP.")
    if source.suffix.lower() not in {".skp", ".zip"}:
        raise ConversionError("Input must be a .skp file or a .zip archive containing one .skp file.")
    if target.suffix.lower() != ".glb":
        raise ConversionError("Output must use the .glb extension.")
    if target.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {target} (pass --force to replace it)")
    metadata_target = target.with_name(f"{target.stem}_metadata.json")
    if metadata_target.exists() and not overwrite:
        raise FileExistsError(
            f"Metadata already exists: {metadata_target} (pass --force to replace it)"
        )

    try:
        from openskp import SkpFile, SkpParseError
        from openskp.export import instanced_glb
    except ImportError as exc:
        raise ConversionError(
            "OpenSKP is not installed. Install the converter dependencies with "
            "`python -m pip install -r requirements-skp-converter.txt`."
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".skp-to-glb-", dir=target.parent) as temp_dir:
        working_dir = Path(temp_dir)
        model_path = (
            _extract_skp_from_zip(source, working_dir / "input.skp")
            if source.suffix.lower() == ".zip"
            else source
        )
        staged_output = working_dir / target.name
        staged_metadata = working_dir / f"{target.stem}_metadata.json"

        print(f"Reading {model_path.name}...", flush=True)
        skp = SkpFile.open(str(model_path))
        try:
            skp.parse()
        except SkpParseError as exc:
            raise ConversionError(f"Could not parse the SketchUp model: {exc}") from exc

        print("Exporting instanced GLB locally...", flush=True)
        instanced_glb.export(skp, str(staged_output), textures=embed_textures)
        if not staged_output.is_file() or staged_output.stat().st_size == 0:
            raise ConversionError("The GLB exporter did not produce a valid output file.")
        if not staged_metadata.is_file():
            raise ConversionError("The GLB exporter did not produce its scene metadata.")

        if target.exists() and not overwrite:
            raise FileExistsError(f"Output already exists: {target} (pass --force to replace it)")
        if metadata_target.exists() and not overwrite:
            raise FileExistsError(
                f"Metadata already exists: {metadata_target} (pass --force to replace it)"
            )
        os.replace(staged_output, target)
        os.replace(staged_metadata, metadata_target)

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a local SketchUp .skp file or ZIP archive to GLB."
    )
    parser.add_argument("input", type=Path, help="Path to a .skp file or a ZIP containing one .skp")
    parser.add_argument("output", type=Path, help="Path for the output .glb file")
    parser.add_argument(
        "--no-textures",
        action="store_true",
        help="Skip embedding texture images to reduce output size",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    args = parser.parse_args(argv)

    try:
        output = convert(
            args.input,
            args.output,
            embed_textures=not args.no_textures,
            overwrite=args.force,
        )
    except (ConversionError, FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    print(f"Created {output} ({output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
