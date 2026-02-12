import { usePoseStore } from './poseStore';

export class PosePipeline {
    private worker: Worker | null = null;
    private canvas: OffscreenCanvas | null = null;
    private ctx: OffscreenCanvasRenderingContext2D | null = null;
    private lastProcessTime = 0;
    private readonly THROTTLE_MS = 100; // Process max 10 times per second
    private isProcessing = false;

    constructor() {
        if (typeof window !== 'undefined') {
            this.worker = new Worker(new URL('../workers/pose.worker.ts', import.meta.url));
            this.worker.onmessage = (event) => {
                if (event.data.type === 'POSE_RESULT') {
                    usePoseStore.getState().setFrame(event.data.pose);
                }
                this.isProcessing = false;
            };
        }
    }

    public processVideo(video: HTMLVideoElement) {
        if (!this.worker || this.isProcessing) return;

        const now = performance.now();
        if (now - this.lastProcessTime < this.THROTTLE_MS) return;

        this.lastProcessTime = now;
        this.isProcessing = true;

        // Create canvas lazily with smaller dimensions for performance
        if (!this.canvas || this.canvas.width !== Math.floor(video.videoWidth / 4)) {
            this.canvas = new OffscreenCanvas(
                Math.floor(video.videoWidth / 4) || 160,
                Math.floor(video.videoHeight / 4) || 120
            );
            this.ctx = this.canvas.getContext('2d', { alpha: false });
        }

        if (this.ctx && this.canvas) {
            this.ctx.drawImage(video, 0, 0, this.canvas.width, this.canvas.height);
            const imageBitmap = this.canvas.transferToImageBitmap();
            this.worker.postMessage({ image: imageBitmap, timestamp: now }, [imageBitmap]);
        }
    }

    public destroy() {
        this.worker?.terminate();
        this.worker = null;
    }
}

export const posePipeline = new PosePipeline();
