"use client";

import React from "react";
import { Toggle } from "@/components/ui/Toggle";

interface GizmosOverlayProps {
  showBones: boolean;
  showJoints: boolean;
  showLabels: boolean;
  onToggleBones: (next: boolean) => void;
  onToggleJoints: (next: boolean) => void;
  onToggleLabels: (next: boolean) => void;
}

export const GizmosOverlay = ({
  showBones,
  showJoints,
  showLabels,
  onToggleBones,
  onToggleJoints,
  onToggleLabels,
}: GizmosOverlayProps) => {
  return (
    <div className="card">
      <h3 className="section-title">Debug Gizmos</h3>
      <p className="section-subtitle">Toggle joint markers, bones, and labels</p>
      <div style={{ display: "grid", gap: 12 }}>
        <Toggle label="Bones" checked={showBones} onChange={onToggleBones} />
        <Toggle label="Joints" checked={showJoints} onChange={onToggleJoints} />
        <Toggle label="Labels" checked={showLabels} onChange={onToggleLabels} />
      </div>
    </div>
  );
};
