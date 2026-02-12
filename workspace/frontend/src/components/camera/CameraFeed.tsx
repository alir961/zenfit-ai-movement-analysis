"use client";

import React, { useEffect, useState, forwardRef } from "react";

interface CameraFeedProps {
  className?: string;
  mirrored?: boolean;
  onReady?: () => void;
}

export const CameraFeed = forwardRef<HTMLVideoElement, CameraFeedProps>(
  ({ className, mirrored = true, onReady }, ref) => {
    const internalRef = React.useRef<HTMLVideoElement>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
      let stream: MediaStream | null = null;

      const setupCamera = async () => {
        try {
          const videoElement = internalRef.current;
          if (typeof ref === "function") {
            ref(videoElement);
          } else if (ref) {
            ref.current = videoElement;
          }

          stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: "user",
              width: { ideal: 720 },
              height: { ideal: 1280 },
              frameRate: { ideal: 30 },
            },
            audio: false,
          });

          if (videoElement) {
            videoElement.srcObject = stream;
            videoElement.onloadedmetadata = () => {
              videoElement.play().catch(() => undefined);
              onReady?.();
            };
          }
        } catch (err) {
          console.error("Camera error:", err);
          setError("camera_permission_denied");
        }
      };

      setupCamera();

      return () => {
        if (stream) {
          stream.getTracks().forEach((track) => track.stop());
        }
      };
    }, [onReady, ref]);

    if (error) {
      return (
        <div className="flex items-center justify-center w-full h-full bg-black/90 text-white text-xs">
          Camera error: {error}
        </div>
      );
    }

    return (
      <video
        ref={internalRef}
        className={`w-full h-full object-cover ${mirrored ? "scale-x-[-1]" : ""} ${className ?? ""}`}
        muted
        playsInline
      />
    );
  }
);

CameraFeed.displayName = "CameraFeed";
