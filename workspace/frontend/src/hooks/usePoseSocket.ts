"use client";

import { useEffect, useMemo } from "react";
import type { Socket } from "socket.io-client";
import { createPoseSocket } from "@/lib/socket/client";
import { DEBUG_STATE, EXERCISE_STATE, POSE_METRICS, POSE_NORMALIZED } from "@/lib/socket/events";
import type {
  DebugStatePayload,
  ExerciseStatePayload,
  PoseMetricsPayload,
  PoseNormalizedPayload,
} from "@/lib/types/socket";
import { usePoseStore } from "@/lib/poseStore";

export const usePoseSocket = (): Socket => {
  const socket = useMemo(() => createPoseSocket(), []);
  const setSocketConnected = usePoseStore((state) => state.setSocketConnected);
  const setNormalizedPose = usePoseStore((state) => state.setNormalizedPose);
  const setMetrics = usePoseStore((state) => state.setMetrics);
  const setExerciseState = usePoseStore((state) => state.setExerciseState);
  const setDebugState = usePoseStore((state) => state.setDebugState);

  useEffect(() => {
    socket.on("connect", () => setSocketConnected(true));
    socket.on("disconnect", () => setSocketConnected(false));

    socket.on(POSE_NORMALIZED, (payload: PoseNormalizedPayload) => {
      setNormalizedPose(payload.frame, payload.params);
    });

    socket.on(POSE_METRICS, (payload: PoseMetricsPayload) => {
      setMetrics(payload.metrics);
    });

    socket.on(EXERCISE_STATE, (payload: ExerciseStatePayload) => {
      setExerciseState(payload.state);
    });

    socket.on(DEBUG_STATE, (payload: DebugStatePayload) => {
      setDebugState(payload);
    });

    return () => {
      socket.removeAllListeners();
      socket.disconnect();
    };
  }, [setDebugState, setExerciseState, setMetrics, setNormalizedPose, setSocketConnected, socket]);

  return socket;
};
