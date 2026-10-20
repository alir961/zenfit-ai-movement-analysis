import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { PredictedOverlays } from "./overlays.js";

const DEFAULT_URL = "";

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.body.appendChild(renderer.domElement);
console.log("THREE.REVISION", THREE.REVISION);

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x0b0b0f, 8, 50);

const pmrem = new THREE.PMREMGenerator(renderer);
const envRT = pmrem.fromScene(new RoomEnvironment(), 0.06);
scene.environment = envRT.texture;

const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.01, 500);
camera.position.set(2.8, 1.8, 3.2);

const orbit = new OrbitControls(camera, renderer.domElement);
orbit.target.set(0, 1.0, 0);
orbit.update();

const transformControls = new TransformControls(camera, renderer.domElement);
transformControls.setMode("rotate");
transformControls.setSpace("local");
transformControls.setSize(1.25);
transformControls.addEventListener("dragging-changed", (e) => {
  orbit.enabled = !e.value;
});
transformControls.addEventListener("objectChange", () => {
  if (state.selectedBone) {
    state.selectedBone.updateMatrixWorld(true);
    state.treeDirty = true;
  }
});
const transformControlsHelper = transformControls.getHelper();
transformControlsHelper.traverse((o) => {
  if (o.material) {
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      m.depthTest = false;
      m.depthWrite = false;
      m.toneMapped = false;
    }
  }
  o.renderOrder = 1200;
});
scene.add(transformControlsHelper);

scene.add(new THREE.HemisphereLight(0xffffff, 0x202040, 1.4));
const dir = new THREE.DirectionalLight(0xffffff, 2.2);
dir.position.set(3, 6, 2);
scene.add(dir);

const grid = new THREE.GridHelper(10, 20, 0x444466, 0x222233);
scene.add(grid);

const gizmoLayer = new THREE.Group();
scene.add(gizmoLayer);
const predictedOverlays = new PredictedOverlays(scene);

const ui = {
  tree: document.getElementById("tree"),
  meta: document.getElementById("meta"),
  meshSelect: document.getElementById("skelSelect"),
  toggleSkeleton: document.getElementById("toggleSkeleton"),
  toggleJoints: document.getElementById("toggleJoints"),
  toggleAxes: document.getElementById("toggleAxes"),
  toggleAngles: document.getElementById("toggleAngles"),
  btnTPose: document.getElementById("btnTPose"),
  btnResetBone: document.getElementById("btnResetBone"),
  tcMode: document.getElementById("tcMode"),
  tcSpace: document.getElementById("tcSpace"),
  modeWarn: document.getElementById("modeWarn"),
  drop: document.getElementById("drop")
};

const state = {
  currentRoot: null,
  entries: [],
  selectedEntryIndex: 0,
  currentSkinnedMesh: null,
  currentSkeleton: null,
  rootBone: null,
  pelvisBone: null,
  kinematicRootBone: null,
  selectedBone: null,
  bindPoseCache: new Map(),
  boneLimits: new Map(),
  modelMaxDim: 1,
  footAnchorWorld: null,
  treeDirty: false,
  lastTreeTs: 0,
  skeletonHelper: null,
  jointSpheres: [],
  jointAxes: [],
  selectionMarker: null,
  ikChainLines: [],
  jointGeo: null,
  jointMat: null,
  jointBaseRadius: 0.02
};

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const tmpV = new THREE.Vector3();
const tmpA = new THREE.Vector3();
const tmpB = new THREE.Vector3();

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

function collectBonesByName(skeleton) {
  const map = new Map();
  for (const b of skeleton.bones) map.set(b.name, b);
  return map;
}

function getBoneStrict(skeleton, name) {
  const b = collectBonesByName(skeleton).get(name);
  if (!b) throw new Error(`Bone obligatoire introuvable: ${name}`);
  return b;
}

function findRootBone(skeleton) {
  const roots = skeleton.bones.filter(b => !b.parent || !b.parent.isBone);
  return roots[0] || skeleton.bones[0] || null;
}

function findPelvisBone(skeleton) {
  const byName = collectBonesByName(skeleton);
  for (const n of ["Hip", "Hips", "Pelvis", "pelvis"]) {
    if (byName.has(n)) return byName.get(n);
  }
  return findRootBone(skeleton);
}

