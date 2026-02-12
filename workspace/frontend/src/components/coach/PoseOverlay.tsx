"use client";

import React, { useCallback, useEffect, useRef } from "react";
import { usePoseStore } from "@/lib/poseStore";
import type { JointName } from "@/lib/types/pose";

const CONNECTIONS: Array<[JointName, JointName]> = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"],
];

export const PoseOverlay = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { rawPose } = usePoseStore.getState();

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!rawPose) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.strokeStyle = "rgba(114, 76, 249, 0.7)";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";

    const mapToCanvas = (x: number, y: number) => {
      let cx = x;
      let cy = y;
      if (rawPose.space === "normalized") {
        cx = (cx + 1) / 2;
        cy = 1 - (cy + 1) / 2;
      }
      return { x: cx * width, y: cy * height };
    };

    CONNECTIONS.forEach(([aName, bName]) => {
      const a = rawPose.joints.find((joint) => joint.name === aName);
      const b = rawPose.joints.find((joint) => joint.name === bName);
      if (!a || !b || a.c < 0.2 || b.c < 0.2) return;
      const aPoint = mapToCanvas(a.x, a.y);
      const bPoint = mapToCanvas(b.x, b.y);
      ctx.beginPath();
      ctx.moveTo(aPoint.x, aPoint.y);
      ctx.lineTo(bPoint.x, bPoint.y);
      ctx.stroke();
    });
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let running = true;

    const loop = () => {
      if (!running) return;
      draw();
      frameRef.current = requestAnimationFrame(loop);
    };

    loop();

    return () => {
      running = false;
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [draw]);

  return (
    <div ref={containerRef} className="absolute inset-0 pointer-events-none">
      <canvas ref={canvasRef} />
    </div>
  );
};
