import type { ExerciseName } from "./types/exercise";

export type ExerciseId = Exclude<ExerciseName, "none">;

export interface ExerciseInfo {
  id: ExerciseId;
  label: string;
  region: "Full body" | "Upper body";
  /** How to stand so the joints the backend needs are in frame. */
  framing: string;
}

export const EXERCISES: ExerciseInfo[] = [
  {
    id: "squat",
    label: "Squat",
    region: "Full body",
    framing: "Step back until your hips, knees and ankles are in frame.",
  },
  {
    id: "push_up",
    label: "Push-up",
    region: "Full body",
    framing: "Turn side-on with your arms and hips in frame.",
  },
  {
    id: "jumping_jack",
    label: "Jumping jack",
    region: "Full body",
    framing: "Face the camera with your hands and feet in frame.",
  },
  {
    id: "bicep_curl",
    label: "Bicep curl",
    region: "Upper body",
    framing: "Keep one shoulder, elbow and wrist in frame.",
  },
  {
    id: "lateral_raise",
    label: "Lateral raise",
    region: "Upper body",
    framing: "Face the camera with your arms in frame.",
  },
];

export const getExercise = (id: ExerciseName): ExerciseInfo | undefined =>
  EXERCISES.find((exercise) => exercise.id === id);
