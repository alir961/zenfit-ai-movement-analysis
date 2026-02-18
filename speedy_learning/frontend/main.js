import { CameraCapture } from "./camera.js";
import { CameraStreamClient } from "./camera_stream_client.js";
import { processSnapshot, fetchHealth } from "./protocol.js";
import {
  setPredictionPayload,
  setPredictionOverlayVisibility,
  getRuntimeInfo
} from "./renderer.js";

const ui = {
  camVideo: document.getElementById("camPreview"),
  camProcessedPreview: document.getElementById("camProcessedPreview"),
  processBtn: document.getElementById("btnProcess"),
  startStreamBtn: document.getElementById("btnStartStream"),
  stopStreamBtn: document.getElementById("btnStopStream"),
  streamFps: document.getElementById("streamFps"),
  saveBtn: document.getElementById("btnSavePayload"),
  endpoint: document.getElementById("endpoint"),
  status: document.getElementById("status"),
  streamStats: document.getElementById("streamStats"),
  overlayRaw: document.getElementById("toggleRaw17"),
  overlayRawNormalized: document.getElementById("toggleRaw17Normalized"),
  normalizedMode: document.getElementById("normalizedMode"),
  overlayMapped: document.getElementById("toggleMapped"),
  payloadMeta: document.getElementById("payloadMeta"),
  payloadDebug: document.getElementById("payloadDebug")
};

const sessionId = (crypto.randomUUID ? crypto.randomUUID() : `sess_${Date.now()}`);
let frameId = 0;
let lastPayload = null;
let streamClient = null;

function setStatus(message, isError = false) {
  if (!ui.status) return;
  ui.status.textContent = message;
  ui.status.style.color = isError ? "#ff8f8f" : "#b7d7ff";
}

function pickDebugSubset(payload) {
  return {
    meta: payload?.meta,
    detector: payload?.detector,
    debug: payload?.debug,
    postprocess: {
      ik_max_length: payload?.postprocess?.ik_max_length,
      yaw_deg: payload?.postprocess?.yaw_deg,
      regularization: payload?.postprocess?.regularization
    },
    gaussian: payload?.gaussian
  };
}

function renderPayload(payload) {
  if (!payload) return;
  const runtime = getRuntimeInfo();
  const normMode = ui.normalizedMode?.value || "easy";
  ui.payloadMeta.textContent = [
    `session=${payload?.meta?.session_id || sessionId}`,
    `frame=${payload?.meta?.frame_id ?? frameId}`,
    `latency=${payload?.meta?.latency_ms ?? "n/a"}ms`,
    `providers=${(payload?.meta?.providers || []).join(",") || "n/a"}`,
    `norm_mode=${normMode}`,
    `three=r${runtime.revision}`,
    `mesh=${runtime.currentMesh || "none"}`
  ].join(" | ");

  ui.payloadDebug.textContent = JSON.stringify(pickDebugSubset(payload), null, 2);
}

function overlayPayloadForMode(payload) {
  const mode = ui.normalizedMode?.value || "easy";
  if (mode === "transformed" && payload?.pose_raw17_transformed) {
    return {
      ...payload,
      pose_raw17_normalized: payload.pose_raw17_transformed
    };
  }
  if (mode === "full" && payload?.pose_raw17_normalized_full) {
    return {
      ...payload,
      pose_raw17_normalized: payload.pose_raw17_normalized_full
    };
  }
  return payload;
}

async function bootCamera() {
  if (!ui.camVideo) return null;
  const camera = new CameraCapture(ui.camVideo, { width: 960, height: 540 });
  try {
    await camera.start();
    setStatus("camera ready");
    return camera;
  } catch (error) {
    setStatus(`camera error: ${error.message}`, true);
    return null;
  }
}

function hookOverlayToggles() {
  ui.overlayRaw?.addEventListener("change", () => {
    setPredictionOverlayVisibility("rtmw3d_raw17", !!ui.overlayRaw.checked);
  });
  ui.overlayRawNormalized?.addEventListener("change", () => {
    setPredictionOverlayVisibility("***REMOVED***", !!ui.overlayRawNormalized.checked);
  });
  ui.overlayMapped?.addEventListener("change", () => {
    setPredictionOverlayVisibility("rtmw3d_mapped_humanoid", !!ui.overlayMapped.checked);
  });
}

function saveBlobToFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function saveFrameSnapshot(camera) {
  if (!camera) {
    setStatus("camera unavailable", true);
    return;
  }
  try {
    const snap = await camera.captureJpegBlob(0.92);
    const now = Date.now();
    saveBlobToFile(snap.blob, `speedy_frame_${now}.jpg`);
    if (lastPayload) {
      const payloadBlob = new Blob([JSON.stringify(lastPayload, null, 2)], { type: "application/json" });
      saveBlobToFile(payloadBlob, `speedy_payload_${lastPayload?.meta?.frame_id ?? now}.json`);
      setStatus("frame + payload saved");
    } else {
      setStatus("frame saved");
    }
  } catch (error) {
    setStatus(`save frame error: ${error.message}`, true);
  }
}

