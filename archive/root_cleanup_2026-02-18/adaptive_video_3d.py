
import cv2
import time
import os
import sys
import argparse
import numpy as np
import torch

# Backend setup
sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))
from app.processing.rtmw3d_runtime import RTMW3DRunner

# --- 2D VISUALIZATION CONSTANTS ---
# COCO 17-Keypoints Topology (Standard)
# 0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear
# 5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow
# 9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip
# 13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle

SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),           # Face
    (5, 6), (5, 7), (7, 9),                   # Left Arm
    (6, 8), (8, 10),                          # Right Arm
    (5, 11), (6, 12),                         # Torso
    (11, 12),                                 # Hips
    (11, 13), (13, 15),                       # Left Leg
    (12, 14), (14, 16)                        # Right Leg
]

# (B, G, R) Colors
C_FACE = (255, 255, 0)   # Cyan
C_L_ARM = (0, 255, 0)    # Green
C_R_ARM = (0, 0, 255)    # Red
C_BODY = (255, 150, 0)   # Blueish
C_LEGS = (180, 180, 180) # Grey

class AdaptiveVideoProcessor:
    def __init__(self, video_path, model_size="l"):
        print(f"🎥 [Adaptive3D] Initializing Video Processor...")
        self.video_path = video_path
        
        # 1. Initialize CAP
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print(f"❌ Error: Cannot open video {video_path}")
            sys.exit(1)
            
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"   Video Info: {self.width}x{self.height} @ {self.fps:.2f} FPS")

        # 2. Performance Settings
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            print("🚀 [Adaptive3D] CuDNN Benchmark Enabled")
        
        # 3. Model
        print(f"⏳ Loading RTMW3D-{model_size.upper()}...")
        self.runner = RTMW3DRunner(model_size=model_size, device="auto")
        if not self.runner.ready:
            print("❌ Model failed to load.")
            sys.exit(1)
            
        # 4. Calibration State
        self.inference_time_ms = 0.0
        self.process_interval = 1 
        self.last_pose = None
        self.biometrics = {}
        self.scale_factor = 0.47 # Default metric scale

    def calibrate_performance(self, num_frames=10):
        print(f"\n⚡ [Adaptive3D] Calibrating Performance (Running {num_frames} frames)...")
        
        # Use a resize for consistent input
        input_size = (640, 360)
        
        times = []
        for _ in range(num_frames):
            ret, frame = self.cap.read()
            if not ret: break
            
            resized = cv2.resize(frame, input_size)
            
            t0 = time.perf_counter()
            _ = self.runner.infer(resized)
            t1 = time.perf_counter()
            times.append(t1 - t0)
            
        avg_time = sum(times) / len(times)
        self.inference_time_ms = avg_time * 1000
        
        max_model_fps = 1.0 / avg_time
        optimal_interval = int(np.ceil(self.fps / max_model_fps))
        
        # Add 10% safety margin
        safe_max_fps = 1.0 / (avg_time * 1.1) 
        self.process_interval = int(np.ceil(self.fps / safe_max_fps))
        
        # Reset video
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        print(f"   Avg Inference: {self.inference_time_ms:.2f} ms")
        print(f"   Max Model FPS: {max_model_fps:.2f} FPS")
        print(f"   Video FPS:     {self.fps:.2f} FPS")
        print(f"✅ OPTIMAL INTERVAL: Process every {self.process_interval} frame(s)")
        print(f"   (This ensures real-time playback speed)")

    def run(self):
        self.calibrate_performance()
        
        print("\n▶️  Starting Adaptive Playback...")
        print("⌨️  Controls: [Q] Quit | [SPACE] Pause")
        
        frame_idx = 0
        input_size = (640, 360) # Optimization
        paused = False
        
        # Window setup
        win_name = "Adaptive 3D Output"
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
        
        # Resize logic (Max height 800)
        target_h = 800
        scale = target_h / self.height
        target_w = int(self.width * scale)
        cv2.resizeWindow(win_name, target_w, target_h)
        
        while True:
            t_start = time.perf_counter()
            
            if not paused:
                ret, frame = self.cap.read()
                if not ret:
                    print("↺ Loop video")
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # ADAPTIVE LOGIC: ONLY INFER IF INDEX MATCHES INTERVAL
                is_inference_frame = (frame_idx % self.process_interval == 0)
                
                if is_inference_frame:
                    resized = cv2.resize(frame, input_size)
                    pose = self.runner.infer(resized)
                    if pose:
                        self.last_pose = pose
                        self.calculate_metrics(pose['joints'])
                
                # Always Increment Frame Index (Video Progress)
                frame_idx += 1
            
            # RENDER (Every Frame - utilizing last known pose)
            display_frame = frame.copy() if not paused else self.last_frame_copy
            
            if hasattr(self, 'last_pose') and self.last_pose:
                self.render_overlay(display_frame, self.last_pose)
            
            # UI Info
            cv2.putText(display_frame, f"Video FPS: {self.fps:.1f}", (20, 30), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 0), 1)
            cv2.putText(display_frame, f"Inference: {self.inference_time_ms:.1f}ms (Every {self.process_interval} frames)", (20, 60), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 255), 1)
            
            cv2.imshow(win_name, display_frame)
            
            if not paused:
                self.last_frame_copy = frame.copy()

            # FPS Control: Wait to match Video FPS
            t_end = time.perf_counter()
            elapsed = t_end - t_start
            target_time = 1.0 / self.fps
            wait_ms = max(1, int((target_time - elapsed) * 1000))
            
            key = cv2.waitKey(wait_ms) & 0xFF
            if key == ord('q'): break
            if key == ord(' '): paused = not paused
            
        self.cap.release()
        cv2.destroyAllWindows()

    def calculate_metrics(self, joints):
        # Placeholder for simplified demo
        pass 

    def render_overlay(self, img, pose):
        h, w = img.shape[:2]
        joints_dict = {j['name']: j for j in pose['joints']}
        # We need an ordered list to match standard indices if pose['joints'] order is consistent 
        # (RTMW3D returns consistent order, usually COCO-WholeBody or COCO)
        
        # Fallback to index-based access assuming COCO-17 order for the first 17 joints
        # If model includes Hands/Face, they are usually appended after.
        # Let's map dynamically to be safe.
        
        kp_map = {}
        names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear', 
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip', 
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # Populate map
        for i, name in enumerate(names):
            if name in joints_dict:
                kp_map[i] = joints_dict[name]

        # Draw Lines
        for idx1, idx2 in SKELETON_EDGES:
            if idx1 in kp_map and idx2 in kp_map:
                p1, p2 = kp_map[idx1], kp_map[idx2]
                if p1['c'] > 0.3 and p2['c'] > 0.3:
                    pt1 = (int(p1['px'] * w), int(p1['py'] * h))
                    pt2 = (int(p2['px'] * w), int(p2['py'] * h))
                    
                    # Choose Color based on limb
                    color = C_BODY
                    if idx1 in [5,7,9] or idx2 in [5,7,9]: color = C_L_ARM
                    elif idx1 in [6,8,10] or idx2 in [6,8,10]: color = C_R_ARM
                    elif idx1 in [11,13,15] or idx2 in [11,13,15]: color = C_LEGS
                    elif idx1 in [12,14,16] or idx2 in [12,14,16]: color = C_LEGS
                    elif idx1 <= 4 or idx2 <= 4: color = C_FACE
                    
                    cv2.line(img, pt1, pt2, color, 3)

        # Draw Points
        for i, name in enumerate(names):
            if i in kp_map:
                p = kp_map[i]
                if p['c'] > 0.3:
                    pt = (int(p['px'] * w), int(p['py'] * h))
                    
                    # Color Logic
                    c = C_BODY
                    if i <= 4: c = C_FACE
                    elif i in [9]: c = C_L_ARM # Wrist L
                    elif i in [10]: c = C_R_ARM # Wrist R
                    
                    # Special for Hands (if we had full hand keypoints we'd use them, 
                    # but here we emphasize Wrists as "Hands")
                    radius = 4
                    if i in [9, 10]: radius = 6
                    
                    cv2.circle(img, pt, radius, c, -1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--video", type=str, default=r"docs/squat.mp4")
    parser.add_argument("-m", "--model", type=str, default="l")
    args = parser.parse_args()
    
    processor = AdaptiveVideoProcessor(args.video, args.model)
    processor.run()
