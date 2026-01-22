'use client';

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment, useGLTF, Center } from '@react-three/drei';
import { usePoseStore } from '@/lib/poseStore';

const AvatarModel: React.FC = () => {
    // Placeholder GLB path or logic
    // const { scene } = useGLTF('/avatar.glb');

    // Load the user-provided 3D model
    const { scene } = useGLTF('/3d/male_body.glb');

    return (
        <Center>
            <primitive
                object={scene}
                scale={0.05}
            // Position handled by Center
            />
        </Center>
    );
};

export const AvatarCanvas: React.FC = () => {
    return (
        <div className="w-full h-full absolute inset-0 z-10 pointer-events-none">
            <Canvas camera={{ position: [0, 0, 5], fov: 50 }}>
                <Suspense fallback={null}>
                    <ambientLight intensity={0.8} />
                    <pointLight position={[10, 10, 10]} intensity={1} />
                    <Environment preset="city" />

                    <AvatarModel />

                    {/* Disable interactions for now as it's an overlay */}
                    {/* <OrbitControls enablePan={false} enableZoom={false} /> */}
                </Suspense>
            </Canvas>
        </div>
    );
};