function makeStreamClient() {
  return new CameraStreamClient({
    processedImgEl: ui.camProcessedPreview,
    fpsTarget: Number(ui.streamFps?.value || 15),
    onStatus: (msg) => {
      if (!ui.streamStats) return;
      if (msg?.type === "stats") {
        const livePayload = msg?.summary?.payload || null;
        if (livePayload) {
          lastPayload = livePayload;
          setPredictionPayload(overlayPayloadForMode(livePayload));
          renderPayload(livePayload);
        }
        const st = msg?.state || {};
        ui.streamStats.textContent =
          `stream owner=${msg.owner_client_id || "none"} qin=${msg.buffer_in ?? 0} qout=${msg.buffer_out ?? 0} in=${st.frames_in ?? 0} proc=${st.frames_processed ?? 0} out=${st.frames_out ?? 0} drop=${st.frames_dropped ?? 0} fps=${st.fps_target ?? "-"}`;
      } else if (msg?.type === "hello") {
        ui.streamStats.textContent = `stream connected client=${msg.client_id} fps=${msg.fps_target}`;
      } else if (msg?.type === "error") {
        ui.streamStats.textContent = `stream error ${msg.code || ""}: ${msg.message || ""}`;
      } else if (msg?.type === "ws") {
        ui.streamStats.textContent = `stream ${msg.state || "idle"} fps=${msg.fps_target || "-"}`;
      }
    }
  });
}

function buildCameraState(camera, capture) {
  const track = camera?.stream?.getVideoTracks?.()[0] || null;
  const settings = track?.getSettings?.() || {};
  const width = Number(capture?.width || settings.width || 0);
  const height = Number(capture?.height || settings.height || 0);
  const fps = Number(settings.frameRate || 0);
  return {
    camera_id: track?.id || "browser_camera",
    width,
    height,
    fps,
    timestamp_ms: Date.now()
  };
}

async function main() {
  hookOverlayToggles();
  setPredictionOverlayVisibility("rtmw3d_raw17", !!ui.overlayRaw?.checked);
  setPredictionOverlayVisibility("***REMOVED***", !!ui.overlayRawNormalized?.checked);
  setPredictionOverlayVisibility("rtmw3d_mapped_humanoid", !!ui.overlayMapped?.checked);

  try {
    const health = await fetchHealth("/health");
    setStatus(`backend ok: ${health.providers.join(",")}`);
  } catch (error) {
    setStatus(`backend warning: ${error.message}`, true);
  }

  let camera = await bootCamera();
  streamClient = makeStreamClient();

  ui.processBtn?.addEventListener("click", async () => {
    if (!camera) {
      camera = await bootCamera();
      if (!camera) {
        setStatus("camera unavailable", true);
        return;
      }
    }

    ui.processBtn.disabled = true;
    const started = performance.now();
    try {
      const capture = await camera.captureJpegBlob(0.92);
      frameId += 1;
      const payload = await processSnapshot({
        endpoint: ui.endpoint?.value || "/process",
        imageBlob: capture.blob,
        timestampMs: Date.now(),
        sessionId,
        frameId,
        cameraState: buildCameraState(camera, capture)
      });
      lastPayload = payload;
      setPredictionPayload(overlayPayloadForMode(payload));
      renderPayload(payload);
      setStatus(`processed frame ${frameId} in ${Math.round(performance.now() - started)}ms`);
    } catch (error) {
      setStatus(`process error: ${error.message}`, true);
    } finally {
      ui.processBtn.disabled = false;
    }
  });

  ui.saveBtn?.addEventListener("click", async () => {
    await saveFrameSnapshot(camera);
  });

  ui.startStreamBtn?.addEventListener("click", async () => {
    if (!camera) {
      camera = await bootCamera();
      if (!camera) {
        setStatus("camera unavailable", true);
        return;
      }
    }
    try {
      streamClient.setFpsTarget(Number(ui.streamFps?.value || 15));
      await streamClient.startStreaming(camera);
      setStatus("stream started");
    } catch (error) {
      setStatus(`stream start error: ${error.message}`, true);
    }
  });

  ui.stopStreamBtn?.addEventListener("click", () => {
    try {
      streamClient.stopStreaming();
      setStatus("stream stopped");
    } catch (error) {
      setStatus(`stream stop error: ${error.message}`, true);
    }
  });

  ui.streamFps?.addEventListener("change", () => {
    streamClient?.setFpsTarget(Number(ui.streamFps.value || 15));
  });
  ui.normalizedMode?.addEventListener("change", () => {
    if (lastPayload) {
      setPredictionPayload(overlayPayloadForMode(lastPayload));
      renderPayload(lastPayload);
    }
  });

  window.addEventListener("beforeunload", () => {
    try {
      streamClient?.disconnect();
    } catch {
      // noop
    }
  });
}

main();
