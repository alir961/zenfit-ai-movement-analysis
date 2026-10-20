export const JOINT_NAMES = [
  "nose",
  "left_eye",
  "right_eye",
  "left_ear",
  "right_ear",
  "left_shoulder",
  "right_shoulder",
  "left_elbow",
  "right_elbow",
  "left_wrist",
  "right_wrist",
  "left_hip",
  "right_hip",
  "left_knee",
  "right_knee",
  "left_ankle",
  "right_ankle",
] as const;

export type JointName = (typeof JOINT_NAMES)[number];

export interface PoseJoint {
  name: JointName;
  x: number;
  y: number;
  z: number;
  c: number;
  /** Image position (0..1) of the joint; sent with camera-space frames. */
  px?: number;
  py?: number;
}

export interface PoseFrame {
  t: number;
  space: "camera" | "normalized";
  joints: PoseJoint[];
}

export interface NormalizationParams {
  center: { x: number; y: number; z: number };
  scale: number;
}
