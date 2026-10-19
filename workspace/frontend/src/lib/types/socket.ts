import type { ExerciseName, ExerciseState } from "./exercise";
import type { PoseFrame, NormalizationParams } from "./pose";
import type { PoseMetrics } from "./metrics";

export interface PoseInputPayload {
  timestamp: number;
  frameId: number;
  width: number;
  height: number;
  image: Blob;
  exercise: Exclude<ExerciseName, "none">;
  clientMeta?: Record<string, string | number | boolean>;
}

export interface PoseNormalizedPayload {
  frame: PoseFrame;
  params: NormalizationParams;
}

export interface PoseMetricsPayload {
  metrics: PoseMetrics;
}

export interface ExerciseStatePayload {
  state: ExerciseState;
}

export interface DebugStatePayload {
  raw: PoseFrame | null;
  normalized: PoseFrame | null;
  params: NormalizationParams | null;
  metrics: PoseMetrics | null;
  errors?: string[];
}
