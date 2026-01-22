'use client';

import React from 'react';
import { ArrowUpRight } from 'lucide-react';

/* 
   MASTER DESIGN - UI COMPONENTS
   Minimalist, Swiss-style, Performance-oriented.
*/

interface ZenButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    children: React.ReactNode;
    variant?: 'primary' | 'outline';
}

export const ZenButton: React.FC<ZenButtonProps> = ({ children, variant = 'primary', className = '', ...props }) => (
    <button
        className={`${variant === 'primary' ? 'btn-zen' : 'btn-outline'} ${className} flex items-center justify-between px-6`}
        {...props}
    >
        <span>{children}</span>
        {variant === 'primary' && <ArrowUpRight size={16} />}
    </button>
);

interface TechBadgeProps {
    label: string;
    value: string | number;
}

export const TechBadge: React.FC<TechBadgeProps> = ({ label, value }) => (
    <div className="flex flex-col items-start">
        <span className="label-mono opacity-50 mb-1">{label}</span>
        <span className="font-mono text-xl text-white">{value}</span>
    </div>
);

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    children: React.ReactNode;
}

export const MinimalIconBtn: React.FC<IconButtonProps> = ({ children, className = '', ...props }) => (
    <button
        className={`w-10 h-10 flex items-center justify-center rounded-full border border-white/10 hover:bg-white hover:text-black transition-colors duration-200 ${className}`}
        {...props}
    >
        {children}
    </button>
);

/* Chat Bubble - Minimalist & Integrated */
export const ZenBubble: React.FC<{ message: string; visible: boolean }> = ({ message, visible }) => (
    <div
        className={`absolute bottom-24 right-6 max-w-[220px] transition-all duration-500 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
            }`}
    >
        <div className="bg-white/5 border border-white/10 p-4 backdrop-blur-sm">
            <p className="font-mono text-xs text-secondary leading-relaxed text-[#00ff9d] mb-1">:: SYSTEM</p>
            <p className="text-sm font-light leading-snug">{message}</p>
        </div>
    </div>
);
