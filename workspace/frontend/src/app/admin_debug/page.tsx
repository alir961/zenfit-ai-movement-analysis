"use client";

import React, { useRef, useState, useEffect } from "react";
import { usePoseSocket } from "@/hooks/usePoseSocket";
import { usePoseStream } from "@/hooks/usePoseStream";
import { usePoseStore } from "@/lib/poseStore";
import { GizmosOverlay } from "@/components/debug/GizmosOverlay";
import { MetricsTable } from "@/components/debug/MetricsTable";
import { SkeletonRawView } from "@/components/debug/SkeletonRawView";
import { SkeletonNormalizedView } from "@/components/debug/SkeletonNormalizedView";
import { CameraFeed } from "@/components/camera/CameraFeed";

import { DebugLayout } from "@/components/debug/layout/DebugLayout";
import { DiagnosticCard } from "@/components/debug/ui/DiagnosticCard";
import { ThreeDebugViewer } from "@/components/avatar/ThreeDebugViewer";
import { generateMockPose, generateMockMetrics } from "@/lib/mock/poseMock";

export default function AdminDebugPage() {
  const socket = usePoseSocket();
  const videoRef = useRef<HTMLVideoElement>(null);

  const [showBones, setShowBones] = useState(true);
  const [showJoints, setShowJoints] = useState(true);
  const [showLabels, setShowLabels] = useState(false);
  const debugErrors = usePoseStore((state) => state.debugErrors);
  const socketConnected = usePoseStore((state) => state.socketConnected);

  usePoseStream(socket, videoRef, socketConnected);

  const [useMock, setUseMock] = useState(false);

  // Effect to generate mock data if useMock is true and socket is offline
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (useMock && !socketConnected) {
      interval = setInterval(() => {
        usePoseStore.getState().setRawPose(generateMockPose());
        usePoseStore.getState().setMetrics(generateMockMetrics());
      }, 100); // 10 FPS mock
    }
    return () => clearInterval(interval);
  }, [useMock, socketConnected]);

  return (
    <DebugLayout socketConnected={socketConnected}>
      <div className="grid grid-cols-12 gap-6 pb-20">
        {/* Left Column (Input & Raw Data) - Span 4 */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          <DiagnosticCard title="Video Input" variant="neon">
            <div className="aspect-video bg-black relative rounded-lg overflow-hidden border border-white/5">
              {!useMock ? <CameraFeed ref={videoRef} /> : (
                <div className="w-full h-full flex items-center justify-center text-white/20 font-mono text-xs">
                  [ MOCK DATA STREAM ACTIVE ]
                </div>
              )}
              <div className="overlay-grid" />
            </div>
          </DiagnosticCard>

          <DiagnosticCard title="Gizmos Controls" headerAction={
             <button 
               onClick={() => setUseMock(!useMock)}
               className={`text-[9px] px-2 py-1 rounded border ${useMock ? "border-mint text-mint" : "border-white/10 text-white/30"}`}
             >
               {useMock ? "MOCK: ON" : "MOCK: OFF"}
             </button>
          }>
            <GizmosOverlay
              showBones={showBones}
              showJoints={showJoints}
              showLabels={showLabels}
              onToggleBones={setShowBones}
              onToggleJoints={setShowJoints}
              onToggleLabels={setShowLabels}
            />
          </DiagnosticCard>

          <DiagnosticCard title="System Telemetry">
            <MetricsTable />
          </DiagnosticCard>
        </div>

        {/* Middle Column (Visualizations) - Span 4 */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          <DiagnosticCard title="Raw Skeleton Flux" headerAction={<span className="text-[9px] text-mint">60Hz</span>}>
            <div className="aspect-square bg-black/20 rounded-lg relative overflow-hidden">
               <SkeletonRawView showBones={showBones} showJoints={showJoints} showLabels={showLabels} />
            </div>
          </DiagnosticCard>

          <DiagnosticCard title="Normalized Rig" headerAction={<span className="text-[9px] text-majorelle-blue">MMPose</span>}>
            <div className="aspect-square bg-black/20 rounded-lg relative overflow-hidden">
              <SkeletonNormalizedView showBones={showBones} showJoints={showJoints} showLabels={showLabels} />
            </div>
          </DiagnosticCard>
        </div>

        {/* Right Column (3D Verification) - Span 4 */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          <DiagnosticCard title="3D Space Verification" variant="neon" className="h-[500px]">
             <ThreeDebugViewer modelPath="/3d/MaleBodyWithArmature.glb" />
          </DiagnosticCard>

          {debugErrors.length > 0 && (
            <DiagnosticCard title="Critical Errors" variant="error">
              <ul className="text-xs text-red-400 space-y-2">
                {debugErrors.map((error) => (
                  <li key={error} className="flex gap-2">
                    <span className="opacity-50">!</span> {error}
                  </li>
                ))}
              </ul>
            </DiagnosticCard>
          )}
        </div>
      </div>
    </DebugLayout>
  );
}
