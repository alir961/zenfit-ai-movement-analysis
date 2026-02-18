import * as THREE from "three";

const RAW17_EDGES = [
  [0, 1], [1, 3], [0, 2], [2, 4],
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16]
];

const DEFAULT_MAPPED_EDGES = [
  ["Pelvis", "Spine"], ["Spine", "Chest"], ["Chest", "Neck"], ["Neck", "Head"],
  ["Chest", "L_Shoulder"], ["L_Shoulder", "L_Elbow"], ["L_Elbow", "L_Wrist"],
  ["Chest", "R_Shoulder"], ["R_Shoulder", "R_Elbow"], ["R_Elbow", "R_Wrist"],
  ["Pelvis", "L_Hip"], ["L_Hip", "L_Knee"], ["L_Knee", "L_Ankle"],
  ["Pelvis", "R_Hip"], ["R_Hip", "R_Knee"], ["R_Knee", "R_Ankle"]
];

function makePointMaterial(color) {
  return new THREE.MeshBasicMaterial({
    color,
    depthTest: false,
    depthWrite: false,
    transparent: true,
    opacity: 0.95,
    toneMapped: false
  });
}

function makeLineMaterial(color) {
  return new THREE.LineBasicMaterial({
    color,
    depthTest: false,
    depthWrite: false,
    transparent: true,
    opacity: 0.9,
    toneMapped: false
  });
}

function clearGroup(group) {
  for (const child of [...group.children]) {
    group.remove(child);
    child.geometry?.dispose?.();
    child.material?.dispose?.();
  }
}

function asVector3(j) {
  return new THREE.Vector3(Number(j.x) || 0, Number(j.y) || 0, Number(j.z) || 0);
}

export class PredictedOverlays {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.renderOrder = 1300;
    scene.add(this.group);

    this.raw17 = this._createLayer("rtmw3d_raw17", 0xff7f50);
    this.raw17Normalized = this._createLayer("***REMOVED***", 0x66a3ff);
    this.humanoid = this._createLayer("rtmw3d_mapped_humanoid", 0x7fff00);
    this.backCenterMarker = null;