function findBoneByAliases(skeleton, aliases) {
  const byName = collectBonesByName(skeleton);
  for (const a of aliases) {
    if (byName.has(a)) return byName.get(a);
  }
  const lowerAliases = aliases.map(a => a.toLowerCase());
  for (const b of skeleton.bones) {
    const n = (b.name || "").toLowerCase();
    if (lowerAliases.some(a => n.includes(a.toLowerCase()))) return b;
  }
  return null;
}

function buildHipToHeadPath(hipBone, headBone) {
  if (!hipBone || !headBone) return [];
  const up = [];
  let cur = headBone;
  while (cur && cur.isBone) {
    up.push(cur);
    if (cur === hipBone) break;
    cur = cur.parent;
  }
  if (up[up.length - 1] === hipBone) {
    return up.reverse();
  }
  const fallback = [hipBone];
  const spine = findBoneByAliases(state.currentSkeleton, ["Spine", "Lower_Torso", "spine", "torso"]);
  const chest = findBoneByAliases(state.currentSkeleton, ["Chest", "Upper_Torso", "chest", "upper"]);
  const neck = findBoneByAliases(state.currentSkeleton, ["Neck", "neck"]);
  for (const b of [spine, chest, neck, headBone]) {
    if (b && fallback[fallback.length - 1] !== b) fallback.push(b);
  }
  return fallback;
}

function buildNamedFootToHeadChain(side, hipBone, headBone) {
  if (!hipBone || !headBone) return null;

  const aliasBySide = side === "L"
    ? {
        thigh: ["L_Thigh", "LeftUpLeg", "LeftThigh", "mixamorigleftupleg"],
        calf: ["L_Calf", "LeftLeg", "LeftCalf", "mixamorigleftleg"],
        foot: ["L_Foot", "LeftFoot", "foot_l", "mixamorigleftfoot"],
      }
    : {
        thigh: ["R_Thigh", "RightUpLeg", "RightThigh", "mixamorigrightupleg"],
        calf: ["R_Calf", "RightLeg", "RightCalf", "mixamorigrightleg"],
        foot: ["R_Foot", "RightFoot", "foot_r", "mixamorigrightfoot"],
      };

  const thigh = findBoneByAliases(state.currentSkeleton, aliasBySide.thigh);
  const calf = findBoneByAliases(state.currentSkeleton, aliasBySide.calf);
  const foot = findBoneByAliases(state.currentSkeleton, aliasBySide.foot);

  const chain = [];
  for (const b of [foot, calf, thigh, hipBone]) {
    if (b && chain[chain.length - 1] !== b) chain.push(b);
  }
  if (chain.length < 2) return null;

  const hipToHead = buildHipToHeadPath(hipBone, headBone);
  for (const b of hipToHead.slice(1)) {
    if (b && chain[chain.length - 1] !== b) chain.push(b);
  }
  return chain.length >= 2 ? chain : null;
}

function getDisplayChildren(bone) {
  const out = [];
  for (const c of bone.children) {
    if (c.isBone) out.push(c);
  }
  if (
    bone === state.kinematicRootBone &&
    state.rootBone &&
    state.rootBone !== state.kinematicRootBone
  ) {
    for (const c of state.rootBone.children) {
      if (!c.isBone || c === state.kinematicRootBone) continue;
      if (!out.includes(c)) out.push(c);
    }
  }
  return out;
}

function cacheBindPose(skeleton) {
  const cache = new Map();
  for (const b of skeleton.bones) {
    cache.set(b.uuid, {
      position: b.position.clone(),
      quaternion: b.quaternion.clone(),
      scale: b.scale.clone()
    });
  }
  return cache;
}

function applyBindPose(skeleton, cache) {
  state.currentSkinnedMesh?.pose?.();
  for (const b of skeleton.bones) {
    const c = cache.get(b.uuid);
    if (!c) continue;
    b.position.copy(c.position);
    b.quaternion.copy(c.quaternion);
    b.scale.copy(c.scale);
  }
  skeleton.bones[0]?.updateMatrixWorld(true);
  state.treeDirty = true;
}

