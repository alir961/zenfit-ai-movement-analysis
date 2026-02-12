"use client";

import React from "react";

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}

export const Toggle = ({ label, checked, onChange }: ToggleProps) => {
  return (
    <button
      type="button"
      className="btn-secondary"
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
      aria-label={label}
      style={{ justifyContent: "space-between", width: "100%" }}
    >
      <span>{label}</span>
      <span>{checked ? "On" : "Off"}</span>
    </button>
  );
};
