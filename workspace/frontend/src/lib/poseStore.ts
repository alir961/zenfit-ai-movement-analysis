import { create } from "zustand";
import type { ExerciseState, ExerciseName } from "./types/exercise";
import type { PoseFrame, NormalizationParams } from "./types/pose";
import type { PoseMetrics } from "./types/metrics";

export type SessionState = "running" | "paused";

interface PoseState {
  socketConnected: boolean;
  sessionState: SessionState;
  selectedExercise: Exclude<ExerciseName, "none">;
  rawPose: PoseFrame | null;
  normalizedPose: PoseFrame | null;
  normalizationParams: NormalizationParams | null;
  metrics: PoseMetrics | null;
  exercise: ExerciseState;
  debugErrors: string[];
  lastUpdated: number | null;

  setSocketConnected: (connected: boolean) => void;
  setSessionState: (state: SessionState) => void;
  setSelectedExercise: (name: Exclude<ExerciseName, "none">) => void;
  setRawPose: (frame: PoseFrame | null) => void;
  setNormalizedPose: (frame: PoseFrame | null, params: NormalizationParams | null) => void;
  setMetrics: (metrics: PoseMetrics | null) => void;
  setExerciseState: (state: ExerciseState) => void;
  setDebugState: (payload: {
    raw: PoseFrame | null;
    normalized: PoseFrame | null;
    params: NormalizationParams | null;
    metrics: PoseMetrics | null;
    errors?: string[];
  }) => void;
  reset: () => void;
}

const defaultExercise: ExerciseState = {
  name: "none",
  phase: "idle",
  confidence: 0,
  repCount: 0,
};

export const usePoseStore = create<PoseState>((set) => ({
  socketConnected: false,
  sessionState: "paused",
  selectedExercise: "squat",
  rawPose: null,
  normalizedPose: null,
  normalizationParams: null,
  metrics: null,
  exercise: defaultExercise,
  debugErrors: [],
  lastUpdated: null,

  setSocketConnected: (connected) =>
    set({ socketConnected: connected }),
  setSessionState: (state) => set({ sessionState: state }),
  setSelectedExercise: (name) => set({ selectedExercise: name }),
  setRawPose: (frame) => set({ rawPose: frame, lastUpdated: Date.now() }),
  setNormalizedPose: (frame, params) =>
    set({ normalizedPose: frame, normalizationParams: params, lastUpdated: Date.now() }),
  setMetrics: (metrics) => set({ metrics, lastUpdated: Date.now() }),
  setExerciseState: (exercise) => set({ exercise, lastUpdated: Date.now() }),
  setDebugState: (payload) =>
    set({
      rawPose: payload.raw,
      normalizedPose: payload.normalized,
      normalizationParams: payload.params,
      metrics: payload.metrics,
      debugErrors: payload.errors ?? [],
      lastUpdated: Date.now(),
    }),
  reset: () =>
    set({
      sessionState: "paused",
      selectedExercise: "squat",
      rawPose: null,
      normalizedPose: null,
      normalizationParams: null,
      metrics: null,
      exercise: defaultExercise,
      debugErrors: [],
      lastUpdated: null,
    }),
}));
