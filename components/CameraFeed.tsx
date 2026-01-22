'use client';

import React, { useEffect, useState, forwardRef } from 'react';

interface CameraFeedProps {
    className?: string;
}

export const CameraFeed = forwardRef<HTMLVideoElement, CameraFeedProps>(({ className }, ref) => {
    const internalRef = React.useRef<HTMLVideoElement>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let stream: MediaStream | null = null;

        const setupCamera = async () => {
            try {
                // Combine refs
                const videoElement = internalRef.current;
                if (typeof ref === 'function') {
                    ref(videoElement);
                } else if (ref) {
                    ref.current = videoElement;
                }

                stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: 'user',
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        frameRate: { ideal: 30 }
                    },
                    audio: false,
                });

                if (videoElement) {
                    videoElement.srcObject = stream;
                    videoElement.onloadedmetadata = () => {
                        videoElement.play().catch(e => console.error("Play error:", e));
                    };
                }
            } catch (err) {
                console.error('Error accessing camera:', err);
                setError('PERMISSION DENIED');
            }
        };

        setupCamera();

        return () => {
            if (stream) {
                stream.getTracks().forEach((track) => track.stop());
            }
        };
    }, [ref]);

    if (error) {
        return (
            <div className="flex items-center justify-center w-full h-full bg-black/90 text-red-500 font-mono text-xs border border-red-900/50">
                [ERROR: {error}]
            </div>
        );
    }

    return (
        <video
            ref={internalRef}
            className={`w-full h-full object-cover ${className} transform scale-x-[-1]`} // Mirror effect
            muted
            playsInline
        />
    );
});

CameraFeed.displayName = 'CameraFeed';
