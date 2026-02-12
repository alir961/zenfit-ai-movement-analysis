"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";

export const MetricsTable = () => {
  const metrics = usePoseStore((state) => state.metrics);
  const params = usePoseStore((state) => state.normalizationParams);

  const distanceEntries = metrics ? Object.entries(metrics.distances) : [];

  return (
    <div className="card">
      <h3 className="section-title">Metrics</h3>
      <p className="section-subtitle">Body scale, distances, and confidence</p>

      <div className="metrics-grid" style={{ marginBottom: 16 }}>
        <div className="metric-card">
          <div className="metric-label">Confidence</div>
          <div className="metric-value">{metrics ? (metrics.confidence * 100).toFixed(1) : "--"}%</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Scale</div>
          <div className="metric-value">{params ? params.scale.toFixed(3) : "--"}</div>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {distanceEntries.length === 0 && (
            <tr>
              <td colSpan={2}>No metrics yet</td>
            </tr>
          )}
          {distanceEntries.map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{value.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
