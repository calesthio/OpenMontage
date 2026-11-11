# Local SketchUp to GLB converter

The local converter exports a SketchUp `.skp` model, or a ZIP containing
exactly one `.skp` model, to GLB. Conversion runs locally and preserves
repeated component instances.

## Install

Install the optional parser dependency once:

```powershell
python -m pip install -r requirements-skp-converter.txt
```

After installation, conversion does not require network access.

## Convert

```powershell
python tools/graphics/skp_to_glb.py "path\to\model.zip" "exports\model.glb"
```

You can also pass an extracted `.skp` file directly. ZIP archives must contain
exactly one `.skp`; `.skb` backup files are ignored. Textures are embedded by
default. Pass `--no-textures` to omit them, or `--force` to replace existing
output files.

The converter also writes a sibling `_metadata.json` file with the model's
layers and instance hierarchy. Keep it alongside the GLB when inspecting the
source model's structure.

Run the focused tests with:

```powershell
python -m pytest -q tests/tools/test_skp_to_glb.py
```
