import { create } from 'zustand';
import { PoseFrame, RigMap } from './contracts';

interface PoseState {
    currentFrame: PoseFrame | null;
    rigMap: RigMap | null;
    score: number;
    combo: number;
    status: 'idle' | 'calibrating' | 'active' | 'countdown';
    pandaMessage: string;

    setFrame: (frame: PoseFrame) => void;
    setRigMap: (rigMap: RigMap) => void;
    setScore: (score: number) => void;
    setCombo: (combo: number) => void;
    setStatus: (status: PoseState['status']) => void;
    setPandaMessage: (msg: string) => void;
    reset: () => void;
}

export const usePoseStore = create<PoseState>((set) => ({
    currentFrame: null,
    rigMap: null,
    score: 0,
    combo: 0,
    status: 'idle',
    pandaMessage: 'Prêt à t\'entraîner ?',

    setFrame: (frame) => set({ currentFrame: frame }),
    setRigMap: (rigMap) => set({ rigMap }),
    setScore: (score) => set({ score }),
    setCombo: (combo) => set({ combo }),
    setStatus: (status) => set({ status }),
    setPandaMessage: (pandaMessage) => set({ pandaMessage }),
    reset: () => set({ currentFrame: null, rigMap: null, score: 0, combo: 0, status: 'idle', pandaMessage: 'Prêt à t\'entraîner ?' }),
}));
