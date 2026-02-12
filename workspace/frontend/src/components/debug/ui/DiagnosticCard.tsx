import React from "react";

interface DiagnosticCardProps {
  title: string;
  children: React.ReactNode;
  headerAction?: React.ReactNode;
  variant?: "default" | "error" | "neon";
  className?: string;
}

export const DiagnosticCard: React.FC<DiagnosticCardProps> = ({
  title,
  children,
  headerAction,
  variant = "default",
  className = "",
}) => {
  const getBorderColor = () => {
    if (variant === "error") return "border-red-500/30";
    if (variant === "neon") return "neon-border";
    return "border-white/10";
  };

  return (
    <div className={`glass-card ${getBorderColor()} flex flex-col gap-4 ${className}`}>
      <div className="flex justify-between items-center border-b border-white/5 pb-3">
        <h3 className="text-[10px] uppercase tracking-[0.2em] font-mono text-lavender/70 flex items-center gap-2">
          <span className="w-1 h-3 bg-mint/50 rounded-sm"></span>
          {title}
        </h3>
        {headerAction && <div className="text-xs">{headerAction}</div>}
      </div>
      <div className="relative">
        {children}
      </div>
    </div>
  );
};
