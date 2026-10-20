"use client";

import React, { useRef } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { CameraFeed } from "@/components/camera/CameraFeed";
import { LiveDetectionPanel } from "@/components/coach/LiveDetectionPanel";
import { PoseOverlay } from "@/components/coach/PoseOverlay";
import { ExerciseSelector } from "@/components/coach/ExerciseSelector";
import { usePoseSocket } from "@/hooks/usePoseSocket";
import { usePoseStream } from "@/hooks/usePoseStream";
import { usePoseStore } from "@/lib/poseStore";
import { getExercise } from "@/lib/exercises";

const AvatarCanvas = dynamic(() => import("@/components/avatar/AvatarCanvas").then((mod) => mod.AvatarCanvas), {
  ssr: false,
});

export default function HomePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const socket = usePoseSocket();
  const sessionState = usePoseStore((state) => state.sessionState);
  const socketConnected = usePoseStore((state) => state.socketConnected);
  const selectedExercise = usePoseStore((state) => state.selectedExercise);
  const phase = usePoseStore((state) => state.exercise.phase);
  const setSessionState = usePoseStore((state) => state.setSessionState);

  const running = sessionState === "running";
  const exerciseInfo = getExercise(selectedExercise);

  usePoseStream(socket, videoRef, running);

  return (
    <div className="coach">
      <header className="coach__header">
        <div className="brand">
          Zen<span>Fit</span>
        </div>
        <div className="coach__header-actions">
          <span className={`status${socketConnected ? " is-online" : ""}`}>
            <span className="status__dot" />
            {socketConnected ? "Backend connected" : "Backend offline"}
          </span>
          <Link href="/admin_debug" className="link-muted">
            Debug
          </Link>
        </div>
      </header>

      <main className="coach__body">
        <section className="stage">
          {running ? (
            <>
              <CameraFeed ref={videoRef} fit="contain" />
              <PoseOverlay videoRef={videoRef} fit="contain" />
              <div className="stage__hud">
                <span className="hud-chip">
                  <span className="live-dot" /> Live
                </span>
                <span className="hud-chip">{phase}</span>
              </div>
              {exerciseInfo && <p className="stage__hint">{exerciseInfo.framing}</p>}
            </>
          ) : (
            <div className="stage__idle">
              <h1 className="stage__title">Real-time rep counting</h1>
              <p className="stage__lead">
                Pick an exercise, start the camera and ZenFit counts your reps from your pose. Green joints are
                tracked, red ones are out of view.
              </p>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => setSessionState("running")}
                disabled={!socketConnected}
              >
                Start session
              </button>
              {!socketConnected && (
                <p className="stage__warning">
                  Waiting for the backend. Start it with <code>just dev-backend</code>.
                </p>
              )}
            </div>
          )}
        </section>

        <aside className="coach__side">
          <section className="panel">
            <h2 className="eyebrow">Exercise</h2>
            <ExerciseSelector />
          </section>

          <LiveDetectionPanel />

          {running && (
            <button type="button" className="btn btn--danger" onClick={() => setSessionState("paused")}>
              Stop session
            </button>
          )}
        </aside>
      </main>

      {/* Hidden Avatar Worker */}
      <div className="hidden">
        <AvatarCanvas />
      </div>
    </div>
  );
}
