'use client';

import React, { useEffect, useState } from 'react';
import Image from 'next/image';
import { CameraFeed } from '@/components/CameraFeed';
import { PoseOverlay } from '@/components/PoseOverlay';
import { AvatarCanvas } from '@/components/AvatarCanvas';
import { usePoseStore } from '@/lib/poseStore';
import { usePoseDetection } from '@/hooks/usePoseDetection';

// Icons using lucide-react as fallback or Google Material Symbols if loaded
import { ArrowRight, Volume2, VolumeX, Download, Square, Link as LinkIcon } from 'lucide-react';

const MESSAGES = {
  idle: "Prêt à t'entraîner ?",
  calibrating: "Aligne ton corps avec la grille.",
  countdown: "Préparez-vous...",
  active: "Mode Performance Activé.",
};

export default function Home() {
  const { status, setStatus, score, combo, reset, pandaMessage, setPandaMessage } = usePoseStore();
  const { videoRef } = usePoseDetection();

  const [muted, setMuted] = useState(false);
  const [countdown, setCountdown] = useState(3);
  const [countRingOffset, setCountRingOffset] = useState(377);

  // Update system message
  useEffect(() => {
    setPandaMessage(MESSAGES[status] || MESSAGES.idle);
  }, [status, setPandaMessage]);

  // Handle countdown logic
  useEffect(() => {
    if (status !== 'countdown') {
      setCountdown(3); // Reset when not in countdown
      return;
    }

    setCountRingOffset(0);
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [status]);

  // Trigger active mode when countdown hits 0
  useEffect(() => {
    if (status === 'countdown' && countdown === 0) {
      setStatus('active');
    }
  }, [countdown, status, setStatus]);

  // Handle sound toggle
  const toggleMute = () => {
    const video = videoRef.current;
    if (video) {
      video.muted = !video.muted;
      setMuted(!video.muted);
    }
  };

  return (
    <main className="h-screen w-screen bg-black flex items-center justify-center overflow-hidden">
      {/* App Container (Mobile Aspect Ratio Preserved like original) */}
      <div className="relative w-full h-full max-w-md bg-black overflow-hidden shadow-2xl sm:rounded-3xl border-0 sm:border border-[#222]">

        {/* Download Project Button */}
        <button className="download-btn" onClick={() => window.open('https://github.com/alir961/ZenFit', '_blank')}>
          <Download size={12} className="mr-1" />
          <span>Project</span>
        </button>

        {/* 1. Background (Dark Zen) */}
        <div className="absolute inset-0 z-0 opacity-40">
          {/* Fallback pattern or image if original BLOB is not accessible. Using a gradient for now. */}
          <div className="w-full h-full object-cover grayscale bg-[url('https://images.unsplash.com/photo-1550684848-fac1c5b4e853?q=80&w=2070&auto=format&fit=crop')] bg-cover bg-center" />
          <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent"></div>
        </div>

        {/* 2. Video & CV Layer */}
        <div className="absolute inset-0 z-10 flex flex-col">
          <div id="video-container">
            <CameraFeed ref={videoRef} className="opacity-60" />
            <PoseOverlay />
            {/* Overlay Grid (Subtle) */}
            <div className="absolute inset-0 z-20 pointer-events-none bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTTAgNDBMMCAwTDQwIDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsIDI1NSwgMjU1LCAwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIiAvPjwvc3ZnPg==')] opacity-30"></div>
          </div>
          {/* Avatar Layer on top of everything if active */}
          {status === 'active' && (
            <div className="absolute inset-0 z-25 pointer-events-none">
              <AvatarCanvas />
            </div>
          )}
        </div>

        {/* 3. UI Layer */}
        <div className="absolute inset-0 z-30 p-6 flex flex-col justify-between pointer-events-none">

          {/* Header */}
          <header className="flex justify-end items-start pointer-events-auto mt-2">
            <div className="flex flex-col items-end mr-4">
              <h1 className="font-outfit font-bold text-2xl text-white tracking-tighter">ZEN<span className="text-[#00ff9d]">FIT</span></h1>
              <div className="h-0.5 w-8 bg-[#00ff9d] mt-1"></div>
            </div>
            <button
              className="w-10 h-10 rounded-full border border-white/10 bg-black/40 backdrop-blur-md flex items-center justify-center text-white/70 hover:text-white transition-colors"
              onClick={toggleMute}
            >
              {muted ? <VolumeX size={20} /> : <Volume2 size={20} />}
            </button>
          </header>

          {/* Main Content Views */}
          <div className="relative flex-grow pointer-events-none">

            {/* INTRO */}
            <section className={`view-section ${status === 'idle' ? 'active' : ''}`} id="view-intro">
              <div className="text-center space-y-2 mb-8">
                <h2 className="font-outfit text-5xl font-light text-white mb-2">ZEN<span className="text-[#00ff9d]">FIT</span></h2>
                <p className="text-gray-400 text-xs tracking-[0.3em] uppercase">Corps & Esprit</p>
              </div>
              <div className="glass-sharp p-6 rounded-2xl w-full border-l-2 border-[#00ff9d]">
                <div className="flex items-center gap-4 mb-4">
                  <span className="material-symbols-outlined text-[#00ff9d]"><ArrowRight /></span>
                  <p className="text-sm font-light text-gray-200">Coach postural intelligent.</p>
                </div>
                <button
                  className="w-full bg-[#00ff9d] text-black font-bold py-4 rounded-xl hover:bg-[#00cc7d] transition-colors flex items-center justify-center gap-2 group pointer-events-auto"
                  onClick={() => setStatus('calibrating')}
                >
                  <span>COMMENCER</span>
                  <ArrowRight className="group-hover:translate-x-1 transition-transform" size={18} />
                </button>
              </div>
            </section>

            {/* CALIBRATION */}
            <section className={`view-section ${status === 'calibrating' ? 'active' : ''}`} id="view-calibration">
              {/* Box removed per user request */}

              <div className="flex flex-col items-center justify-center gap-6 w-[80%] pointer-events-auto">
                <p className="text-sm font-light text-gray-200 text-center animate-pulse">
                  Prêt à commencer ?
                </p>
                <button
                  className="w-full max-w-[200px] py-4 text-xs font-bold uppercase tracking-widest text-black bg-[#00ff9d] rounded-xl hover:bg-[#00cc7d] transition-colors shadow-[0_0_20px_rgba(0,255,157,0.3)]"
                  onClick={() => setStatus('active')}
                >
                  Mode Libre
                </button>
              </div>
            </section>

            {/* COUNTDOWN */}
            <section className={`view-section ${status === 'countdown' ? 'active' : ''}`} id="view-countdown">
              <div className="relative flex items-center justify-center">
                <svg className="w-32 h-32 -rotate-90">
                  <circle cx="64" cy="64" r="60" fill="none" stroke="#222" strokeWidth="4"></circle>
                  <circle
                    cx="64"
                    cy="64"
                    r="60"
                    fill="none"
                    stroke="#00ff9d"
                    strokeWidth="4"
                    strokeDasharray="377"
                    strokeDashoffset={countRingOffset} // Use state for animation if needed or just CSS
                    className="transition-all duration-1000 ease-linear"
                  ></circle>
                </svg>
                <span className="absolute font-jp text-5xl font-bold">{countdown}</span>
              </div>
              <p className="mt-6 text-xs text-[#00ff9d] tracking-[0.2em] uppercase animate-pulse">Analyse...</p>
            </section>

            {/* ACTIVE */}
            <section className={`view-section !justify-start pt-4 ${status === 'active' ? 'active' : ''}`} id="view-active">
              {/* HUD */}
              <div className="w-full flex justify-between px-2 mb-8">
                <div className="glass-sharp px-3 py-2 rounded-lg border-l-2 border-[#00ff9d]">
                  <span className="block text-[8px] text-gray-400 uppercase tracking-wide">Posture</span>
                  <span className="font-mono text-xl font-bold" id="score">{score}%</span>
                </div>
                <div className="glass-sharp px-3 py-2 rounded-lg text-right">
                  <span className="block text-[8px] text-gray-400 uppercase tracking-wide">Combo</span>
                  <span className="font-mono text-xl font-bold text-purple-400" id="combo">x{combo}</span>
                </div>
              </div>

              {/* Feedback Zone (Could be used for text feedback overlays) */}
              <div className="relative w-full h-40 flex items-center justify-center pointer-events-none" id="feedback-zone">
                {/* Dynamic Text Appears Here */}
              </div>

              {/* Stop Button */}
              <button
                className="absolute bottom-4 left-4 w-12 h-12 rounded-full border border-red-500/30 text-red-500 hover:bg-red-500/10 flex items-center justify-center transition-colors pointer-events-auto"
                onClick={() => reset()}
              >
                <Square size={20} fill="currentColor" />
              </button>
            </section>

          </div>

          {/* Footer / Panda Avatar */}
          <div className="pointer-events-auto absolute bottom-0 right-0 p-4 z-50 flex flex-col items-end">
            {/* Chat Bubble */}
            <div className={`mb-2 mr-2 glass-sharp px-4 py-3 rounded-2xl rounded-tr-none max-w-[200px] transform transition-all duration-500 origin-bottom-right ${pandaMessage ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`} id="panda-bubble">
              <p className="text-xs text-gray-100 font-medium leading-relaxed">{pandaMessage}</p>
            </div>
            {/* Avatar (The PNG Illusion) */}
            <div className="avatar-container relative w-32 h-32 cursor-pointer hover:scale-105 transition-transform" onClick={() => { }}>
              {/* Glow behind */}
              <div className="absolute bottom-0 right-0 w-24 h-24 bg-[#00ff9d] blur-[50px] opacity-20 rounded-full"></div>
              {/* Image */}
              <img src="panda.png" alt="Coach" className="w-full h-full object-contain object-top drop-shadow-2xl" />
            </div>
          </div>

        </div>

      </div>
    </main>
  );
}
