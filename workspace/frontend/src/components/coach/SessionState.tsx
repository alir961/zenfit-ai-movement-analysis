"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";

export const SessionState = () => {
  const sessionState = usePoseStore((state) => state.sessionState);
  const socketConnected = usePoseStore((state) => state.socketConnected);

  const label = sessionState === "running" ? "Running" : sessionState === "paused" ? "Paused" : "No Input";
  const dotColor = sessionState === "running" ? "var(--mint-leaf)" : sessionState === "paused" ? "#ffb74d" : "#ff6b6b";
  const dotShadow =
    sessionState === "running"
      ? "0 0 0 4px rgba(0, 204, 153, 0.18)"
      : sessionState === "paused"
      ? "0 0 0 4px rgba(255, 183, 77, 0.25)"
      : "0 0 0 4px rgba(255, 107, 107, 0.2)";

  return (
    <div className="status-chip">
      <span className="status-dot" style={{ background: dotColor, boxShadow: dotShadow }} />
      <span>{label}</span>
      <span style={{ opacity: 0.6 }}>{socketConnected ? "Socket On" : "Socket Off"}</span>
    </div>
  );
};
