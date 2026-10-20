"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";
import { EXERCISES } from "@/lib/exercises";

export const ExerciseSelector = () => {
  const selectedExercise = usePoseStore((state) => state.selectedExercise);
  const setSelectedExercise = usePoseStore((state) => state.setSelectedExercise);

  return (
    <div className="exercise-grid" role="radiogroup" aria-label="Exercise">
      {EXERCISES.map((ex) => {
        const active = selectedExercise === ex.id;
        return (
          <button
            key={ex.id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setSelectedExercise(ex.id)}
            className={`exercise-option${active ? " is-active" : ""}`}
          >
            <span className="exercise-option__label">{ex.label}</span>
            <span className="exercise-option__region">{ex.region}</span>
          </button>
        );
      })}
    </div>
  );
};
