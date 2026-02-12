
import sys
import os
import cv2
import time
import numpy as np
import torch

# Backend setup
sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))
from app.processing.rtmw3d_runtime import RTMW3DRunner

def benchmark():
    print("🚀 Benchmarking RTMW3D: PyTorch vs ONNX (Real Frame)")
    
    # Load Real Frame
    vid_path = r"docs/squat.mp4"
    cap = cv2.VideoCapture(vid_path)
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to load frame from docs/squat.mp4")
        return
    cap.release()
    
    # Resize to standard processing size
    frame = cv2.resize(frame, (640, 480))
    print(f"Frame Size: {frame.shape}")

    # 1. Warmup PyTorch
    print("\n--- PyTorch (Warmup) ---")
    runner_pt = RTMW3DRunner(model_size="l")
    runner_pt.use_onnx = False 
    
    for _ in range(3):
        runner_pt.infer(frame)
        
    # Measure PyTorch
    t0 = time.perf_counter()
    N = 10
    for _ in range(N):
        res = runner_pt.infer(frame)
        if res is None:
            print("⚠️ PyTorch returned None (Detection failed?)")
    t1 = time.perf_counter()
    fps_pt = N / (t1 - t0)
    print(f"✅ PyTorch FPS: {fps_pt:.2f}")

    # 2. Warmup ONNX
    print("\n--- ONNX (Warmup) ---")
    runner_onnx = RTMW3DRunner(model_size="l")
    if not runner_onnx.use_onnx:
        print("❌ ONNX model not found.")
        return

    print(f"🔌 ONNX Providers: {runner_onnx._ort_session.get_providers()}")
    
    for _ in range(3):
        runner_onnx.infer(frame)
        
    # Measure ONNX
    t0 = time.perf_counter()
    for _ in range(N):
        res = runner_onnx.infer(frame)
        if res is None:
            print("⚠️ ONNX returned None (Detection failed?)")
    t1 = time.perf_counter()
    fps_onnx = N / (t1 - t0)
    print(f"✅ ONNX FPS:    {fps_onnx:.2f}")
    
    print("\n--- Result ---")
    speedup = fps_onnx / fps_pt
    print(f"Speedup: {speedup:.2f}x")

if __name__ == "__main__":
    benchmark()
