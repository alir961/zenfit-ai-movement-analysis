"use client";

import React, { useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Center, useGLTF } from "@react-three/drei";
import { usePoseStore } from "@/lib/poseStore";
import { applyPoseToRig, buildRig } from "./RigBindings";

export const AvatarRig = () => {
  const { scene } = useGLTF("/3d/MaleBodyWithArmature.glb");
  const normalizedPose = usePoseStore((state) => state.normalizedPose);

  const rig = useMemo(() => buildRig(scene), [scene]);

  useFrame(() => {
    applyPoseToRig(rig, normalizedPose);
  });

  return (
    <Center position={[0, -0.7, 0]}>
      <primitive object={scene} scale={0.85} />
    </Center>
  );
};

useGLTF.preload("/3d/MaleBodyWithArmature.glb");
