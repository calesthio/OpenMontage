import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.181.2/+esm";
import { GLTFLoader } from "https://cdn.jsdelivr.net/npm/three@0.181.2/examples/jsm/loaders/GLTFLoader.js";
import { WORLD_SPEC } from "./world-spec.js";
import { ASSET_CATALOG } from "./asset-catalog.js";

const root = document.getElementById("world-root");
const canvas = document.getElementById("world-canvas");
const status = document.getElementById("world-status");
const regionName = document.getElementById("world-region-name");
const timecode = document.getElementById("world-timecode");
const altitude = document.getElementById("world-altitude");
const renderMode = root.dataset.renderMode || "cinematic";
const width = Number(root.dataset.width || canvas.width || 1920);
const height = Number(root.dataset.height || canvas.height || 1080);
const qualityTier = window.__WORLD_QUALITY_TIER__ || "blockout";

function mulberry32(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(text) {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }
function smoothstep(value) { const t = clamp(value, 0, 1); return t * t * (3 - 2 * t); }

function regionWeights(nx, nz) {
  const raw = WORLD_SPEC.regions.map((region) => {
    const dx = nx - region.center[0];
    const dz = nz - region.center[1];
    const distance = Math.hypot(dx, dz) / Math.max(0.05, region.radius);
    const softness = Math.max(0.02, region.blend_width);
    return Math.max(0.00001, Math.exp(-Math.pow(Math.max(0, distance - 0.05), 2) / (softness * 2.8)));
  });
  const total = raw.reduce((sum, value) => sum + value, 0) || 1;
  return raw.map((value) => value / total);
}

function landform(kind, dx, dz, distance) {
  if (kind === "peak") return Math.pow(Math.max(0, 1 - distance), 2.2);
  if (kind === "ridge") return Math.max(0, 1 - Math.abs(dx * 1.8 + Math.sin(dz * 5) * 0.16));
  if (kind === "dune") return (Math.sin((dx + dz * 0.25) * 18) + 1) * 0.24;
  if (kind === "terrace") return Math.floor(Math.max(0, 1 - distance) * 5) / 5;
  if (kind === "basin") return -Math.pow(Math.max(0, 1 - distance), 1.7);
  if (kind === "canyon") return -Math.pow(Math.max(0, 1 - Math.abs(dx + Math.sin(dz * 7) * 0.1)), 2);
  return 0;
}

function heightAt(x, z) {
  const half = WORLD_SPEC.world.size / 2;
  const nx = x / half;
  const nz = z / half;
  const weights = regionWeights(nx, nz);
  const seed = WORLD_SPEC.seed * 0.01337;
  let elevation = 0;
  WORLD_SPEC.regions.forEach((region, index) => {
    const frequency = region.frequency;
    const noise = (
      Math.sin((nx * 3.1 + seed + index) * frequency * Math.PI)
      + Math.cos((nz * 2.7 - seed * 0.7 + index) * frequency * Math.PI)
      + 0.5 * Math.sin((nx + nz) * frequency * 7.3 + seed * 3 + index)
    ) / 2.5;
    const dx = nx - region.center[0];
    const dz = nz - region.center[1];
    const distance = Math.hypot(dx, dz) / Math.max(0.05, region.radius);
    elevation += weights[index] * (
      region.base_elevation + region.amplitude * (noise * 0.48 + landform(region.landform, dx, dz, distance) * 0.8)
    );
  });
  return elevation * WORLD_SPEC.world.elevation_scale;
}

function dominantRegion(x, z) {
  const half = WORLD_SPEC.world.size / 2;
  const weights = regionWeights(x / half, z / half);
  let index = 0;
  for (let i = 1; i < weights.length; i += 1) if (weights[i] > weights[index]) index = i;
  return { region: WORLD_SPEC.regions[index], weight: weights[index] };
}

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
renderer.setSize(width, height, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = renderMode === "cinematic" ? 1.05 : 1;
renderer.shadowMap.enabled = renderMode === "cinematic";
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(WORLD_SPEC.atmosphere.sky_color);
if (renderMode === "cinematic" && WORLD_SPEC.atmosphere.fog_density > 0) {
  scene.fog = new THREE.FogExp2(WORLD_SPEC.atmosphere.fog_color, WORLD_SPEC.atmosphere.fog_density);
}

const camera = new THREE.PerspectiveCamera(45, width / height, 0.2, WORLD_SPEC.world.size * 4);
const terrainGroup = new THREE.Group();
terrainGroup.name = "terrain-foundation";
const environmentGroup = new THREE.Group();
environmentGroup.name = "environment-prototypes";
const landmarkGroup = new THREE.Group();
landmarkGroup.name = "regional-landmarks";
scene.add(terrainGroup, environmentGroup, landmarkGroup);

const hemi = new THREE.HemisphereLight(
  WORLD_SPEC.atmosphere.sky_color,
  WORLD_SPEC.atmosphere.ground_color,
  renderMode === "cinematic" ? 1.45 : 2.2,
);
scene.add(hemi);

const sun = new THREE.DirectionalLight(WORLD_SPEC.atmosphere.sun_color, WORLD_SPEC.atmosphere.sun_intensity);
sun.position.fromArray(WORLD_SPEC.atmosphere.sun_position);
sun.castShadow = renderMode === "cinematic";
sun.shadow.mapSize.set(1024, 1024);
const shadowSpan = WORLD_SPEC.world.size * 0.62;
sun.shadow.camera.left = -shadowSpan;
sun.shadow.camera.right = shadowSpan;
sun.shadow.camera.top = shadowSpan;
sun.shadow.camera.bottom = -shadowSpan;
sun.shadow.camera.near = 1;
sun.shadow.camera.far = WORLD_SPEC.world.size * 3;
sun.shadow.bias = -0.0003;
sun.shadow.normalBias = 0.035;
scene.add(sun);

const terrainGeometry = new THREE.PlaneGeometry(
  WORLD_SPEC.world.size,
  WORLD_SPEC.world.size,
  WORLD_SPEC.world.resolution,
  WORLD_SPEC.world.resolution,
);
terrainGeometry.rotateX(-Math.PI / 2);
const position = terrainGeometry.attributes.position;
const colors = new Float32Array(position.count * 3);
const color = new THREE.Color();
const mixed = new THREE.Color();
for (let index = 0; index < position.count; index += 1) {
  const x = position.getX(index);
  const z = position.getZ(index);
  position.setY(index, heightAt(x, z));
  const weights = regionWeights(x / (WORLD_SPEC.world.size / 2), z / (WORLD_SPEC.world.size / 2));
  mixed.setRGB(0, 0, 0);
  WORLD_SPEC.regions.forEach((region, regionIndex) => {
    color.set(renderMode === "semantic" ? region.accent_color : region.color);
    mixed.r += color.r * weights[regionIndex];
    mixed.g += color.g * weights[regionIndex];
    mixed.b += color.b * weights[regionIndex];
  });
  colors[index * 3] = mixed.r;
  colors[index * 3 + 1] = mixed.g;
  colors[index * 3 + 2] = mixed.b;
}
position.needsUpdate = true;
terrainGeometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
terrainGeometry.computeVertexNormals();
terrainGeometry.computeBoundingSphere();

const terrainMaterial = renderMode === "wireframe"
  ? new THREE.MeshBasicMaterial({ color: 0x8de8ff, wireframe: true, transparent: true, opacity: 0.82 })
  : new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0.02, flatShading: false });
