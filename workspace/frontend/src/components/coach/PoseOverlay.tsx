"use client";

import React, { useCallback, useEffect, useRef } from "react";
import type { RefObject } from "react";
import { usePoseStore } from "@/lib/poseStore";
import type { JointName, PoseJoint } from "@/lib/types/pose";

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

const DRAWN_JOINTS = new Set<string>(CONNECTIONS.flat());
// Same threshold the backend uses to treat a joint as missing for rep counting.
const MIN_CONFIDENCE = 0.3;

interface PoseOverlayProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  mirrored?: boolean;
  /** Must match the CameraFeed fit so joints land on the video. */
  fit?: "cover" | "contain";
}

/** Draws the detected skeleton on top of the camera feed (optionally mirrored). */
export const PoseOverlay = ({ videoRef, mirrored = true, fit = "cover" }: PoseOverlayProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // The context is already scaled by devicePixelRatio: draw in CSS pixels.
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;
    ctx.clearRect(0, 0, width, height);

    const { rawPose } = usePoseStore.getState();
    if (!rawPose || rawPose.space !== "camera" || !video?.videoWidth) return;

    // Reproduce object-fit: cover scales to fill the box and crops, contain letterboxes.
    const fitScale = fit === "contain" ? Math.min : Math.max;
    const scale = fitScale(width / video.videoWidth, height / video.videoHeight);
    const drawnWidth = video.videoWidth * scale;
    const drawnHeight = video.videoHeight * scale;
    const offsetX = (width - drawnWidth) / 2;
    const offsetY = (height - drawnHeight) / 2;

    const toCanvas = (joint: PoseJoint) => {
      const px = mirrored ? 1 - (joint.px ?? 0) : joint.px ?? 0;
      return { x: offsetX + px * drawnWidth, y: offsetY + (joint.py ?? 0) * drawnHeight };
    };

    const byName = new Map(rawPose.joints.map((joint) => [joint.name, joint]));
    const isVisible = (joint: PoseJoint | undefined): joint is PoseJoint =>
      !!joint && joint.px !== undefined && joint.py !== undefined;

    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    CONNECTIONS.forEach(([aName, bName]) => {
      const a = byName.get(aName);
      const b = byName.get(bName);
      if (!isVisible(a) || !isVisible(b)) return;
      const confident = a.c >= MIN_CONFIDENCE && b.c >= MIN_CONFIDENCE;
      ctx.strokeStyle = confident ? "rgba(0, 204, 153, 0.9)" : "rgba(255, 255, 255, 0.2)";
      const aPoint = toCanvas(a);
      const bPoint = toCanvas(b);
      ctx.beginPath();
      ctx.moveTo(aPoint.x, aPoint.y);
      ctx.lineTo(bPoint.x, bPoint.y);
      ctx.stroke();
    });

    // Joints the backend cannot trust (e.g. out of frame) are drawn red.
    DRAWN_JOINTS.forEach((name) => {
      const joint = byName.get(name as JointName);
      if (!isVisible(joint)) return;
      const point = toCanvas(joint);
      ctx.fillStyle = joint.c >= MIN_CONFIDENCE ? "rgba(255, 255, 255, 0.95)" : "rgba(255, 80, 80, 0.7)";
      ctx.beginPath();
      ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [fit, mirrored, videoRef]);

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
