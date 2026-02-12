"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";

export const LiveDetectionPanel = () => {
  const exercise = usePoseStore((state) => state.exercise);
  
  if (exercise.name === "none" && exercise.repCount === 0) return null;

  return (
    <div className="glass-card neon-border flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2 className="display-large text-mint uppercase text-xs tracking-[0.3em]">Live Analysis</h2>
        <div className="nav-item-pill text-[9px] animate-pulse">REC</div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-lavender/50">Mouvement</span>
          <span className="text-lg font-bold uppercase">{exercise.name.replace("_", " ")}</span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-lavender/50">Répétitions</span>
          <span className="text-lg font-bold text-mint">{exercise.repCount}</span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-lavender/50">Phase</span>
          <span className="text-sm font-medium">{exercise.phase}</span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-lavender/50">Confiance</span>
          <span className="text-sm font-medium">{Math.round(exercise.confidence * 100)}%</span>
        </div>
      </div>
    </div>
  );
};

