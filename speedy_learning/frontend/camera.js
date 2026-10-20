export class CameraCapture {
  constructor(videoEl, { width = 640, height = 360 } = {}) {
    this.videoEl = videoEl;
    this.width = width;
    this.height = height;
    this.stream = null;
    this.canvas = document.createElement("canvas");
    this.canvas.width = width;
    this.canvas.height = height;
    this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });
  }

  async start() {
    if (!this.videoEl) throw new Error("video element missing");
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("getUserMedia unavailable");
    }

    const tries = [
      {
        video: {
          width: { ideal: this.width },
          height: { ideal: this.height }
        },
        audio: false
      },
      { video: true, audio: false }
    ];

    let lastError = null;
    for (const constraints of tries) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia(constraints);
        break;
      } catch (err) {
        lastError = err;
      }
    }
    if (!this.stream) {
      throw lastError || new Error("unable to open camera");
    }

    this.videoEl.srcObject = this.stream;
    if (this.videoEl.readyState < 2) {
      await new Promise((resolve) => {
        const onReady = () => {
          this.videoEl.removeEventListener("loadedmetadata", onReady);
          resolve();
        };
        this.videoEl.addEventListener("loadedmetadata", onReady, { once: true });
        setTimeout(resolve, 1000);
      });
    }
    await this.videoEl.play();
  }

  stop() {
    if (!this.stream) return;
    for (const track of this.stream.getTracks()) track.stop();
    this.stream = null;
    this.videoEl.srcObject = null;
  }

  async captureJpegBlob(quality = 0.92) {
    if (!this.videoEl) {
      throw new Error("camera unavailable");
    }
    if (this.videoEl.readyState < 2) {
      await new Promise((resolve) => setTimeout(resolve, 120));
    }
    if (this.videoEl.readyState < 2) {
      throw new Error("camera frame unavailable");
    }

    const vw = this.videoEl.videoWidth || this.width;
    const vh = this.videoEl.videoHeight || this.height;
    if (this.canvas.width !== vw || this.canvas.height !== vh) {
      this.canvas.width = vw;
      this.canvas.height = vh;
    }
    this.ctx.drawImage(this.videoEl, 0, 0, vw, vh);

    const blob = await new Promise((resolve, reject) => {
      this.canvas.toBlob((b) => {
        if (!b) reject(new Error("failed to encode jpeg"));
        else resolve(b);
      }, "image/jpeg", quality);
    });

    return {
      blob,
      width: vw,
      height: vh
    };
  }
}
