'use client';

import React, { useEffect, useRef, useCallback } from 'react';
import { usePoseStore } from '@/lib/poseStore';
import type { Keypoint } from '@/lib/contracts';

const SKELETON_CONNECTIONS = [
    [5, 7], [7, 9], // Left arm
    [6, 8], [8, 10], // Right arm
    [5, 6], [5, 11], [6, 12], [11, 12], // Torso
    [11, 13], [13, 15], // Left leg
    [12, 14], [14, 16], // Right leg
];

export const PoseOverlay: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const animationFrameRef = useRef<number>(0);
    const dimensionsRef = useRef({ width: 0, height: 0 });

    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const currentFrame = usePoseStore.getState().currentFrame;

        // Clear with optimized method
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!currentFrame) return;

        const { keypoints } = currentFrame;
        const w = canvas.width;
        const h = canvas.height;

        // Set styles once
        ctx.strokeStyle = '#00ff9d';
        ctx.lineWidth = 2;
        ctx.lineCap = 'round';
        ctx.fillStyle = '#ffffff';

        // Draw skeleton lines (Disabled per user request)
        /*
        ctx.beginPath();
        for (const [i, j] of SKELETON_CONNECTIONS) {
            const kp1 = keypoints[i];
            const kp2 = keypoints[j];
            if (kp1 && kp2 && (kp1.score ?? 0) > 0.3 && (kp2.score ?? 0) > 0.3) {
                ctx.moveTo(kp1.x * w, kp1.y * h);
                ctx.lineTo(kp2.x * w, kp2.y * h);
            }
        }
        ctx.stroke();

        // Draw keypoints (Disabled per user request)
        for (const kp of keypoints) {
            if ((kp.score ?? 0) > 0.3) {
                ctx.beginPath();
                ctx.arc(kp.x * w, kp.y * h, 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }
        */
    }, []);

    useEffect(() => {
        const container = containerRef.current;
        const canvas = canvasRef.current;
        if (!container || !canvas) return;

        const updateSize = () => {
            const rect = container.getBoundingClientRect();
            const dpr = Math.min(window.devicePixelRatio || 1, 2); // Cap at 2x for performance
            dimensionsRef.current = { width: rect.width, height: rect.height };
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = `${rect.width}px`;
            canvas.style.height = `${rect.height}px`;
            const ctx = canvas.getContext('2d');
            if (ctx) ctx.scale(dpr, dpr);
        };

        updateSize();

        const observer = new ResizeObserver(updateSize);
        observer.observe(container);

        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        let running = true;

        const loop = () => {
            if (!running) return;
            draw();
            animationFrameRef.current = requestAnimationFrame(loop);
        };

        loop();

        return () => {
            running = false;
            cancelAnimationFrame(animationFrameRef.current);
        };
    }, [draw]);

    return (
        <div ref={containerRef} className="absolute inset-0 z-20 pointer-events-none">
            <canvas ref={canvasRef} />
        </div>
    );
};
