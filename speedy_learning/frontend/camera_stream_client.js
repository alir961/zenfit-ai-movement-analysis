export class CameraStreamClient {
  constructor({ processedImgEl, endpointWs, fpsTarget = 15, onStatus = null } = {}) {
    this.processedImgEl = processedImgEl;
    this.endpointWs = endpointWs;
    this.fpsTarget = fpsTarget;
    this.onStatus = onStatus;

    this.ws = null;
    this.captureTimer = null;
    this.streaming = false;
    this.cameraCapture = null;
    this.lastBlobUrl = null;
    this.sessionId = null;
    this.clientId = null;
  }

  _emitStatus(payload) {
    if (typeof this.onStatus === "function") this.onStatus(payload);
  }

  _wsUrl() {
    if (this.endpointWs) return this.endpointWs;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/camera/stream/ws`;
  }

  async connect({ sessionId = null } = {}) {
    this.sessionId = sessionId;
    const url = new URL(this._wsUrl());
    if (sessionId) url.searchParams.set("session_id", sessionId);
    url.searchParams.set("fps_target", String(this.fpsTarget));

    this.ws = new WebSocket(url.toString());
    this.ws.binaryType = "arraybuffer";

    await new Promise((resolve, reject) => {
      const onOpen = () => {
        this.ws.removeEventListener("open", onOpen);
        this.ws.removeEventListener("error", onError);
        resolve();
      };
      const onError = (e) => {
        this.ws.removeEventListener("open", onOpen);
        this.ws.removeEventListener("error", onError);
        reject(new Error(`ws open error: ${e?.message || "unknown"}`));
      };
      this.ws.addEventListener("open", onOpen);
      this.ws.addEventListener("error", onError);
    });

    this.ws.addEventListener("message", (event) => this._handleMessage(event));
    this.ws.addEventListener("close", () => {
      this.streaming = false;
      this._emitStatus({ type: "ws", state: "closed" });
    });
  }

  _handleMessage(event) {
    if (typeof event.data === "string") {
      let msg = null;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (msg.type === "hello") {
        this.clientId = msg.client_id;
      }
      this._emitStatus(msg);
      return;
    }

    const data = event.data;
    const blob = data instanceof Blob ? data : new Blob([data], { type: "image/jpeg" });
    if (this.lastBlobUrl) URL.revokeObjectURL(this.lastBlobUrl);
    this.lastBlobUrl = URL.createObjectURL(blob);
    if (this.processedImgEl) this.processedImgEl.src = this.lastBlobUrl;
  }

  setFpsTarget(n) {
    this.fpsTarget = Math.max(1, Number(n) || 15);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "set_fps", fps_target: this.fpsTarget }));
    }
    if (this.streaming) {
      this.stopStreaming();
      this.startStreaming(this.cameraCapture);
    }
  }

  async startStreaming(cameraCapture) {
    this.cameraCapture = cameraCapture;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      await this.connect({ sessionId: this.sessionId });
    }
    if (!this.cameraCapture) throw new Error("camera capture missing");

    this.streaming = true;
    const tick = async () => {
      if (!this.streaming || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      try {
        const snap = await this.cameraCapture.captureJpegBlob(0.82);
        const arr = await snap.blob.arrayBuffer();
        this.ws.send(arr);
      } catch (error) {
        this._emitStatus({ type: "error", code: "CAPTURE_FAIL", message: String(error?.message || error) });
      }
    };

    await tick();
    this.captureTimer = window.setInterval(tick, Math.max(30, Math.round(1000 / this.fpsTarget)));
    this._emitStatus({ type: "ws", state: "streaming", fps_target: this.fpsTarget });
  }

  stopStreaming() {
    this.streaming = false;
    if (this.captureTimer) {
      clearInterval(this.captureTimer);
      this.captureTimer = null;
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "stop" }));
    }
  }

  disconnect() {
    this.stopStreaming();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // noop
      }
      this.ws = null;
    }
    if (this.lastBlobUrl) {
      URL.revokeObjectURL(this.lastBlobUrl);
      this.lastBlobUrl = null;
    }
  }
}