const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
terrain.name = "semantic-terrain";
terrain.receiveShadow = renderMode === "cinematic";
terrainGroup.add(terrain);

let water = null;
if (renderMode !== "wireframe") {
  const waterGeometry = new THREE.PlaneGeometry(WORLD_SPEC.world.size * 1.08, WORLD_SPEC.world.size * 1.08, 1, 1);
  waterGeometry.rotateX(-Math.PI / 2);
  const waterMaterial = new THREE.MeshPhysicalMaterial({
    color: renderMode === "semantic" ? 0x1765a3 : 0x143d55,
    roughness: 0.22,
    metalness: 0.08,
    transmission: renderMode === "cinematic" ? 0.22 : 0,
    transparent: true,
    opacity: renderMode === "cinematic" ? 0.76 : 0.9,
    depthWrite: false,
  });
  water = new THREE.Mesh(waterGeometry, waterMaterial);
  water.name = "global-water-plane";
  water.position.y = WORLD_SPEC.world.water_level;
  terrainGroup.add(water);
}

const instanceStats = { tree: 0, rock: 0, crystal: 0 };
function slopeAt(x, z) {
  const step = 0.65;
  return Math.abs(heightAt(x + step, z) - heightAt(x - step, z))
    + Math.abs(heightAt(x, z + step) - heightAt(x, z - step));
}

