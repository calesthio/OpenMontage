"""Blender-side deterministic world builder used by ``blender_world``.

No creative decisions live here: palette, density, asset choices, regions,
paths, water, camera, and lighting arrive in the JSON world specification.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.noise import fractal, hetero_terrain, noise_vector, seed_set


def args_after_separator() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--start-frame", type=int)
    parser.add_argument("--end-frame", type=int)
    parser.add_argument("--frame", type=int)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def material(name: str, color: list[float], roughness: float = 0.7, metallic: float = 0.0, emission: float = 0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color[:3], color[3] if len(color) > 3 else 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = mat.diffuse_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = mat.diffuse_color
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def terrain_height(x: float, y: float, spec: dict) -> float:
    terrain = spec.get("terrain", {})
    scale = float(terrain.get("height_scale", 16.0))
    frequency = float(terrain.get("frequency", 0.018))
    base = hetero_terrain(Vector((x * frequency, y * frequency, 0)), 1.0, 2.0, 5.0, 0.7)
    detail = fractal(Vector((x * frequency * 4.2, y * frequency * 4.2, 4.3)), 1.1, 2.0, 3.0)
    height = (base - 0.65) * scale + detail * scale * 0.12
    for region in spec.get("regions", []):
        cx, cy = region.get("center", [0, 0])[:2]
        radius = max(1.0, float(region.get("radius", 40)))
        distance = math.hypot(x - cx, y - cy)
        influence = max(0.0, 1.0 - distance / radius)
        influence = influence * influence * (3.0 - 2.0 * influence)
        height += float(region.get("height_offset", 0)) * influence
        if region.get("flatten") is not None:
            target = float(region["flatten"])
            strength = float(region.get("flatten_strength", 0.75)) * influence
            height = height * (1.0 - strength) + target * strength
    return height


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def build_terrain(spec: dict):
    terrain = spec.get("terrain", {})
    size = float(terrain.get("size", 240))
    resolution = max(32, min(320, int(terrain.get("resolution", 180))))
    vertices = []
    faces = []
    for iy in range(resolution):
        y = -size / 2 + size * iy / (resolution - 1)
        for ix in range(resolution):
            x = -size / 2 + size * ix / (resolution - 1)
            vertices.append((x, y, terrain_height(x, y, spec)))
    for iy in range(resolution - 1):
        for ix in range(resolution - 1):
            a = iy * resolution + ix
            faces.append((a, a + 1, a + resolution + 1, a + resolution))
    mesh = bpy.data.meshes.new("WorldTerrainMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("WorldTerrain", mesh)
    bpy.context.collection.objects.link(obj)
    palette = terrain.get("palette", [[0.11, 0.28, 0.08, 1], [0.28, 0.45, 0.10, 1], [0.35, 0.28, 0.16, 1]])
    mats = [material(f"Terrain-{index}", list(color), 0.92) for index, color in enumerate(palette)]
    region_material_start = len(mats)
    for region in spec.get("regions", []):
        color = region.get("color")
        if color:
            mats.append(material(f"Region-{region.get('id', len(mats))}", list(color), float(region.get("roughness", 0.88))))
    for mat in mats:
        obj.data.materials.append(mat)
    for polygon in mesh.polygons:
        center = sum((mesh.vertices[index].co for index in polygon.vertices), Vector()) / len(polygon.vertices)
        z = center.z
        normal_z = polygon.normal.z
        region_choice = None
        region_strength = 0.0
        for region_index, region in enumerate(spec.get("regions", [])):
            if not region.get("color"):
                continue
            cx, cy = region.get("center", [0, 0])[:2]
            radius = max(1.0, float(region.get("radius", 40)))
            strength = max(0.0, 1.0 - math.hypot(center.x - cx, center.y - cy) / radius)
            if strength > region_strength:
                region_choice = region_index
                region_strength = strength
        if normal_z < 0.67:
            polygon.material_index = min(2, len(palette) - 1)
        elif region_choice is not None and region_strength > 0.18:
            polygon.material_index = region_material_start + region_choice
        else:
            polygon.material_index = 1 if z > 4.0 and len(palette) > 1 else 0
    bevel = obj.modifiers.new("Terrain micro bevel", "BEVEL")
    bevel.width = 0.18
    bevel.segments = 2
    return obj


def make_ribbon(name: str, points: list[list[float]], width: float, mat, z_offset: float = 0.25):
    """Build a flat terrain-following ribbon, avoiding tube-like curve bevels."""
    vertices = []
    faces = []
    half_width = width / 2.0
    for index, source in enumerate(points):
        x, y = source[:2]
        previous = points[max(0, index - 1)]
        following = points[min(len(points) - 1, index + 1)]
        dx = float(following[0]) - float(previous[0])
        dy = float(following[1]) - float(previous[1])
        length = max(0.001, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        for side in (-1.0, 1.0):
            vx, vy = x + nx * half_width * side, y + ny * half_width * side
            vz = source[2] if len(source) > 2 else terrain_height(vx, vy, WORLD_SPEC) + z_offset
            vertices.append((vx, vy, vz))
        if index:
            base = index * 2
            faces.append((base - 2, base, base + 1, base - 1))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new(f"{name} edge softness", "BEVEL")
    bevel.width = min(0.22, width * 0.03)
    bevel.segments = 2
    return obj


def import_asset_collection(path: Path, asset_id: str):
    before = set(bpy.context.scene.objects)
    if path.suffix.lower() in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif path.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif path.suffix.lower() == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise ValueError(f"Unsupported asset format: {path}")
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    collection = bpy.data.collections.new(f"ASSET::{asset_id}")
    bpy.context.scene.collection.children.link(collection)
    for obj in imported:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        if obj.type == "MESH":
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
    # Keep the source collection available for collection instances without
    # rendering its authoring copy at the origin.
    bpy.context.scene.collection.children.unlink(collection)
    z_values = []
    for obj in imported:
        if obj.type == "MESH":
            z_values.extend((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)
    source_height = max(z_values) - min(z_values) if z_values else 1.0
    source_floor = min(z_values) if z_values else 0.0
    return collection, max(0.001, source_height), source_floor


def scatter_assets(spec: dict):
    rng = random.Random(int(spec.get("seed", 1)))
    report = {"asset_sources": 0, "instances": 0, "missing_assets": []}
    for asset in spec.get("assets", []):
        path = Path(asset["path"]).expanduser().resolve()
        if not path.is_file():
            report["missing_assets"].append(str(path))
            continue
        asset_id = str(asset.get("id") or path.stem)
        collection, source_height, source_floor = import_asset_collection(path, asset_id)
        target_height = float(asset.get("target_height", source_height))
        normalization = target_height / source_height
        report["asset_sources"] += 1
        placements = list(asset.get("placements") or [])
        if not placements:
            center = asset.get("center", [0, 0])
            radius = float(asset.get("radius", 30))
            count = int(asset.get("count", 1))
            exclusions = list(asset.get("exclusion_zones") or [])
            attempts = 0
            while len(placements) < count and attempts < count * 24:
                attempts += 1
                angle = rng.random() * math.tau
                distance = radius * math.sqrt(rng.random())
                x = center[0] + math.cos(angle) * distance
                y = center[1] + math.sin(angle) * distance
                if any(
                    math.hypot(x - zone.get("center", [0, 0])[0], y - zone.get("center", [0, 0])[1])
                    < float(zone.get("radius", 0))
                    for zone in exclusions
                ):
                    continue
                placements.append({
                    "position": [x, y],
                    "rotation": rng.random() * math.tau,
                    "scale": rng.uniform(float(asset.get("scale_min", 1)), float(asset.get("scale_max", asset.get("scale_min", 1)))),
                })
        for index, placement in enumerate(placements):
            x, y = placement.get("position", [0, 0])[:2]
            z = terrain_height(float(x), float(y), spec) + float(placement.get("z_offset", 0))
            instance = bpy.data.objects.new(f"{asset_id}-{index:03d}", None)
            instance.instance_type = "COLLECTION"
            instance.instance_collection = collection
            instance.location = (x, y, z)
            if placement.get("rotation_euler_degrees") is not None:
                instance.rotation_euler = [math.radians(float(value)) for value in placement["rotation_euler_degrees"]]
            else:
                instance.rotation_euler[2] = float(placement.get("rotation", 0))
            scale = placement.get("scale", 1)
            if isinstance(scale, list):
                instance.scale = [component * normalization for component in scale]
                instance.location.z = z - source_floor * instance.scale.z
            else:
                effective_scale = scale * normalization
                instance.scale = (effective_scale, effective_scale, effective_scale)
                instance.location.z = z - source_floor * effective_scale
            visible_from = placement.get("visible_from_seconds", asset.get("visible_from_seconds"))
            visible_until = placement.get("visible_until_seconds", asset.get("visible_until_seconds"))
            if visible_from is not None:
                reveal_frame = max(1, round(float(visible_from) * int(spec.get("fps", 30))))
                instance.hide_render = True
                instance.hide_viewport = True
                instance.keyframe_insert("hide_render", frame=max(1, reveal_frame - 1))
                instance.keyframe_insert("hide_viewport", frame=max(1, reveal_frame - 1))
                instance.hide_render = False
                instance.hide_viewport = False
                instance.keyframe_insert("hide_render", frame=reveal_frame)
                instance.keyframe_insert("hide_viewport", frame=reveal_frame)
            if visible_until is not None:
                hide_frame = max(1, round(float(visible_until) * int(spec.get("fps", 30))))
                instance.hide_render = False
                instance.hide_viewport = False
                instance.keyframe_insert("hide_render", frame=hide_frame)
                instance.keyframe_insert("hide_viewport", frame=hide_frame)
                instance.hide_render = True
                instance.hide_viewport = True
                instance.keyframe_insert("hide_render", frame=hide_frame + 1)
                instance.keyframe_insert("hide_viewport", frame=hide_frame + 1)
            bpy.context.collection.objects.link(instance)
            report["instances"] += 1
    return report


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def setup_camera_and_lights(spec: dict, args: argparse.Namespace):
    camera_spec = spec.get("camera", {})
    camera_data = bpy.data.cameras.new("HeroCamera")
    camera = bpy.data.objects.new("HeroCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = camera_spec.get("position", [105, -125, 95])
    camera_data.lens = float(camera_spec.get("lens", 44))
    camera_data.sensor_width = 36
    target = bpy.data.objects.new("CameraTarget", None)
    target.empty_display_type = "SPHERE"
    target.empty_display_size = 1.0
    target.location = camera_spec.get("target", [0, 0, 3])
    bpy.context.collection.objects.link(target)
    tracking = camera.constraints.new(type="TRACK_TO")
    tracking.target = target
    tracking.track_axis = "TRACK_NEGATIVE_Z"
    tracking.up_axis = "UP_Y"
    bpy.context.scene.camera = camera

    camera.data.lens = float(camera_spec.get("lens", 44))

    for key_index, key in enumerate(camera_spec.get("path", [])):
        frame = 1 + round(float(key["time"]) * args.fps)
        camera.location = key["position"]
        target.location = key["target"]
        if key.get("lens") is not None:
            camera.data.lens = float(key["lens"])
            camera.data.keyframe_insert("lens", frame=frame)
        camera.keyframe_insert("location", frame=frame)
        target.keyframe_insert("location", frame=frame)
    for animated in (camera, target):
        for curve in animated.animation_data.action.fcurves if animated.animation_data and animated.animation_data.action else []:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"

    lighting = spec.get("lighting", {})
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = float(lighting.get("sun_energy", 3.0))
    sun_data.angle = math.radians(float(lighting.get("sun_angle_degrees", 18)))
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = [math.radians(value) for value in lighting.get("sun_rotation_degrees", [35, -28, -32])]
    bpy.context.collection.objects.link(sun)

    area_data = bpy.data.lights.new("SkyFill", "AREA")
    area_data.energy = float(lighting.get("fill_energy", 850))
    area_data.shape = "DISK"
    area_data.size = 70
    area = bpy.data.objects.new("SkyFill", area_data)
    area.location = (-35, -20, 70)
    look_at(area, [0, 0, 0])
    bpy.context.collection.objects.link(area)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = lighting.get("world_color", [0.16, 0.24, 0.34, 1])
    background.inputs["Strength"].default_value = float(lighting.get("world_strength", 0.5))


def setup_title(spec: dict, args: argparse.Namespace):
    title = spec.get("title_card")
    if not title:
        return
    curve = bpy.data.curves.new("FinalTitleText", "FONT")
    curve.body = str(title.get("text", ""))
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = float(title.get("size", 0.62))
    curve.extrude = 0.012
    curve.bevel_depth = 0.004
    text = bpy.data.objects.new("FinalTitle", curve)
    bpy.context.collection.objects.link(text)
    text.parent = bpy.context.scene.camera
    text.location = title.get("camera_local_position", [0, -0.92, -5.2])
    text.rotation_euler = (0, 0, 0)
    text.data.materials.append(material("FinalTitleGold", title.get("color", [0.95, 0.68, 0.24, 1]), 0.38, 0.05, 0.12))
    start_frame = round(float(title.get("start_seconds", 58.0)) * args.fps)
    text.hide_render = True
    text.hide_viewport = True
    text.keyframe_insert("hide_render", frame=max(1, start_frame - 1))
    text.keyframe_insert("hide_viewport", frame=max(1, start_frame - 1))
    text.hide_render = False
    text.hide_viewport = False
    text.keyframe_insert("hide_render", frame=start_frame)
    text.keyframe_insert("hide_viewport", frame=start_frame)


def setup_render(args: argparse.Namespace):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = args.samples
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.fps = args.fps
    scene.frame_start = args.start_frame or 1
    scene.frame_end = args.end_frame or max(1, round(args.duration * args.fps))
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.filepath = args.output


def build(spec: dict, args: argparse.Namespace):
    global WORLD_SPEC
    WORLD_SPEC = spec
    clear_scene()
    seed_set(int(spec.get("seed", 1)))
    build_terrain(spec)
    water = spec.get("water")
    if water:
        water_mat = material("Water", water.get("color", [0.03, 0.30, 0.48, 0.82]), 0.13, 0.05)
        make_ribbon("River", water.get("points", [[-90, -20], [0, 0], [90, 25]]), float(water.get("width", 5)), water_mat, float(water.get("z_offset", 0.6)))
    path_spec = spec.get("path")
    if path_spec:
        path_mat = material("Path", path_spec.get("color", [0.55, 0.36, 0.14, 1]), 0.95)
        make_ribbon("Path", path_spec.get("points", []), float(path_spec.get("width", 2.2)), path_mat, float(path_spec.get("z_offset", 0.32)))
    report = scatter_assets(spec)
    setup_camera_and_lights(spec, args)
    setup_title(spec, args)
    setup_render(args)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    Path(args.blend).with_suffix(".report.json").write_text(json.dumps({
        "version": "1.0", "engine": "BLENDER_EEVEE_NEXT", "seed": spec.get("seed"), **report,
    }, indent=2), encoding="utf-8")
    return report


def main():
    args = args_after_separator()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    report = build(spec, args)
    if args.operation == "render_still":
        bpy.context.scene.frame_set(args.frame or 1)
        bpy.context.scene.render.filepath = args.output
        bpy.ops.render.render(write_still=True)
    elif args.operation == "render_animation":
        bpy.context.scene.render.filepath = args.output
        bpy.ops.render.render(animation=True)
    print("OPENMONTAGE_WORLD_REPORT=" + json.dumps(report, sort_keys=True))


WORLD_SPEC = {}
main()