function resetSelectedBone() {
  const b = state.selectedBone;
  if (!b) return;
  const c = state.bindPoseCache.get(b.uuid);
  if (!c) return;
  b.position.copy(c.position);
  b.quaternion.copy(c.quaternion);
  b.scale.copy(c.scale);
  b.updateMatrixWorld(true);
  state.treeDirty = true;
}

function computeFootAnchor(skeleton) {
  const l = getBoneStrict(skeleton, "L_Foot");
  const r = getBoneStrict(skeleton, "R_Foot");
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  l.getWorldPosition(a);
  r.getWorldPosition(b);
  return a.add(b).multiplyScalar(0.5);
}

function getSafeBox(root, meshes) {
  const box = new THREE.Box3().setFromObject(root);
  const s = new THREE.Vector3();
  box.getSize(s);
  if (Number.isFinite(s.length()) && s.length() > 1e-5) return box;
  if (meshes[0]) {
    const mbox = new THREE.Box3().setFromObject(meshes[0]);
    mbox.getSize(s);
    if (Number.isFinite(s.length()) && s.length() > 1e-5) return mbox;
  }
  return null;
}

function normalizeScale(root, meshes) {
  const box = getSafeBox(root, meshes);
  if (!box) return;
  const s = new THREE.Vector3();
  box.getSize(s);
  const k = 2.2 / Math.max(s.y, 1e-5);
  root.scale.multiplyScalar(k);
  console.log("normalize.scale", k);
}

function computeFootAnchorSafe(skeleton) {
  try {
    return computeFootAnchor(skeleton);
  } catch {
    return null;
  }
}

function frameModel(root, meshes) {
  const box = getSafeBox(root, meshes);
  if (!box) return;
  const size = new THREE.Vector3();
  box.getSize(size);
  state.modelMaxDim = Math.max(size.x, size.y, size.z);

  const dist = state.modelMaxDim * 1.6 + 1.0;
  camera.near = Math.max(0.001, dist / 500);
  camera.far = Math.max(100, dist * 40);
  camera.updateProjectionMatrix();

  camera.position.set(dist, dist * 0.65, dist * 1.08);
  if (state.pelvisBone) {
    state.pelvisBone.getWorldPosition(tmpV);
    orbit.target.copy(tmpV);
  } else {
    orbit.target.set(0, Math.max(0.6, size.y * 0.45), 0);
  }
  orbit.update();
  grid.scale.setScalar(clamp(state.modelMaxDim / 2, 0.6, 30));
  if (state.footAnchorWorld) {
    grid.position.set(state.footAnchorWorld.x, 0, state.footAnchorWorld.z);
  } else {
    grid.position.set(0, 0, 0);
  }
}

function buildMeshLabel(mesh, skeleton, index) {
  const v = mesh.geometry?.getAttribute("position")?.count || 0;
  const m = Array.isArray(mesh.material) ? mesh.material.length : (mesh.material ? 1 : 0);
  const used = new Set();
  const skinIndex = mesh.geometry?.getAttribute("skinIndex");
  if (skinIndex) {
    for (let i = 0; i < skinIndex.count; i++) {
      used.add(skinIndex.getX(i)); used.add(skinIndex.getY(i)); used.add(skinIndex.getZ(i)); used.add(skinIndex.getW(i));
    }
  }
  let bonesUsed = 0;
  for (const idx of used) if (idx >= 0 && idx < skeleton.bones.length) bonesUsed++;
  const b = new THREE.Box3().setFromObject(mesh);
  const s = new THREE.Vector3();
  b.getSize(s);
  const h = Number.isFinite(s.y) ? s.y.toFixed(3) : "n/a";
  const name = mesh.name || "(unnamed skinned mesh)";
  return `${index + 1}. ${name} | v:${v} | m:${m} | b:${bonesUsed} | h:${h}`;
}

function disposeArmatureVisuals() {
  if (state.skeletonHelper) {
    gizmoLayer.remove(state.skeletonHelper);
    state.skeletonHelper.geometry?.dispose();
  }
  state.skeletonHelper = null;

  for (const j of state.jointSpheres) if (j.parent) j.parent.remove(j);
  for (const a of state.jointAxes) if (a.parent) a.parent.remove(a);
  state.jointSpheres = [];
  state.jointAxes = [];

  if (state.selectionMarker) {
    gizmoLayer.remove(state.selectionMarker);
    state.selectionMarker.geometry?.dispose();
    state.selectionMarker.material?.dispose();
  }
  state.selectionMarker = null;

  for (const line of state.ikChainLines) {
    gizmoLayer.remove(line);
    line.geometry?.dispose();
    line.material?.dispose();
  }
  state.ikChainLines = [];

  state.jointGeo?.dispose();
  state.jointMat?.dispose();
  state.jointGeo = null;
  state.jointMat = null;

  transformControls.detach();
}