function scatterPoints(region, count, salt) {
  const random = mulberry32((WORLD_SPEC.seed ^ hashString(region.id + salt)) >>> 0);
  const points = [];
  const half = WORLD_SPEC.world.size / 2;
  for (let index = 0; index < count; index += 1) {
    let accepted = null;
    for (let attempt = 0; attempt < 14; attempt += 1) {
      const angle = random() * Math.PI * 2;
      const radius = Math.sqrt(random()) * region.radius * half;
      const x = region.center[0] * half + Math.cos(angle) * radius;
      const z = region.center[1] * half + Math.sin(angle) * radius;
      const dominant = dominantRegion(x, z);
      if (dominant.region.id !== region.id || dominant.weight < 0.34) continue;
      if (slopeAt(x, z) > region.slope_limit) continue;
      accepted = { x, z, y: heightAt(x, z), rotation: random() * Math.PI * 2, scale: 0.72 + random() * 0.72 };
      break;
    }
    if (accepted) points.push(accepted);
  }
  return points;
}

function makeInstanced(geometry, material, points, transform) {
  if (!points.length) return null;
  const mesh = new THREE.InstancedMesh(geometry, material, points.length);
  const dummy = new THREE.Object3D();
  points.forEach((point, index) => {
    transform(dummy, point, index);
    dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.castShadow = renderMode === "cinematic";
  mesh.receiveShadow = renderMode === "cinematic";
  environmentGroup.add(mesh);
  return mesh;
}

const catalogModels = new Map();
for (const catalog of ASSET_CATALOG.catalogs || []) {
  for (const model of catalog.models || []) {
    catalogModels.set(`${catalog.catalog_id}:${model.id}`, model.runtime_path);
  }
}

async function loadProductionPalette() {
  if (qualityTier !== "production") return;
  const loader = new GLTFLoader();
  const prototypes = new Map();
  const palette = WORLD_SPEC.asset_palette || [];
  await Promise.all(palette.map(async (entry) => {
    const key = `${entry.catalog_id}:${entry.model_id}`;
    const path = catalogModels.get(key);
    if (!path || prototypes.has(key)) return;
    const gltf = await loader.loadAsync(path);
    gltf.scene.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = renderMode === "cinematic";
      node.receiveShadow = renderMode === "cinematic";
      if (node.material) node.material.envMapIntensity = 0.8;
    });
    prototypes.set(key, gltf.scene);
  }));

  palette.forEach((entry, entryIndex) => {
    const prototype = prototypes.get(`${entry.catalog_id}:${entry.model_id}`);
    if (!prototype) return;
    const region = WORLD_SPEC.regions.find((item) => item.id === entry.region_id) || WORLD_SPEC.regions[entryIndex % WORLD_SPEC.regions.length];
    const points = scatterPoints(region, Math.min(180, Math.max(1, Number(entry.count || 12))), `catalog-${entry.id || entryIndex}`);
    points.forEach((point, pointIndex) => {
      const clone = prototype.clone(true);
      const random = mulberry32((WORLD_SPEC.seed ^ hashString(`${entry.id || entryIndex}:${pointIndex}`)) >>> 0);
      const scaleRange = Array.isArray(entry.scale_range) ? entry.scale_range : [0.8, 1.4];
      const scale = THREE.MathUtils.lerp(Number(scaleRange[0]), Number(scaleRange[1]), random()) * Number(entry.base_scale || 1);
      clone.position.set(point.x, point.y + Number(entry.y_offset || 0), point.z);
      clone.rotation.y = random() * Math.PI * 2;
      clone.scale.setScalar(scale);
      clone.name = `catalog-${entry.id || entryIndex}-${pointIndex}`;
      environmentGroup.add(clone);
    });
  });
}

