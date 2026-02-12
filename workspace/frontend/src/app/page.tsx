"use client";

import React, { useMemo, useRef } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { CameraFeed } from "@/components/camera/CameraFeed";
import { PandaCoach } from "@/components/coach/PandaCoach";
import { LiveDetectionPanel } from "@/components/coach/LiveDetectionPanel";
import { usePoseSocket } from "@/hooks/usePoseSocket";
import { usePoseStream } from "@/hooks/usePoseStream";
import { usePoseStore } from "@/lib/poseStore";

const AvatarCanvas = dynamic(() => import("@/components/avatar/AvatarCanvas").then((mod) => mod.AvatarCanvas), {
  ssr: false,
});

export default function HomePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const socket = usePoseSocket();
  const sessionState = usePoseStore((state) => state.sessionState);
  const socketConnected = usePoseStore((state) => state.socketConnected);
  const exercise = usePoseStore((state) => state.exercise);
  const setSessionState = usePoseStore((state) => state.setSessionState);

  usePoseStream(socket, videoRef, sessionState === "running");

  const coachMessage = useMemo(() => {
    if (!socketConnected) return "L'ombre précède le mouvement. Connexion...";
    if (sessionState === "paused" || sessionState === "no_input") return "Prêt pour l'équilibre ?";
    if (exercise.name === "squat") return "Pousse sur tes talons.";
    if (exercise.name === "push_up") return "Garde ton centre solide.";
    if (exercise.name === "burpee") return "Explose vers le haut.";
    return "Respire. Bouge avec intention.";
  }, [exercise.name, sessionState, socketConnected]);

  const handleToggle = () => {
    if (sessionState === "running") {
      setSessionState("paused");
    } else {
      setSessionState("running");
    }
  };

  return (
    <div className="zen-live-container">
      <div className="main-view">
        <header className="minimal-nav">
          <div className="nav-item-pill">
            <span className="text-mint">●</span> PROJECT
          </div>
          <div className="display-large tracking-widest">
            ZEN<span className="text-mint">FIT</span>
          </div>
          <div className="nav-item-pill">
            🔊
          </div>
        </header>

        <div className="flex-1 flex flex-col items-center justify-center gap-12">
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1 }}
            className="text-center"
          >
            <h1 className="harmonie-title glow-text">調和</h1>
            <p className="harmonie-subtitle">Harmonie & Mouvement</p>
          </motion.div>

          <div className="w-full relative glass-card neon-border group animate-neon">
            <div className="absolute inset-0 bg-blur-accent -top-10 -left-10 bg-mint-leaf"></div>
            
            <div className="flex flex-col gap-6 relative z-10">
              <div className="flex items-center gap-4">
                <div className="btn-icon-circle text-mint">👤</div>
                <p className="text-sm font-medium text-lavender">
                  {coachMessage}
                </p>
              </div>

              <button 
                className="btn-commencer"
                onClick={handleToggle}
              >
                {sessionState === "running" ? "PAUSE" : "COMMENCER"}
                <span className="ml-2">→</span>
              </button>
            </div>
          </div>

          <AnimatePresence>
            {sessionState === "running" && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className="w-full flex flex-col gap-6"
              >
                <LiveDetectionPanel />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Floating Background Effects */}
          <div className="fixed -bottom-20 -right-20 w-64 h-64 bg-majorelle-blue blur-[120px] opacity-20 pointer-events-none"></div>
          <div className="fixed -top-20 -left-20 w-64 h-64 bg-mint-leaf blur-[120px] opacity-10 pointer-events-none"></div>
        </div>

        <footer className="p-6 flex justify-between items-center">
          <Link href="/admin_debug" className="text-[10px] uppercase tracking-[0.3em] text-white/30 hover:text-mint transition-colors">
            Debug Stack
          </Link>
          <div className="flex gap-4">
            <div className="nav-item-pill text-[9px] opacity-50">{exercise.repCount} REPS</div>
            <div className={`nav-item-pill text-[9px] ${socketConnected ? "text-mint" : "text-red-500"}`}>
              {socketConnected ? "LIVE" : "OFFLINE"}
            </div>
          </div>
        </footer>

        {/* Camera/Avatar Hidden background processing */}
        <div className="hidden">
          <CameraFeed ref={videoRef} />
          <AvatarCanvas />
        </div>
      </div>
    </div>
  );
}
