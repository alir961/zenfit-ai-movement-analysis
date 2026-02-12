
import sys
import os
import cv2
import numpy as np

# Backend setup
sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))
from app.processing.rtmw3d_runtime import RTMW3DRunner

def test_onnx_real():
    print("Testing ONNX with real frame...")
    
    # 1. Initialize
    runner = RTMW3DRunner(model_size="l")
    if not runner.ready:
        print("Model not ready.")
        return

    print(f"Mode: {'ONNX' if runner.use_onnx else 'PyTorch'}")
    
    # 2. Load Video Frame
    vid_path = r"docs/squat.mp4"
    cap = cv2.VideoCapture(vid_path)
    ret, frame = cap.read()
    if not ret:
        print("Cannot read video.")
        return
        
    # Resize for faster debug
    frame = cv2.resize(frame, (640, 360))
    
    # 3. Infer
    print("Inferring...")
    pose = runner.infer(frame)
    
    if pose:
        print(f"✅ Success! Joints detected: {len(pose['joints'])}")
        print(f"Sample Joint: {pose['joints'][0]}")
    else:
        print("❌ Inference returned None (Check logs)")

if __name__ == "__main__":
    test_onnx_real()
