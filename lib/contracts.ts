export interface Keypoint {
  x: number;
  y: number;
  score?: number;
  name?: string;
}

export interface PoseFrame {
  keypoints: Keypoint[];
  score: number;
  timestamp: number;
}

export interface RigMap {
  [boneName: string]: {
    rotation: [number, number, number]; // Euler angles or similar
    position?: [number, number, number];
  };
}
