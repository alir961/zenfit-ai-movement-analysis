"use client";

import React from "react";
import Image from "next/image";

interface PandaCoachProps {
  message: string;
}

export const PandaCoach = ({ message }: PandaCoachProps) => {
  return (
    <div className="glass-card neon-border flex items-center gap-6">
      <div className="flex-1">
        <div className="nav-item-pill mb-3 inline-flex">
          Coach Sensi
        </div>
        <p className="text-lavender text-sm leading-relaxed">{message}</p>
      </div>
      <div className="w-16 h-16 relative flex-shrink-0">
        <Image src="/panda.png" alt="Panda coach" fill sizes="64px" className="object-contain" />
      </div>
    </div>
  );
};
