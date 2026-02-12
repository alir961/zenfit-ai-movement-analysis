import * as THREE from "three";
import type { PoseFrame } from "@/lib/types/pose";

const normalizeName = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "");

const matchBone = (scene: THREE.Object3D, candidates: string[]) => {
  const normalized = candidates.map(normalizeName);
  let found: THREE.Bone | null = null;
  scene.traverse((child) => {
    if (!child || found) return;
    if ((child as THREE.Bone).isBone) {
      const bone = child as THREE.Bone;
      const name = normalizeName(bone.name);
      if (normalized.some((candidate) => name.includes(candidate))) {
        found = bone;
      }
    }
  });
  return found;
};

export interface RigBones {
  hips?: THREE.Bone | null;
  spine?: THREE.Bone | null;
  chest?: THREE.Bone | null;
  leftUpperArm?: THREE.Bone | null;
  leftLowerArm?: THREE.Bone | null;
  rightUpperArm?: THREE.Bone | null;
  rightLowerArm?: THREE.Bone | null;
  leftUpperLeg?: THREE.Bone | null;
  leftLowerLeg?: THREE.Bone | null;
  rightUpperLeg?: THREE.Bone | null;
  rightLowerLeg?: THREE.Bone | null;
}

export const buildRig = (scene: THREE.Object3D): RigBones => {
  return {
    hips: matchBone(scene, ["hips", "pelvis", "root"]),
    spine: matchBone(scene, ["spine", "spine1", "spine02"]),
    chest: matchBone(scene, ["chest", "spine2", "spine03"]),
    leftUpperArm: matchBone(scene, ["leftarm", "upperarmleft", "upperarm_l", "leftupperarm"]),
    leftLowerArm: matchBone(scene, ["leftforearm", "lowerarmleft", "lowerarm_l", "leftlowerarm"]),
    rightUpperArm: matchBone(scene, ["rightarm", "upperarmright", "upperarm_r", "rightupperarm"]),
    rightLowerArm: matchBone(scene, ["rightforearm", "lowerarmright", "lowerarm_r", "rightlowerarm"]),
    leftUpperLeg: matchBone(scene, ["leftupleg", "leftthigh", "upperleg_l", "leftupperleg"]),
    leftLowerLeg: matchBone(scene, ["leftleg", "leftcalf", "lowerleg_l", "leftlowerleg"]),
    rightUpperLeg: matchBone(scene, ["rightupleg", "rightthigh", "upperleg_r", "rightupperleg"]),
    rightLowerLeg: matchBone(scene, ["rightleg", "rightcalf", "lowerleg_r", "rightlowerleg"]),
  };
};

const joint = (frame: PoseFrame, name: string) => frame.joints.find((item) => item.name === name);

const poseVector = (frame: PoseFrame, from: string, to: string) => {
  const a = joint(frame, from);
  const b = joint(frame, to);
  if (!a || !b) return null;
  return new THREE.Vector3(b.x - a.x, b.y - a.y, b.z - a.z).normalize();
};

const applyBoneDirection = (bone: THREE.Bone | null | undefined, direction: THREE.Vector3 | null) => {
  if (!bone || !direction) return;
  const forward = new THREE.Vector3(0, 1, 0);
  const quaternion = new THREE.Quaternion().setFromUnitVectors(forward, direction);
  bone.quaternion.slerp(quaternion, 0.35);
};

export const applyPoseToRig = (rig: RigBones, frame: PoseFrame | null) => {
  if (!frame) return;

  applyBoneDirection(rig.leftUpperArm, poseVector(frame, "left_shoulder", "left_elbow"));
  applyBoneDirection(rig.leftLowerArm, poseVector(frame, "left_elbow", "left_wrist"));
  applyBoneDirection(rig.rightUpperArm, poseVector(frame, "right_shoulder", "right_elbow"));
  applyBoneDirection(rig.rightLowerArm, poseVector(frame, "right_elbow", "right_wrist"));
  applyBoneDirection(rig.leftUpperLeg, poseVector(frame, "left_hip", "left_knee"));
  applyBoneDirection(rig.leftLowerLeg, poseVector(frame, "left_knee", "left_ankle"));
  applyBoneDirection(rig.rightUpperLeg, poseVector(frame, "right_hip", "right_knee"));
  applyBoneDirection(rig.rightLowerLeg, poseVector(frame, "right_knee", "right_ankle"));
};
