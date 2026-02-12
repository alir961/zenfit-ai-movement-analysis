"use client";

import React, { useRef, useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import { BoxHelper, GridHelper, AxesHelper, Group } from "three";

interface ThreeDebugViewerProps {
  modelPath?: string;
}

function SceneHelpers() {
  const { scene } = useThree();
  useEffect(() => {
    const axes = new AxesHelper(2); // Red=X, Green=Y, Blue=Z
    scene.add(axes);
    
    // Grid 1x1 meters
    const grid = new GridHelper(10, 10, 0x444444, 0x222222);
    scene.add(grid);

    return () => {
      scene.remove(axes);
      scene.remove(grid);
    };
  }, [scene]);
  return null;
}

import { getNormalizationScale } from "@/lib/math/normalization";

// ...

function ModelInspector({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const ref = useRef<Group>(null);

  useEffect(() => {
    if (ref.current) {
      const object = ref.current;
      // Apply normalization
      const scale = getNormalizationScale(scene);
      object.scale.set(scale, scale, scale);
      
      // Center the model
      const box = new BoxHelper(object);
      box.update();
      // centering logic if needed, but usually scale is enough for inspection
    }
  }, [scene]);

  return (
    <group>
      <primitive object={scene} ref={ref} />
      {ref.current && <primitive object={new BoxHelper(ref.current, 0x00cc99)} />}
    </group>
  );
}

export const ThreeDebugViewer: React.FC<ThreeDebugViewerProps> = ({ modelPath = "/3d/MaleBodyWithArmature.glb" }) => {
  return (
    <div className="w-full h-full min-h-[300px] bg-black/80 rounded-lg overflow-hidden border border-white/10 relative group">
      <div className="absolute top-2 left-2 z-10 pointer-events-none flex flex-col gap-1">
        <span className="text-[10px] text-white/50 uppercase bg-black/50 px-2 py-1 rounded border border-white/5">
          Grid: 1m x 1m
        </span>
        <span className="text-[10px] text-mint uppercase bg-black/50 px-2 py-1 rounded border border-mint/20">
          Normalized Scale: 1.0
        </span>
      </div>
      <Canvas camera={{ position: [0, 1.2, 2.5], fov: 45 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 5, 2]} intensity={1} />
        <directionalLight position={[-2, 2, 5]} intensity={0.5} />
        
        <SceneHelpers />
        <ModelInspector url={modelPath} />
        
        <OrbitControls makeDefault target={[0, 0.9, 0]} />
      </Canvas>
    </div>
  );
};
