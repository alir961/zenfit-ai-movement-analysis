import { describe, expect, test } from "bun:test";
import { normalizePose } from "../src/lib/pose/normalize";
import { computeMetrics } from "../src/lib/pose/metrics";
import type { PoseFrame } from "../src/lib/types/pose";

const frame: PoseFrame = {
  t: 0,
  space: "camera",
  joints: [
    { name: "nose", x: 0.5, y: 0.1, z: 0, c: 0.9 },
    { name: "left_eye", x: 0.48, y: 0.09, z: 0, c: 0.9 },
    { name: "right_eye", x: 0.52, y: 0.09, z: 0, c: 0.9 },
    { name: "left_ear", x: 0.46, y: 0.1, z: 0, c: 0.9 },
    { name: "right_ear", x: 0.54, y: 0.1, z: 0, c: 0.9 },
    { name: "left_shoulder", x: 0.4, y: 0.3, z: 0, c: 0.9 },
    { name: "right_shoulder", x: 0.6, y: 0.3, z: 0, c: 0.9 },
    { name: "left_elbow", x: 0.35, y: 0.45, z: 0, c: 0.9 },
    { name: "right_elbow", x: 0.65, y: 0.45, z: 0, c: 0.9 },
    { name: "left_wrist", x: 0.3, y: 0.6, z: 0, c: 0.9 },
    { name: "right_wrist", x: 0.7, y: 0.6, z: 0, c: 0.9 },
    { name: "left_hip", x: 0.43, y: 0.6, z: 0, c: 0.9 },
    { name: "right_hip", x: 0.57, y: 0.6, z: 0, c: 0.9 },
    { name: "left_knee", x: 0.44, y: 0.8, z: 0, c: 0.9 },
    { name: "right_knee", x: 0.56, y: 0.8, z: 0, c: 0.9 },
    { name: "left_ankle", x: 0.45, y: 0.95, z: 0, c: 0.9 },
    { name: "right_ankle", x: 0.55, y: 0.95, z: 0, c: 0.9 },
  ],
};

describe("normalizePose", () => {
  test("centers hips near origin", () => {
    const { frame: normalized } = normalizePose(frame);
    const hip = normalized.joints.find((joint) => joint.name === "left_hip");
    expect(hip).toBeTruthy();
    if (!hip) return;
    expect(Math.abs(hip.x)).toBeLessThan(1);
  });
});

describe("computeMetrics", () => {
  test("returns confidence and distances", () => {
    const metrics = computeMetrics(frame);
    expect(metrics.confidence).toBeGreaterThan(0);
    expect(metrics.body.height).toBeGreaterThan(0);
  });
});

