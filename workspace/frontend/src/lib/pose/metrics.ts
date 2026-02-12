import type { PoseFrame } from "../types/pose";
import type { PoseMetrics } from "../types/metrics";

const getJoint = (frame: PoseFrame, name: string) =>
  frame.joints.find((joint) => joint.name === name);

const distance = (a: { x: number; y: number; z: number }, b: { x: number; y: number; z: number }) => {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
};

export const computeMetrics = (frame: PoseFrame): PoseMetrics => {
  const leftShoulder = getJoint(frame, "left_shoulder");
  const rightShoulder = getJoint(frame, "right_shoulder");
  const leftHip = getJoint(frame, "left_hip");
  const rightHip = getJoint(frame, "right_hip");
  const leftAnkle = getJoint(frame, "left_ankle");
  const rightAnkle = getJoint(frame, "right_ankle");
  const nose = getJoint(frame, "nose");

  const shoulderWidth = leftShoulder && rightShoulder ? distance(leftShoulder, rightShoulder) : 0;
  const hipWidth = leftHip && rightHip ? distance(leftHip, rightHip) : 0;

  const heightTop = nose ?? leftShoulder ?? rightShoulder ?? leftHip ?? rightHip;
  const heightBottom = leftAnkle ?? rightAnkle ?? leftHip ?? rightHip;
  const height = heightTop && heightBottom ? distance(heightTop, heightBottom) : 0;

  const confidence = frame.joints.reduce((sum, joint) => sum + joint.c, 0) / Math.max(frame.joints.length, 1);

  const distances: Record<string, number> = {
    shoulderWidth,
    hipWidth,
    height,
  };

  return {
    confidence,
    body: {
      height,
      shoulderWidth,
      hipWidth,
    },
    distances,
  };
};
