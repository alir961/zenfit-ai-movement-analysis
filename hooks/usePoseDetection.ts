import { useEffect, useRef, useCallback } from 'react';
import { posePipeline } from '@/lib/posePipeline';

export const usePoseDetection = () => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const frameIdRef = useRef<number>(0);
    const lastProcessTimeRef = useRef<number>(0);
    const THROTTLE_MS = 66; // Target ~15 FPS logic updates

    const loop = useCallback(() => {
        const video = videoRef.current;
        if (!video || video.paused || video.ended) {
            frameIdRef.current = requestAnimationFrame(loop);
            return;
        }

        const now = performance.now();
        if (now - lastProcessTimeRef.current >= THROTTLE_MS) {
            lastProcessTimeRef.current = now;
            posePipeline.processVideo(video);
        }

        frameIdRef.current = requestAnimationFrame(loop);
    }, []);

    const startDetection = useCallback(() => {
        if (!frameIdRef.current) {
            lastProcessTimeRef.current = performance.now();
            loop();
        }
    }, [loop]);

    const stopDetection = useCallback(() => {
        if (frameIdRef.current) {
            cancelAnimationFrame(frameIdRef.current);
            frameIdRef.current = 0;
        }
    }, []);

    useEffect(() => {
        startDetection();
        return () => stopDetection();
    }, [startDetection, stopDetection]);

    return { videoRef };
};