WORLD_SPEC.regions.forEach((region) => {
  const regionColor = new THREE.Color(renderMode === "semantic" ? region.accent_color : region.color);
  const accentColor = new THREE.Color(region.accent_color);

  const rocks = scatterPoints(region, region.scatter.rock, "rock");
  instanceStats.rock += rocks.length;
  makeInstanced(
    new THREE.DodecahedronGeometry(0.72, 0),
    new THREE.MeshStandardMaterial({ color: regionColor.clone().multiplyScalar(0.72), roughness: 0.95, wireframe: renderMode === "wireframe" }),
    rocks,
    (dummy, point) => {
      dummy.position.set(point.x, point.y + 0.42 * point.scale, point.z);
      dummy.rotation.set(point.rotation * 0.17, point.rotation, point.rotation * 0.11);
      dummy.scale.set(point.scale * 1.1, point.scale * 0.72, point.scale);
    },
  );

  const crystals = scatterPoints(region, region.scatter.crystal, "crystal");
  instanceStats.crystal += crystals.length;
  makeInstanced(
    new THREE.OctahedronGeometry(0.72, 0),
    new THREE.MeshStandardMaterial({ color: accentColor, emissive: accentColor, emissiveIntensity: renderMode === "cinematic" ? 1.7 : 0.25, roughness: 0.28, metalness: 0.28, wireframe: renderMode === "wireframe" }),
    crystals,
    (dummy, point) => {
      dummy.position.set(point.x, point.y + 0.82 * point.scale, point.z);
      dummy.rotation.set(0.08, point.rotation, 0.05);
      dummy.scale.set(point.scale * 0.46, point.scale * 1.75, point.scale * 0.46);
    },
  );

  const trees = scatterPoints(region, region.scatter.tree, "tree");
  instanceStats.tree += trees.length;
  const trunkMaterial = new THREE.MeshStandardMaterial({ color: renderMode === "semantic" ? region.accent_color : 0x3e2b22, roughness: 1, wireframe: renderMode === "wireframe" });
  const canopyMaterial = new THREE.MeshStandardMaterial({ color: regionColor.clone().offsetHSL(0, 0.08, 0.09), roughness: 0.94, wireframe: renderMode === "wireframe" });
  makeInstanced(new THREE.CylinderGeometry(0.16, 0.23, 1.75, 6), trunkMaterial, trees, (dummy, point) => {
    dummy.position.set(point.x, point.y + 0.88 * point.scale, point.z);
    dummy.rotation.set(0, point.rotation, 0);
    dummy.scale.setScalar(point.scale);
  });
  makeInstanced(new THREE.ConeGeometry(0.92, 2.4, 7), canopyMaterial, trees, (dummy, point) => {
    dummy.position.set(point.x, point.y + 2.35 * point.scale, point.z);
    dummy.rotation.set(0, point.rotation, 0);
    dummy.scale.setScalar(point.scale);
  });
});

function materialPair(landmark) {
  const base = new THREE.Color(renderMode === "semantic" ? landmark.accent_color : landmark.color);
  const accent = new THREE.Color(landmark.accent_color);
  return {
    base: new THREE.MeshStandardMaterial({ color: base, roughness: 0.72, metalness: 0.18, wireframe: renderMode === "wireframe" }),
    accent: new THREE.MeshStandardMaterial({ color: accent, emissive: accent, emissiveIntensity: renderMode === "cinematic" ? 1.25 : 0.2, roughness: 0.28, metalness: 0.38, wireframe: renderMode === "wireframe" }),
  };
}

function addMesh(group, geometry, material, positionValue, scaleValue = [1, 1, 1], rotationValue = [0, 0, 0]) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(...positionValue);
  mesh.scale.set(...scaleValue);
  mesh.rotation.set(...rotationValue);
  mesh.castShadow = renderMode === "cinematic";
  mesh.receiveShadow = renderMode === "cinematic";
  group.add(mesh);
  return mesh;
}

