"use client";

import React from "react";
import { usePoseStore } from "@/lib/poseStore";
import { SkeletonView } from "./SkeletonView";

interface SkeletonNormalizedViewProps {
  showBones: boolean;
  showJoints: boolean;
  showLabels: boolean;
}

export const SkeletonNormalizedView = ({ showBones, showJoints, showLabels }: SkeletonNormalizedViewProps) => {
  const normalizedPose = usePoseStore((state) => state.normalizedPose);

  return (
    <SkeletonView
      title="Normalized Skeleton"
      pose={normalizedPose}
      showBones={showBones}
      showJoints={showJoints}
      showLabels={showLabels}
    />
  );
};
