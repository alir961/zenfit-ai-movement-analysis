import type { ExerciseState } from "../types/exercise";
import type { PoseFrame } from "../types/pose";
import { computeMetrics } from "./metrics";

const getJoint = (frame: PoseFrame, name: string) =>
  frame.joints.find((joint) => joint.name === name);

const angleAt = (a: { x: number; y: number; z: number }, b: { x: number; y: number; z: number }, c: { x: number; y: number; z: number }) => {
  const ab = { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
  const cb = { x: c.x - b.x, y: c.y - b.y, z: c.z - b.z };
  const dot = ab.x * cb.x + ab.y * cb.y + ab.z * cb.z;
  const mag = Math.hypot(ab.x, ab.y, ab.z) * Math.hypot(cb.x, cb.y, cb.z);
  if (mag === 0) return 180;
  const cos = Math.min(1, Math.max(-1, dot / mag));
  return (Math.acos(cos) * 180) / Math.PI;
};

const defaultState = (): ExerciseState => ({
  name: "none",
  phase: "idle",
  confidence: 0,
  repCount: 0,
});

export const updateExerciseState = (
  prev: ExerciseState | null,
  frame: PoseFrame | null
): ExerciseState => {
  if (!frame) return prev ?? defaultState();

  const leftHip = getJoint(frame, "left_hip");
  const rightHip = getJoint(frame, "right_hip");
  const leftKnee = getJoint(frame, "left_knee");
  const rightKnee = getJoint(frame, "right_knee");
  const leftAnkle = getJoint(frame, "left_ankle");
  const rightAnkle = getJoint(frame, "right_ankle");
  const leftShoulder = getJoint(frame, "left_shoulder");
  const rightShoulder = getJoint(frame, "right_shoulder");
  const leftElbow = getJoint(frame, "left_elbow");
  const rightElbow = getJoint(frame, "right_elbow");
  const leftWrist = getJoint(frame, "left_wrist");
  const rightWrist = getJoint(frame, "right_wrist");

  if (!leftHip || !rightHip || !leftKnee || !rightKnee || !leftAnkle || !rightAnkle) {
    return prev ?? defaultState();
  }

  const hip = {
    x: (leftHip.x + rightHip.x) / 2,
    y: (leftHip.y + rightHip.y) / 2,
    z: (leftHip.z + rightHip.z) / 2,
  };

  const knee = {
    x: (leftKnee.x + rightKnee.x) / 2,
    y: (leftKnee.y + rightKnee.y) / 2,
    z: (leftKnee.z + rightKnee.z) / 2,
  };

  const leftKneeAngle = angleAt(leftHip, leftKnee, leftAnkle);
  const rightKneeAngle = angleAt(rightHip, rightKnee, rightAnkle);
  const kneeAngle = (leftKneeAngle + rightKneeAngle) / 2;

  const metrics = computeMetrics(frame);
  const confidence = Math.min(1, Math.max(0, metrics.confidence));

  const squatDown = hip.y < knee.y - 0.08 && kneeAngle < 120;
  const squatUp = hip.y >= knee.y - 0.02 && kneeAngle > 150;

  let isPushUp = false;
  if (leftShoulder && rightShoulder && leftElbow && rightElbow && leftWrist && rightWrist) {
    const shoulderY = (leftShoulder.y + rightShoulder.y) / 2;
    const wristY = (leftWrist.y + rightWrist.y) / 2;
    const elbowAngle = (angleAt(leftShoulder, leftElbow, leftWrist) + angleAt(rightShoulder, rightElbow, rightWrist)) / 2;
    isPushUp = Math.abs(shoulderY - hip.y) < 0.2 && wristY < shoulderY + 0.2 && elbowAngle < 130;
  }

  const isBurpee = squatDown && isPushUp;

  const prevState = prev ?? defaultState();
  const next = { ...prevState, confidence };

  if (isBurpee) {
    next.name = "burpee";
    next.phase = squatDown ? "down" : "up";
  } else if (isPushUp) {
    next.name = "push_up";
    next.phase = "down";
  } else if (squatDown || squatUp) {
    next.name = "squat";
    next.phase = squatDown ? "down" : "up";
  } else {
    next.name = "none";
    next.phase = "idle";
  }

  if (prevState.name === next.name && prevState.phase === "down" && next.phase === "up") {
    next.repCount = prevState.repCount + 1;
  } else {
    next.repCount = prevState.repCount;
  }

  return next;
};
