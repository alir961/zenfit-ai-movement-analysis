export type ExerciseName = "squat" | "push_up" | "jumping_jack" | "none";

export type ExercisePhase = "idle" | "down" | "up" | "hold" | "transition";

export interface ExerciseState {
  name: ExerciseName;
  phase: ExercisePhase;
  confidence: number;
  repCount: number;
}