function createSkeletonDisplayLines(skeleton, rootBone, hipBone) {
  const geom = new THREE.BufferGeometry();
  const mat = new THREE.LineBasicMaterial({
    color: 0x00ffff,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
    transparent: true,
    opacity: 0.92
  });
  const lines = new THREE.LineSegments(geom, mat);
  lines.renderOrder = 998;
  lines.frustumCulled = false;
  lines.userData = { skeleton, rootBone, hipBone };
  return lines;
}

function updateSkeletonDisplayLines(lines) {
  if (!lines?.userData?.skeleton) return;
  const { skeleton, rootBone, hipBone } = lines.userData;
  const positions = [];
  for (const bone of skeleton.bones) {
    if (!bone.parent || !bone.parent.isBone) continue;
    let parent = bone.parent;
    if (rootBone && hipBone && parent === rootBone) {
      if (bone === hipBone) continue;
      parent = hipBone;
    }
    parent.getWorldPosition(tmpA);
    bone.getWorldPosition(tmpB);
    positions.push(tmpA.x, tmpA.y, tmpA.z, tmpB.x, tmpB.y, tmpB.z);
  }
  lines.geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  lines.geometry.computeBoundingSphere();
}

function rebuildArmatureVisuals(skeleton) {
  disposeArmatureVisuals();

  if (!state.kinematicRootBone) return;
  state.skeletonHelper = createSkeletonDisplayLines(skeleton, state.rootBone, state.kinematicRootBone);
  updateSkeletonDisplayLines(state.skeletonHelper);
  gizmoLayer.add(state.skeletonHelper);

  const headBone = findBoneByAliases(skeleton, ["Head", "head"]);

  const chains = [
    { bones: buildNamedFootToHeadChain("L", state.kinematicRootBone, headBone), color: 0x00ff88 },
    { bones: buildNamedFootToHeadChain("R", state.kinematicRootBone, headBone), color: 0xff66ff }
  ];

  for (const chain of chains) {
    if (!chain.bones || chain.bones.length < 2) continue;
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(chain.bones.length * 3), 3));
    const mat = new THREE.LineBasicMaterial({
      color: chain.color,
      depthTest: false,
      depthWrite: false,
      transparent: true,
      opacity: 0.92,
      toneMapped: false
    });
    const line = new THREE.Line(geom, mat);
    line.userData.chainBones = chain.bones;
    line.frustumCulled = false;
    line.renderOrder = 997;
    state.ikChainLines.push(line);
    gizmoLayer.add(line);
  }

  state.jointBaseRadius = clamp(state.modelMaxDim * 0.04, 0.04, 0.25);
  state.jointGeo = new THREE.SphereGeometry(1, 12, 12);
  state.jointMat = new THREE.MeshBasicMaterial({
    color: 0xffef00,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
    transparent: true,
    opacity: 1.0
  });

  for (const bone of skeleton.bones) {
    const s = new THREE.Mesh(state.jointGeo, state.jointMat);
    s.userData.bone = bone;
    s.renderOrder = 1000;
    bone.add(s);
    state.jointSpheres.push(s);

    const axes = new THREE.AxesHelper(1.0);
    axes.userData.bone = bone;
    axes.renderOrder = 1001;
    axes.material.depthTest = false;
    axes.material.depthWrite = false;
    axes.material.toneMapped = false;
    bone.add(axes);
    state.jointAxes.push(axes);
  }

  const marker = new THREE.Mesh(
    new THREE.SphereGeometry(0.06, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.95, depthTest: false, depthWrite: false, toneMapped: false })
  );
  marker.renderOrder = 1100;
  marker.visible = false;
  gizmoLayer.add(marker);
  state.selectionMarker = marker;

  applyVisibilityToggles();
}

