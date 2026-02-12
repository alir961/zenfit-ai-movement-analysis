import React from "react";
import Link from "next/link";
import { StatusBadge } from "../ui/StatusBadge";

interface DebugLayoutProps {
  children: React.ReactNode;
  socketConnected: boolean;
}

export const DebugLayout: React.FC<DebugLayoutProps> = ({ children, socketConnected }) => {
  return (
    <div className="zen-debug-container font-mono text-sm antialiased text-gray-300">
      <div className="main-view h-full flex flex-col p-4 bg-black/95">
        
        {/* Header Bar */}
        <header className="flex justify-between items-center pb-4 mb-4 border-b border-white/10">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <span className="text-majorelle-blue">DEBUG</span>CORE
            </h1>
            <span className="text-[10px] text-white/40 uppercase tracking-[0.2em] px-2 border-l border-white/10">
              System Diagnostics
            </span>
          </div>

          <div className="flex items-center gap-4">
            <StatusBadge 
              status={socketConnected ? "online" : "offline"} 
              label={`Socket ${socketConnected ? "Connected" : "Disconnected"}`} 
              pulse={socketConnected}
            />
            <Link 
              href="/" 
              className="text-[10px] uppercase tracking-widest text-white/60 hover:text-mint transition-colors border border-white/10 px-3 py-1.5 rounded-full hover:border-mint/30"
            >
              Exit Debug Mode →
            </Link>
          </div>
        </header>

        {/* Main Content Area - Auto-scrolling grid */}
        <main className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
          {children}
        </main>

        {/* Footer Status Line */}
        <footer className="pt-2 mt-2 border-t border-white/5 flex justify-between text-[10px] text-white/30 uppercase tracking-wider">
          <div>RTMW3D Inference Engine v1.0</div>
          <div>ZenFit Systems</div>
        </footer>
      </div>
    </div>
  );
};
