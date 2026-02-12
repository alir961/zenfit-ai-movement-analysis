import * as THREE from "three";

/**
 * Calculates the scale factor required to normalize a model's bounding box to fit within a 1x1x1 unit cube.
 * @param object The 3D object to measure.
 * @returns The scale factor to apply to the object.
 */
export const getNormalizationScale = (object: THREE.Object3D): number => {
  const box = new THREE.Box3().setFromObject(object);
  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDimension = Math.max(size.x, size.y, size.z);
  return maxDimension > 0 ? 1 / maxDimension : 1;
};

/**
 * Normalizes the model's position to center it at (0,0,0) and scales it to fit in a 1x1x1 cube.
 * @param object The 3D object to normalize.
 */
export const normalizeModel = (object: THREE.Object3D) => {
  const scale = getNormalizationScale(object);
  object.scale.set(scale, scale, scale);

  const box = new THREE.Box3().setFromObject(object);
  const center = new THREE.Vector3();
  box.getCenter(center);
  
  // Reposition to center
  object.position.sub(center);
  
  // Adjust Y so feet are at Y=0 (optional, but good for avatars)
  // object.position.y += (box.max.y - box.min.y) / 2;
};