function updateJointGizmoScale() {
  for (const j of state.jointSpheres) {
    j.getWorldPosition(tmpV);
    const dist = camera.position.distanceTo(tmpV);
    const r = clamp(dist * 0.018, state.jointBaseRadius * 0.8, state.jointBaseRadius * 6.0);
    j.scale.setScalar(r);
  }
  for (const a of state.jointAxes) {
    a.getWorldPosition(tmpV);
    const dist = camera.position.distanceTo(tmpV);
    const r = clamp(dist * 0.03, state.jointBaseRadius * 1.4, state.jointBaseRadius * 12.0);
    a.scale.setScalar(r);
  }
  if (state.selectionMarker && state.selectedBone) {
    state.selectedBone.getWorldPosition(tmpV);
    state.selectionMarker.position.copy(tmpV);
    const dist = camera.position.distanceTo(tmpV);
    state.selectionMarker.scale.setScalar(clamp(dist * 0.015, 0.06, 0.22));
  }
}

function attachTransformControlsToBone(bone) {
  if (!bone) {
    transformControls.detach();
    return;
  }
  transformControls.attach(bone);
  transformControls.setMode(ui.tcMode.value);
  transformControls.setSpace(ui.tcSpace.value);
}

function getBoneLineText(bone, depth, showAngles) {
  const indent = "  ".repeat(depth);
  const pos = bone.position.toArray().map(v => v.toFixed(3)).join(", ");
  let base = `${indent}- ${bone.name || "(unnamed)"} [pos:${pos}]`;
  if (showAngles) {
    const e = new THREE.Euler().setFromQuaternion(bone.quaternion, "XYZ");
    const d = [THREE.MathUtils.radToDeg(e.x), THREE.MathUtils.radToDeg(e.y), THREE.MathUtils.radToDeg(e.z)].map(v => v.toFixed(1)).join(",");
    const q = [bone.quaternion.x, bone.quaternion.y, bone.quaternion.z, bone.quaternion.w].map(v => v.toFixed(3)).join(",");
    const lim = state.boneLimits.get(bone.name);
    const limStr = lim ? ` [lim:${JSON.stringify(lim)}]` : "";
    base += ` [rot°:${d}] [quat:${q}]${limStr}`;
  }
  return base;
}

function syncTreeSelection() {
  const nodes = ui.tree.querySelectorAll(".bone-line");
  for (const n of nodes) n.classList.remove("sel");
  if (!state.selectedBone) return;
  const el = ui.tree.querySelector(`[data-bone-uuid="${state.selectedBone.uuid}"]`);
  if (el) el.classList.add("sel");
}

function buildBoneTreeDom(rootBone) {
  const showAngles = ui.toggleAngles.checked;
  const frag = document.createDocumentFragment();
  const walk = (bone, depth) => {
    const row = document.createElement("div");
    row.className = "bone-line";
    row.dataset.boneUuid = bone.uuid;
    row.textContent = getBoneLineText(bone, depth, showAngles);
    row.addEventListener("click", () => selectBone(bone));
    frag.appendChild(row);
    for (const c of getDisplayChildren(bone)) walk(c, depth + 1);
  };
  walk(rootBone, 0);

  ui.tree.replaceChildren(frag);
  syncTreeSelection();
}

function refreshTreeAndMeta() {
  if (!state.currentSkeleton || !state.kinematicRootBone) {
    ui.meta.textContent = "(aucun modele charge)";
    ui.tree.textContent = "";
    return;
  }
  ui.meta.textContent =
    `Mesh: ${state.currentSkinnedMesh?.name || "(unnamed)"} | Bones: ${state.currentSkeleton.bones.length} | SkeletonRoot: ${state.rootBone?.name || "(unnamed)"} | IKRoot(Hip): ${state.kinematicRootBone?.name || "(none)"} | IKChains: ${state.ikChainLines.length}`;
  buildBoneTreeDom(state.kinematicRootBone);
  state.treeDirty = false;
  state.lastTreeTs = performance.now();
}

function selectBone(bone) {
  if (bone && state.rootBone && state.kinematicRootBone && bone === state.rootBone && state.kinematicRootBone !== state.rootBone) {
    bone = state.kinematicRootBone;
  }
  state.selectedBone = bone || null;
  if (state.selectionMarker) state.selectionMarker.visible = !!bone;
  attachTransformControlsToBone(state.selectedBone);
  syncTreeSelection();
  state.treeDirty = true;
}