function buildLandmark(landmark) {
  const group = new THREE.Group();
  group.name = landmark.id;
  const materials = materialPair(landmark);
  const s = landmark.scale;
  const random = mulberry32((WORLD_SPEC.seed ^ hashString(landmark.id)) >>> 0);

  if (landmark.type === "arch") {
    addMesh(group, new THREE.BoxGeometry(1, 1, 1), materials.base, [-0.72 * s, 0.7 * s, 0], [0.34 * s, 1.4 * s, 0.42 * s]);
    addMesh(group, new THREE.BoxGeometry(1, 1, 1), materials.base, [0.72 * s, 0.7 * s, 0], [0.34 * s, 1.4 * s, 0.42 * s]);
    addMesh(group, new THREE.BoxGeometry(1, 1, 1), materials.accent, [0, 1.48 * s, 0], [1.06 * s, 0.24 * s, 0.42 * s]);
  } else if (landmark.type === "tower") {
    addMesh(group, new THREE.CylinderGeometry(0.52, 0.68, 2.4, 8), materials.base, [0, 1.2 * s, 0], [s, s, s]);
    addMesh(group, new THREE.TorusGeometry(0.68, 0.09, 8, 24), materials.accent, [0, 2.08 * s, 0], [s, s, s], [Math.PI / 2, 0, 0]);
    addMesh(group, new THREE.ConeGeometry(0.72, 1.2, 8), materials.accent, [0, 2.72 * s, 0], [s, s, s]);
  } else if (landmark.type === "ruin") {
    for (let i = 0; i < 7; i += 1) {
      const angle = (i / 7) * Math.PI * 2 + random() * 0.2;
      const radius = s * (0.55 + random() * 0.45);
      const h = s * (0.45 + random() * 1.1);
      addMesh(group, new THREE.BoxGeometry(1, 1, 1), i === 3 ? materials.accent : materials.base, [Math.cos(angle) * radius, h / 2, Math.sin(angle) * radius], [s * 0.25, h, s * 0.25], [0, random() * Math.PI, (random() - 0.5) * 0.14]);
    }
  } else if (landmark.type === "crystal") {
    for (let i = 0; i < 5; i += 1) {
      const angle = (i / 5) * Math.PI * 2;
      const localScale = s * (i === 0 ? 1.45 : 0.62 + random() * 0.35);
      addMesh(group, new THREE.OctahedronGeometry(0.55, 0), materials.accent, [Math.cos(angle) * s * 0.42, localScale * 0.62, Math.sin(angle) * s * 0.42], [localScale * 0.44, localScale * 1.25, localScale * 0.44], [0.06, angle, 0.04]);
    }
  } else if (landmark.type === "settlement") {
    for (let i = 0; i < 9; i += 1) {
      const angle = (i / 9) * Math.PI * 2 + random() * 0.3;
      const radius = s * (0.35 + random() * 1.05);
      const h = s * (0.24 + random() * 0.52);
      addMesh(group, new THREE.CylinderGeometry(0.42, 0.56, 1, 6), materials.base, [Math.cos(angle) * radius, h / 2, Math.sin(angle) * radius], [s * 0.42, h, s * 0.42], [0, angle, 0]);
      addMesh(group, new THREE.ConeGeometry(0.64, 0.7, 6), materials.accent, [Math.cos(angle) * radius, h + s * 0.18, Math.sin(angle) * radius], [s * 0.42, s * 0.42, s * 0.42], [0, angle, 0]);
    }
  } else if (landmark.type === "ring") {
    addMesh(group, new THREE.TorusGeometry(1, 0.12, 12, 64), materials.accent, [0, 1.25 * s, 0], [s, s, s], [0, 0, 0]);
    addMesh(group, new THREE.CylinderGeometry(0.28, 0.48, 1.4, 8), materials.base, [0, 0.7 * s, 0], [s, s, s]);
  } else {
    addMesh(group, new THREE.BoxGeometry(1, 1, 1), materials.base, [0, 0.95 * s, 0], [0.62 * s, 1.9 * s, 0.62 * s], [0.04, 0.35, -0.03]);
    addMesh(group, new THREE.OctahedronGeometry(0.32, 0), materials.accent, [0, 2.08 * s, 0], [s, s, s]);
  }

  const terrainY = heightAt(landmark.position[0], landmark.position[2]);
  group.position.set(landmark.position[0], terrainY + landmark.position[1], landmark.position[2]);
  group.rotation.set(...landmark.rotation);
  landmarkGroup.add(group);
}
if (qualityTier === "blockout") WORLD_SPEC.landmarks.forEach(buildLandmark);

