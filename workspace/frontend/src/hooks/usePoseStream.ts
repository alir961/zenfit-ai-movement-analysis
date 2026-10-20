"use client";

import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { Socket } from "socket.io-client";
import { POSE_INPUT } from "@/lib/socket/events";
import type { PoseInputPayload } from "@/lib/types/socket";
import { usePoseStore } from "@/lib/poseStore";

const TARGET_FPS = 10;
const JPEG_QUALITY = 0.6;
const MAX_WIDTH = 320;

export const usePoseStream = (
  socket: Socket | null,
  videoRef: RefObject<HTMLVideoElement | null>,
  enabled: boolean
) => {
  const frameRef = useRef<number | null>(null);
  const lastSentRef = useRef<number>(0);
  const isSendingRef = useRef(false);

  useEffect(() => {
    if (!enabled) {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
      return;
    }

    // Session state belongs to the page: the debug page streams without a
    // session, and setting it here would start one on the coach page.
    if (!socket) return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { alpha: false });

    const loop = () => {
      const video = videoRef.current;
      if (!video || video.readyState < 2) {
        frameRef.current = requestAnimationFrame(loop);
        return;
      }

      const now = performance.now();
      const interval = 1000 / TARGET_FPS;

      if (!isSendingRef.current && now - lastSentRef.current >= interval) {
        const scale = Math.min(1, MAX_WIDTH / Math.max(video.videoWidth || 1, 1));
        const width = Math.max(1, Math.round((video.videoWidth || 640) * scale));
        const height = Math.max(1, Math.round((video.videoHeight || 480) * scale));

        canvas.width = width;
        canvas.height = height;

        if (ctx) {
          ctx.drawImage(video, 0, 0, width, height);
          isSendingRef.current = true;
          canvas.toBlob(
            (blob) => {
              if (blob && socket.connected) {
                const payload: PoseInputPayload = {
                  timestamp: Date.now(),
                  frameId: Math.floor(now),
                  width,
                  height,
                  image: blob,
                  exercise: usePoseStore.getState().selectedExercise,
                  clientMeta: {
                    fps: TARGET_FPS,
                    source: "camera",
                  },
                };
                socket.emit(POSE_INPUT, payload);
              }
              lastSentRef.current = now;
              isSendingRef.current = false;
            },
            "image/jpeg",
            JPEG_QUALITY
          );
        }
      }

      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [enabled, socket, videoRef]);
};