function applyVisibilityToggles() {
  if (state.skeletonHelper) state.skeletonHelper.visible = ui.toggleSkeleton.checked;
  for (const line of state.ikChainLines) line.visible = ui.toggleSkeleton.checked;
  for (const j of state.jointSpheres) j.visible = ui.toggleJoints.checked;
  for (const a of state.jointAxes) a.visible = ui.toggleAxes.checked;
  if (state.selectionMarker) state.selectionMarker.visible = !!state.selectedBone;
}

function setupBonePicking() {
  renderer.domElement.addEventListener("pointerdown", (e) => {
    if (!state.jointSpheres.length) return;
    pointer.x = (e.clientX / innerWidth) * 2 - 1;
    pointer.y = -(e.clientY / innerHeight) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(state.jointSpheres, false);
    if (!hits.length) return;
    const bone = hits[0].object.userData.bone;
    if (bone?.isBone) selectBone(bone);
  });
}

function clearCurrent() {
  if (state.currentRoot) scene.remove(state.currentRoot);
  state.currentRoot = null;
  state.entries = [];
  state.selectedEntryIndex = 0;
  state.currentSkinnedMesh = null;
  state.currentSkeleton = null;
  state.rootBone = null;
  state.pelvisBone = null;
  state.kinematicRootBone = null;
  state.selectedBone = null;
  state.bindPoseCache = new Map();
  state.modelMaxDim = 1;
  state.footAnchorWorld = null;
  state.treeDirty = false;
  disposeArmatureVisuals();
  ui.meshSelect.innerHTML = "";
  refreshTreeAndMeta();
}

function findSkinnedMeshes(root) {
  const arr = [];
  root.traverse((o) => { if (o.isSkinnedMesh && o.skeleton) arr.push(o); });
  return arr;
}

function loadEntry(index) {
  if (!state.entries.length) return;
  state.selectedEntryIndex = clamp(index, 0, state.entries.length - 1);
  const entry = state.entries[state.selectedEntryIndex];
  state.currentSkinnedMesh = entry.mesh;
  state.currentSkeleton = entry.mesh.skeleton;
  state.rootBone = findRootBone(state.currentSkeleton);
  state.pelvisBone = findPelvisBone(state.currentSkeleton);
  state.kinematicRootBone = state.pelvisBone || state.rootBone;
  state.bindPoseCache = entry.bindPoseCache;

  rebuildArmatureVisuals(state.currentSkeleton);
  transformControls.setSize(clamp(state.modelMaxDim * 0.45, 1.0, 3.2));
  selectBone(state.kinematicRootBone);
  if (state.pelvisBone) {
    state.pelvisBone.getWorldPosition(tmpV);
    orbit.target.copy(tmpV);
    orbit.update();
  }
  refreshTreeAndMeta();
}

async function loadGLB(src, isBuffer = false) {
  clearCurrent();
  const loader = new GLTFLoader();
  const gltf = await new Promise((resolve, reject) => {
    if (isBuffer) loader.parse(src, "", resolve, reject);
    else loader.load(src, resolve, undefined, reject);
  });

  state.currentRoot = gltf.scene;
  scene.add(state.currentRoot);

  const meshes = findSkinnedMeshes(state.currentRoot);
  if (!meshes.length) {
    ui.meta.textContent = "(aucune armature detectee: pas de SkinnedMesh/skeleton trouve)";
    return;
  }

  state.entries = meshes.map(mesh => ({ mesh, bindPoseCache: cacheBindPose(mesh.skeleton) }));
  state.entries.sort((a, b) => (b.mesh.geometry?.getAttribute("position")?.count || 0) - (a.mesh.geometry?.getAttribute("position")?.count || 0));

  normalizeScale(state.currentRoot, meshes);
  state.footAnchorWorld = computeFootAnchorSafe(state.entries[0].mesh.skeleton);
  if (!state.footAnchorWorld) {
    console.warn("L_Foot/R_Foot absents: grounding visuel désactivé");
  }

  state.currentSkeleton = state.entries[0].mesh.skeleton;
  state.pelvisBone = findPelvisBone(state.currentSkeleton);
  frameModel(state.currentRoot, meshes);

  ui.meshSelect.innerHTML = "";
  state.entries.forEach((entry, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = buildMeshLabel(entry.mesh, entry.mesh.skeleton, i);
    ui.meshSelect.appendChild(opt);
  });
  ui.meshSelect.value = "0";

  loadEntry(0);
  console.log("renderer.outputColorSpace", renderer.outputColorSpace);
}

