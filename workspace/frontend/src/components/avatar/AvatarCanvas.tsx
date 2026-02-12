"use client";

import React, { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Environment } from "@react-three/drei";
import { AvatarRig } from "./AvatarRig";

export const AvatarCanvas = () => {
  return (
    <div className="absolute inset-0 pointer-events-none">
      <Canvas camera={{ position: [0, 0.8, 3.2], fov: 45 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[3, 5, 2]} intensity={1.1} />
        <Suspense fallback={null}>
          <Environment preset="studio" />
          <AvatarRig />
        </Suspense>
      </Canvas>
    </div>
  );
};
