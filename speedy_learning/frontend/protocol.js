export async function processSnapshot({ endpoint = "/process", imageBlob, timestampMs, sessionId, frameId, cameraState = null }) {
  if (!imageBlob) throw new Error("imageBlob is required");

  const fd = new FormData();
  fd.append("image", imageBlob, `frame_${frameId || Date.now()}.jpg`);
  fd.append("timestamp_ms", String(timestampMs || Date.now()));
  if (sessionId) fd.append("session_id", sessionId);
  if (frameId != null) fd.append("frame_id", String(frameId));
  if (cameraState) fd.append("camera_state", JSON.stringify(cameraState));
  if (cameraState?.width != null) fd.append("camera_width", String(cameraState.width));
  if (cameraState?.height != null) fd.append("camera_height", String(cameraState.height));
  if (cameraState?.fps != null) fd.append("camera_fps", String(cameraState.fps));

  const res = await fetch(endpoint, {
    method: "POST",
    body: fd
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`invalid JSON response (${res.status}): ${text.slice(0, 500)}`);
  }

  if (!res.ok) {
    const message = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(message);
  }

  return data;
}

export async function fetchHealth(endpoint = "/health") {
  const res = await fetch(endpoint);
  if (!res.ok) throw new Error(`health check failed: ${res.status}`);
  return res.json();
}

