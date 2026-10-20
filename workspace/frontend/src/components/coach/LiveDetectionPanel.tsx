"use client";

import React from "react";
import { motion } from "framer-motion";
import { usePoseStore } from "@/lib/poseStore";
import { getExercise } from "@/lib/exercises";

export const LiveDetectionPanel = () => {
  const exercise = usePoseStore((state) => state.exercise);
  const selectedExercise = usePoseStore((state) => state.selectedExercise);

  // The backend switches exercise on the next frame it receives; until then its state
  // still describes the previous exercise.
  const synced = exercise.name === selectedExercise;
  const repCount = synced ? exercise.repCount : 0;
  const confidence = synced ? Math.round(exercise.confidence * 100) : 0;
  const label = getExercise(selectedExercise)?.label ?? selectedExercise;

  return (
    <section className="panel stats" aria-live="polite">
      <div className="stats__reps">
        <span className="eyebrow">Reps</span>
        <motion.span
          key={`${selectedExercise}-${repCount}`}
          className="stats__count"
          initial={{ scale: 1.2, opacity: 0.5 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 400, damping: 22 }}
        >
          {repCount}
        </motion.span>
      </div>

      <dl className="stats__grid">
        <div>
          <dt className="eyebrow">Exercise</dt>
          <dd>{label}</dd>
        </div>
        <div>
          <dt className="eyebrow">Phase</dt>
          <dd className="stats__phase">{synced ? exercise.phase : "waiting"}</dd>
        </div>
      </dl>

      <div className="stats__confidence">
        <div className="stats__confidence-row">
          <span className="eyebrow">Tracking confidence</span>
          <span>{confidence}%</span>
        </div>
        <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={confidence}>
          <div className="meter__fill" style={{ width: `${confidence}%` }} />
        </div>
      </div>
    </section>
  );
};
