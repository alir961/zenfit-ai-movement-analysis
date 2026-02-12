"use client";

import React, { useCallback, useEffect, useRef } from "react";
import type { PoseFrame, PoseJoint } from "@/lib/types/pose";

interface SkeletonViewProps {
  title: string;
  pose: PoseFrame | null;
  showBones: boolean;
  showJoints: boolean;
  showLabels: boolean;
}

const CONNECTIONS: Array<[string, string]> = [
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

const mapToCanvas = (pose: PoseFrame, joint: PoseJoint, width: number, height: number) => {
  let x = joint.x;
  let y = joint.y;
  if (pose.space === "normalized") {
    x = (x + 1) / 2;
    y = 1 - (y + 1) / 2;
  }
  return { x: x * width, y: y * height };
};

const drawJoint = (
  ctx: CanvasRenderingContext2D,
  pose: PoseFrame,
  joint: PoseJoint,
  width: number,
  height: number
) => {
  const { x, y } = mapToCanvas(pose, joint, width, height);
  ctx.beginPath();
  ctx.arc(x, y, 4, 0, Math.PI * 2);
  ctx.fill();
};

export const SkeletonView = ({ title, pose, showBones, showJoints, showLabels }: SkeletonViewProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!pose) return;

    const width = canvas.width;
    const height = canvas.height;

    if (showBones) {
      ctx.strokeStyle = "rgba(114, 76, 249, 0.8)";
      ctx.lineWidth = 2;
      CONNECTIONS.forEach(([aName, bName]) => {
        const a = pose.joints.find((joint) => joint.name === aName);
        const b = pose.joints.find((joint) => joint.name === bName);
        if (!a || !b || a.c < 0.1 || b.c < 0.1) return;
        ctx.beginPath();
        const aPoint = mapToCanvas(pose, a, width, height);
        const bPoint = mapToCanvas(pose, b, width, height);
        ctx.moveTo(aPoint.x, aPoint.y);
        ctx.lineTo(bPoint.x, bPoint.y);
        ctx.stroke();
      });
    }

    if (showJoints) {
      ctx.fillStyle = "rgba(0, 204, 153, 0.8)";
      pose.joints.forEach((joint) => {
        if (joint.c < 0.1) return;
        drawJoint(ctx, pose, joint, width, height);
      });
    }

    if (showLabels) {
      ctx.fillStyle = "rgba(15, 16, 32, 0.7)";
      ctx.font = "12px var(--font-body)";
      pose.joints.forEach((joint) => {
        if (joint.c < 0.1) return;
        const point = mapToCanvas(pose, joint, width, height);
        ctx.fillText(joint.name, point.x + 6, point.y - 4);
      });
    }
  }, [pose, showBones, showJoints, showLabels]);

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
    <div className="card" style={{ position: "relative" }}>
      <h3 className="section-title">{title}</h3>
      <div ref={containerRef} style={{ width: "100%", height: 320, position: "relative" }}>
        <canvas ref={canvasRef} />
      </div>
    </div>
  );
};
