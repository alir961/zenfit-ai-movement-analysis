export type ExerciseName = "squat" | "push_up" | "jumping_jack" | "bicep_curl" | "lateral_raise" | "none";

export type ExercisePhase = "idle" | "down" | "up" | "hold" | "transition";

export interface ExerciseState {
  name: ExerciseName;
  phase: ExercisePhase;
  confidence: number;
  repCount: number;
}
