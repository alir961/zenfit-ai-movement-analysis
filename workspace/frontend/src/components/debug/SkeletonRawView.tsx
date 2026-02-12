"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";
import { SkeletonView } from "./SkeletonView";

interface SkeletonRawViewProps {
  showBones: boolean;
  showJoints: boolean;
  showLabels: boolean;
}

export const SkeletonRawView = ({ showBones, showJoints, showLabels }: SkeletonRawViewProps) => {
  const rawPose = usePoseStore((state) => state.rawPose);

  return (
    <SkeletonView
      title="Raw Skeleton"
      pose={rawPose}
      showBones={showBones}
      showJoints={showJoints}
      showLabels={showLabels}
    />
  );
};
