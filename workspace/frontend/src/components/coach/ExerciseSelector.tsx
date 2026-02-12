"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";
import type { ExerciseName } from "@/lib/types/exercise";

const EXERCISES: { id: Exclude<ExerciseName, "none">; label: string; icon: string }[] = [
    { id: "squat", label: "Squat", icon: "🦵" },
    { id: "push_up", label: "Push Up", icon: "💪" },
    { id: "jumping_jack", label: "Jumping Jack", icon: "🏃" },
];

export const ExerciseSelector = () => {
    const selectedExercise = usePoseStore((state) => state.selectedExercise);
    const setSelectedExercise = usePoseStore((state) => state.setSelectedExercise);

    return (
        <div className="flex gap-2 justify-center w-full">
            {EXERCISES.map((ex) => (
                <button
                    key={ex.id}
                    onClick={() => setSelectedExercise(ex.id)}
                    className={`exercise-pill flex items-center gap-2 ${selectedExercise === ex.id ? "active" : ""
                        }`}
                >
                    <span>{ex.icon}</span>
                    <span>{ex.label}</span>
                </button>
            ))}
        </div>
    );
};