ui.meshSelect.addEventListener("change", () => loadEntry(Number(ui.meshSelect.value || 0)));
ui.toggleSkeleton.addEventListener("change", applyVisibilityToggles);
ui.toggleJoints.addEventListener("change", applyVisibilityToggles);
ui.toggleAxes.addEventListener("change", applyVisibilityToggles);
ui.toggleAngles.addEventListener("change", () => { state.treeDirty = true; refreshTreeAndMeta(); });

ui.btnTPose.addEventListener("click", () => {
  if (!state.currentSkeleton) return;
  applyBindPose(state.currentSkeleton, state.bindPoseCache);
  updateJointGizmoScale();
  refreshTreeAndMeta();
});

ui.btnResetBone.addEventListener("click", () => {
  resetSelectedBone();
  updateJointGizmoScale();
  refreshTreeAndMeta();
});

ui.tcMode.addEventListener("change", () => {
  transformControls.setMode(ui.tcMode.value);
  ui.modeWarn.style.display = ui.tcMode.value === "translate" ? "inline" : "none";
});

ui.tcSpace.addEventListener("change", () => {
  transformControls.setSpace(ui.tcSpace.value);
});

const drop = ui.drop;
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.style.opacity = 0.85; });
drop.addEventListener("dragleave", () => { drop.style.opacity = 1; });
drop.addEventListener("drop", async (e) => {
  e.preventDefault();
  drop.style.opacity = 1;
  const file = e.dataTransfer.files?.[0];
  if (!file) return;
  const n = file.name.toLowerCase();
  if (!n.endsWith(".glb") && !n.endsWith(".gltf")) {
    alert("Fichier non supporte: .glb ou .gltf attendu");
    return;
  }
  await loadGLB(await file.arrayBuffer(), true);
});

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

setupBonePicking();

function animate(ts) {
  requestAnimationFrame(animate);
  if (state.skeletonHelper) {
    updateSkeletonDisplayLines(state.skeletonHelper);
  }
  for (const line of state.ikChainLines) {
    const bones = line.userData.chainBones;
    if (!bones?.length) continue;
    const pos = line.geometry.getAttribute("position");
    for (let i = 0; i < bones.length; i++) {
      bones[i].getWorldPosition(tmpV);
      pos.setXYZ(i, tmpV.x, tmpV.y, tmpV.z);
    }
    pos.needsUpdate = true;
    line.geometry.computeBoundingSphere();
  }
  if (state.jointSpheres.length && (ui.toggleJoints.checked || ui.toggleAxes.checked || state.selectedBone)) {
    updateJointGizmoScale();
  }
  if (state.treeDirty && ts - state.lastTreeTs > 100) {
    refreshTreeAndMeta();
  }
  predictedOverlays.updateScale(camera);
  renderer.render(scene, camera);
}
animate(0);

if (DEFAULT_URL) loadGLB(DEFAULT_URL);

function setPredictionPayload(payload) {
  predictedOverlays.updateFromPayload(payload);
}

function setPredictionOverlayVisibility(key, visible) {
  predictedOverlays.setVisible(key, visible);
}

async function loadModelFromArrayBuffer(arrayBuffer) {
  await loadGLB(arrayBuffer, true);
}

async function loadModelFromUrl(url) {
  await loadGLB(url, false);
}

function getRuntimeInfo() {
  return {
    revision: THREE.REVISION,
    outputColorSpace: renderer.outputColorSpace,
    currentMesh: state.currentSkinnedMesh?.name || null,
    skeletonBones: state.currentSkeleton?.bones?.length || 0
  };
}

export {
  setPredictionPayload,
  setPredictionOverlayVisibility,
  loadModelFromArrayBuffer,
  loadModelFromUrl,
  getRuntimeInfo
};

