import type { NormalizationParams, PoseFrame, PoseJoint } from "../types/pose";

const getJoint = (frame: PoseFrame, name: string) =>
  frame.joints.find((joint) => joint.name === name);

export const normalizePose = (frame: PoseFrame) => {
  const leftHip = getJoint(frame, "left_hip");
  const rightHip = getJoint(frame, "right_hip");
  const leftShoulder = getJoint(frame, "left_shoulder");
  const rightShoulder = getJoint(frame, "right_shoulder");

  if (!leftHip || !rightHip || !leftShoulder || !rightShoulder) {
    const params: NormalizationParams = {
      center: { x: 0, y: 0, z: 0 },
      scale: 1,
    };
    return { frame, params };
  }

  const center = {
    x: (leftHip.x + rightHip.x) / 2,
    y: (leftHip.y + rightHip.y) / 2,
    z: (leftHip.z + rightHip.z) / 2,
  };

  const shoulderCenter = {
    x: (leftShoulder.x + rightShoulder.x) / 2,
    y: (leftShoulder.y + rightShoulder.y) / 2,
    z: (leftShoulder.z + rightShoulder.z) / 2,
  };

  const torso = {
    x: shoulderCenter.x - center.x,
    y: shoulderCenter.y - center.y,
    z: shoulderCenter.z - center.z,
  };

  const scale = Math.max(Math.hypot(torso.x, torso.y, torso.z), 0.0001);

  const normalizedJoints: PoseJoint[] = frame.joints.map((joint) => ({
    ...joint,
    x: (joint.x - center.x) / scale,
    y: -(joint.y - center.y) / scale,
    z: (joint.z - center.z) / scale,
  }));

  const params: NormalizationParams = { center, scale };

  return {
    frame: {
      ...frame,
      space: "normalized",
      joints: normalizedJoints,
    },
    params,
  };
};