function interpolateVector(left, right, amount) {
  return new THREE.Vector3(
    THREE.MathUtils.lerp(left[0], right[0], amount),
    THREE.MathUtils.lerp(left[1], right[1], amount),
    THREE.MathUtils.lerp(left[2], right[2], amount),
  );
}

function cameraAt(time) {
  const keys = WORLD_SPEC.camera_path;
  if (time <= keys[0].time) return { ...keys[0], positionV: new THREE.Vector3(...keys[0].position), targetV: new THREE.Vector3(...keys[0].target) };
  if (time >= keys[keys.length - 1].time) {
    const key = keys[keys.length - 1];
    return { ...key, positionV: new THREE.Vector3(...key.position), targetV: new THREE.Vector3(...key.target) };
  }
  for (let index = 0; index < keys.length - 1; index += 1) {
    const left = keys[index];
    const right = keys[index + 1];
    if (time >= left.time && time <= right.time) {
      const amount = smoothstep((time - left.time) / Math.max(0.0001, right.time - left.time));
      return {
        label: amount < 0.5 ? left.label : right.label,
        positionV: interpolateVector(left.position, right.position, amount),
        targetV: interpolateVector(left.target, right.target, amount),
        fov: THREE.MathUtils.lerp(left.fov, right.fov, amount),
      };
    }
  }
  const fallback = keys[keys.length - 1];
  return { ...fallback, positionV: new THREE.Vector3(...fallback.position), targetV: new THREE.Vector3(...fallback.target) };
}

function formatTime(value) {
  const minutes = Math.floor(value / 60).toString().padStart(2, "0");
  const seconds = (value % 60).toFixed(1).padStart(4, "0");
  return `${minutes}:${seconds}`;
}

function renderAt(timeValue) {
  const time = Math.max(0, Number(timeValue) || 0);
  const state = cameraAt(time);
  camera.position.copy(state.positionV);
  camera.fov = state.fov;
  camera.updateProjectionMatrix();
  camera.lookAt(state.targetV);

  if (water) water.material.opacity = (renderMode === "cinematic" ? 0.73 : 0.88) + Math.sin(time * 0.42) * 0.035;
  sun.intensity = WORLD_SPEC.atmosphere.sun_intensity * (0.96 + Math.sin(time * 0.09) * 0.04);

  const regionState = dominantRegion(state.targetV.x, state.targetV.z);
  regionName.textContent = state.label || regionState.region.label;
  timecode.textContent = formatTime(time);
  altitude.textContent = camera.position.y.toFixed(1).padStart(5, "0");
  renderer.render(scene, camera);
}

async function finalizeWorld() {
  await loadProductionPalette();
  window.addEventListener("hf-seek", (event) => renderAt(event.detail.time));
  window.__worldRenderAt = renderAt;
  window.__worldGraph = { scene, camera, terrainGroup, environmentGroup, landmarkGroup, instanceStats };
  window.__worldReady = true;
  status.textContent = `WORLD READY · ${WORLD_SPEC.regions.length} REGIONS · ${WORLD_SPEC.landmarks.length} LANDMARKS · ${qualityTier.toUpperCase()}`;
  status.style.opacity = "0";
  renderAt(window.__hfThreeTime || 0);
}

finalizeWorld().catch((error) => {
  window.__worldReady = false;
  window.__worldError = String(error?.stack || error);
  status.textContent = "WORLD ASSET LOAD FAILED";
  console.error(error);
});
