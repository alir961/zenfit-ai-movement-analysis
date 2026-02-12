// Basic Mock Generator for Pose Data
import { PoseFrame } from "../types/pose";

export const generateMockPose = (): PoseFrame => {
  const time = Date.now() / 1000;
  
  // Simulate a simple sway
  const sway = Math.sin(time) * 0.1;

  return {
    t: time,
    space: "normalized",
    joints: [
      { name: "nose", x: 0.5 + sway, y: 0.2, z: 0, c: 0.99 },
      { name: "left_shoulder", x: 0.6 + sway, y: 0.3, z: 0, c: 0.98 },
      { name: "right_shoulder", x: 0.4 + sway, y: 0.3, z: 0, c: 0.98 },
      { name: "left_elbow", x: 0.7 + sway, y: 0.4, z: 0.1, c: 0.95 },
      { name: "right_elbow", x: 0.3 + sway, y: 0.4, z: -0.1, c: 0.95 },
      { name: "left_wrist", x: 0.8 + sway, y: 0.5, z: 0.2, c: 0.90 },
      { name: "right_wrist", x: 0.2 + sway, y: 0.5, z: -0.2, c: 0.90 },
      { name: "left_hip", x: 0.55 + sway, y: 0.6, z: 0, c: 0.97 },
      { name: "right_hip", x: 0.45 + sway, y: 0.6, z: 0, c: 0.97 },
      { name: "left_knee", x: 0.55 + sway, y: 0.8, z: 0.1, c: 0.96 },
      { name: "right_knee", x: 0.45 + sway, y: 0.8, z: -0.1, c: 0.96 },
      { name: "left_ankle", x: 0.55 + sway, y: 0.95, z: 0, c: 0.94 },
      { name: "right_ankle", x: 0.45 + sway, y: 0.95, z: 0, c: 0.94 },
    ]
  };
};

export const generateMockMetrics = () => {
  return {
    confidence: 0.95 + Math.random() * 0.05,
    distances: {
      "shoulder_width": 0.45,
      "hip_width": 0.30,
      "height": 1.75
    },
    angles: {},
    body: {
      height: 1.75,
      shoulderWidth: 0.45,
      hipWidth: 0.30
    }
  };
};