    this.visibility = {
      rtmw3d_raw17: true,
      ***REMOVED***: true,
      rtmw3d_mapped_humanoid: true
    };
  }

  _createLayer(name, color) {
    const group = new THREE.Group();
    group.name = name;
    this.group.add(group);
    return {
      name,
      color,
      group,
      points: [],
      lines: []
    };
  }

  setVisible(key, visible) {
    this.visibility[key] = !!visible;
    const layer = key === "rtmw3d_raw17"
      ? this.raw17
      : key === "***REMOVED***"
        ? this.raw17Normalized
        : this.humanoid;
    if (layer) layer.group.visible = !!visible;
    if (key === "***REMOVED***" && this.backCenterMarker) {
      this.backCenterMarker.visible = !!visible;
    }
  }

  updateFromPayload(payload) {
    const raw17 = payload?.pose_raw17;
    const raw17Normalized = payload?.pose_raw17_normalized;
    const mapped = payload?.pose_mapped_humanoid;
    if (raw17) this._updateRaw17(raw17);
    if (raw17Normalized) this._updateRaw17Normalized(raw17Normalized);
    if (mapped) this._updateMapped(mapped);
  }

  _updateRaw17(raw17) {
    const layer = this.raw17;
    clearGroup(layer.group);
    layer.points = [];
    layer.lines = [];

    const joints = raw17?.joints || [];
    const vectors = joints.map(asVector3);

    for (let i = 0; i < vectors.length; i += 1) {
      const p = new THREE.Mesh(new THREE.SphereGeometry(0.015, 10, 10), makePointMaterial(layer.color));
      p.position.copy(vectors[i]);
      p.renderOrder = 1302;
      layer.group.add(p);
      layer.points.push(p);
    }

    const edges = raw17?.edges || RAW17_EDGES.map(([a, b]) => ({ a, b }));
    for (const edge of edges) {
      const a = Array.isArray(edge) ? edge[0] : edge.a;
      const b = Array.isArray(edge) ? edge[1] : edge.b;
      if (!vectors[a] || !vectors[b]) continue;
      const geom = new THREE.BufferGeometry().setFromPoints([vectors[a], vectors[b]]);
      const line = new THREE.Line(geom, makeLineMaterial(layer.color));
      line.renderOrder = 1301;
      layer.group.add(line);
      layer.lines.push(line);
    }

    layer.group.visible = !!this.visibility.rtmw3d_raw17;
  }

  _updateRaw17Normalized(raw17) {
    const layer = this.raw17Normalized;
    clearGroup(layer.group);
    layer.points = [];
    layer.lines = [];

    const joints = raw17?.joints || [];
    const vectors = joints.map(asVector3);
    const modeStr = String(raw17?.mode || "").toLowerCase();
    const isFullMode = modeStr.includes("full");
    const isTransformedMode = modeStr.includes("transform");
    const edgeColor = isTransformedMode ? 0xff4444 : (isFullMode ? 0xb266ff : 0x66a3ff);

    for (let i = 0; i < vectors.length; i += 1) {
      const p = new THREE.Mesh(new THREE.SphereGeometry(0.014, 10, 10), makePointMaterial(edgeColor));
      p.position.copy(vectors[i]);
      p.renderOrder = 1306;
      layer.group.add(p);
      layer.points.push(p);
    }

    const edges = raw17?.edges || RAW17_EDGES.map(([a, b]) => ({ a, b }));
    for (const edge of edges) {
      const a = Array.isArray(edge) ? edge[0] : edge.a;
      const b = Array.isArray(edge) ? edge[1] : edge.b;
      if (!vectors[a] || !vectors[b]) continue;
      const geom = new THREE.BufferGeometry().setFromPoints([vectors[a], vectors[b]]);
      const line = new THREE.Line(geom, makeLineMaterial(edgeColor));
      line.renderOrder = 1305;
      layer.group.add(line);
      layer.lines.push(line);
    }

    if (this.backCenterMarker) {
      layer.group.remove(this.backCenterMarker);
      this.backCenterMarker.geometry?.dispose?.();
      this.backCenterMarker.material?.dispose?.();
      this.backCenterMarker = null;
    }
    const bc = raw17?.metadata?.back_center;
    if (bc) {
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(0.022, 12, 12),
        makePointMaterial(isTransformedMode ? 0xff9900 : (isFullMode ? 0xff66cc : 0xff33aa))
      );
      marker.position.copy(asVector3(bc));
      marker.renderOrder = 1307;
      marker.visible = !!this.visibility.***REMOVED***;
      layer.group.add(marker);
      this.backCenterMarker = marker;
    }

    layer.group.visible = !!this.visibility.***REMOVED***;
  }

  _updateMapped(mapped) {
    const layer = this.humanoid;
    clearGroup(layer.group);
    layer.points = [];
    layer.lines = [];

    const joints = mapped?.joints || [];
    const byName = new Map();
    for (const joint of joints) {
      byName.set(joint.name, joint);
      const p = new THREE.Mesh(
        new THREE.SphereGeometry(joint.is_placeholder ? 0.012 : 0.016, 10, 10),
        makePointMaterial(joint.is_placeholder ? 0xffcc00 : layer.color)
      );
      p.position.copy(asVector3(joint));
      p.renderOrder = 1304;
      layer.group.add(p);
      layer.points.push(p);
    }

    const edges = mapped?.edges || DEFAULT_MAPPED_EDGES;
    for (const edge of edges) {
      const a = Array.isArray(edge) ? edge[0] : edge.a;
      const b = Array.isArray(edge) ? edge[1] : edge.b;
      const ja = byName.get(a);
      const jb = byName.get(b);
      if (!ja || !jb) continue;
      const geom = new THREE.BufferGeometry().setFromPoints([asVector3(ja), asVector3(jb)]);
      const line = new THREE.Line(
        geom,
        makeLineMaterial((ja.is_placeholder || jb.is_placeholder) ? 0xffcc00 : layer.color)
      );
      line.renderOrder = 1303;
      layer.group.add(line);
      layer.lines.push(line);
    }

    layer.group.visible = !!this.visibility.rtmw3d_mapped_humanoid;
  }

  updateScale(camera) {
    const distanceScale = (obj) => {
      const dist = camera.position.distanceTo(obj.position);
      const s = THREE.MathUtils.clamp(dist * 0.0045, 0.012, 0.075);
      obj.scale.setScalar(s / 0.015);
    };
    for (const p of this.raw17.points) distanceScale(p);
    for (const p of this.raw17Normalized.points) distanceScale(p);
    for (const p of this.humanoid.points) distanceScale(p);
    if (this.backCenterMarker) distanceScale(this.backCenterMarker);
  }

  dispose() {
    clearGroup(this.raw17.group);
    clearGroup(this.raw17Normalized.group);
    clearGroup(this.humanoid.group);
    this.scene.remove(this.group);
  }
}

export { RAW17_EDGES, DEFAULT_MAPPED_EDGES };
