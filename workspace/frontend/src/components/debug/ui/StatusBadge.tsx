import React from "react";

interface StatusBadgeProps {
  status: "online" | "offline" | "active" | "error" | "warning";
  label?: string;
  pulse?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, pulse = false }) => {
  const getColors = () => {
    switch (status) {
      case "online":
      case "active":
        return "text-mint border-mint/20 bg-mint/5";
      case "offline":
      case "error":
        return "text-red-500 border-red-500/20 bg-red-500/5";
      case "warning":
        return "text-jasmine border-jasmine/20 bg-jasmine/5";
      default:
        return "text-lavender border-lavender/20 bg-lavender/5";
    }
  };

  const colors = getColors();

  return (
    <div
      className={`
        inline-flex items-center gap-2 px-3 py-1 rounded-full border text-[10px] font-mono tracking-wider uppercase
        ${colors}
        ${pulse ? "animate-pulse" : ""}
      `}
    >
      <div className={`w-1.5 h-1.5 rounded-full ${status === "offline" || status === "error" ? "bg-red-500" : status === "warning" ? "bg-jasmine" : "bg-mint"}`} />
      {label || status}
    </div>
  );
};
