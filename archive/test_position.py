import cv2
import numpy as np
import time
import sys
import os
import json
from typing import Optional, List, Dict
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Add backend to path to import local modules
sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))

from app.processing.rtmw3d_runtime import RTMW3DRunner
from app.processing.classify import ExerciseClassifier

# Colors for professional visualization (BGR)
COLORS = {
    "body": (0, 0, 255),       # Red
    "left_hand": (0, 255, 0),  # Green
    "right_hand": (255, 0, 0), # Blue
    "face": (0, 255, 255),     # Yellow
    "foot": (255, 0, 255),     # Purple
}

class ZenFitSandbox:
    def __init__(self, video_path: str, model_size: str = "l"):
        self.video_path = video_path
        print(f"🚀 Initializing Premium RTMW3D Sandbox ({model_size})...")
        
        # Initialize with specific model size
        self.runner = RTMW3DRunner(model_size=model_size, device="auto")
        self.classifier = ExerciseClassifier()
        
        if not self.runner.ready:
            print("⚠️ Warning: RTMW3D Runner not ready. Checks might fails.")
            
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print(f"❌ Error: Could not open video file {video_path}")
            sys.exit(1)
            
        self.paused = True
        self.frame = None
        self.frame_idx = 0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.pose = None
        self.state = None
        self.skeleton_links = []
        
        # UI State
        self.show_dump = False
        self.show_3d = True
        
        # 3D Plot setup
        if self.show_3d:
            plt.ion()
            self.fig = plt.figure(figsize=(10, 8))
            self.ax = self.fig.add_subplot(111, projection='3d')
            self.fig.suptitle("ZenFit 3D Whole-Body Rig", fontsize=16)
            
        cv2.namedWindow("ZenFit Premium Sandbox", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("ZenFit Premium Sandbox", 1280, 720)

    def get_joint_group(self, name: str) -> str:
        """Categorize joints based on names for coloring."""
        ln = name.lower()
        if any(x in ln for x in ["face", "nose", "eye", "ear", "mouth", "lip"]): return "face"
        if "left_hand" in ln or "left_wrist" in ln or "left_finger" in ln: return "left_hand"
        if "right_hand" in ln or "right_wrist" in ln or "right_finger" in ln: return "right_hand"
        if "foot" in ln or "ankle" in ln: return "foot"
        return "body"

    def update_skeleton_links(self):
        """Retrieve actual skeleton connections from model metadata."""
        if not self.skeleton_links and self.runner.ready:
            # New structure uses _pose_model
            model = getattr(self.runner, "_pose_model", None)
            if model:
                meta = getattr(model, "dataset_meta", {})
                self.skeleton_links = meta.get("skeleton_links", [])
                if self.skeleton_links:
                    print(f"🔗 Loaded {len(self.skeleton_links)} skeleton links from model metadata.")

    def run(self):
        print("\n✨ Sandbox Ready!")
        print("-" * 30)
        print("🎮 Controls:")
        print("  [SPACE]     : Play / Pause")
        print("  [RIGHT/N]   : Next Frame")
        print("  [LEFT]      : Previous Frame")
        print("  [D]         : Toggle Console Output (Real-time Metric Display)")
        print("  [P]         : Complete JSON Dump of Current Frame")
        print("  [Q]         : Quit Sandbox")
        print("-" * 30)
        
        while True:
            if not self.paused or self.frame is None:
                ret, frame = self.cap.read()
                if not ret:
                    print("🏁 Video finished. Press 'Q' to quit or use LEFT to go back.")
                    self.paused = True
                else:
                    self.frame = frame
                    self.frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                    self.process()

            self.render()
            
            # Key Handling
            wait_time = 1 if not self.paused else 0
            key = cv2.waitKey(wait_time) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord(' '):
                self.paused = not self.paused
                status = "PAUSE" if self.paused else "PLAY"
                print(f"▶️ Status: {status}")
            elif key == ord('d'):
                self.show_dump = not self.show_dump
                print(f"📊 Real-time Metrics: {'ENABLED' if self.show_dump else 'DISABLED'}")
            elif key == ord('p'):
                self.print_dump()
            elif key == 83 or key == ord('n'): # Right arrow
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_idx)
                ret, frame = self.cap.read()
                if ret:
                    self.frame = frame
                    self.frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                    self.process()
            elif key == 81: # Left arrow
                new_idx = max(0, self.frame_idx - 2)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_idx)
                ret, frame = self.cap.read()
                if ret:
                    self.frame = frame
                    self.frame_idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                    self.process()

        self.cap.release()
        cv2.destroyAllWindows()
        plt.close('all')

    def process(self):
        if self.frame is None: return
        self.update_skeleton_links()
            
        h, w = self.frame.shape[:2]
        self.pose = self.runner.infer(self.frame, input_size=(w, h))
        
        if self.pose:
            self.state = self.classifier.update(self.pose)
            if self.show_dump:
                print(f"📍 Frame {self.frame_idx}/{self.total_frames} | Ex: {self.state['name']} | Reps: {self.state['repCount']}")

            if self.show_3d:
                self.update_3d_plot()

    def update_3d_plot(self):
        if not self.pose: return
        self.ax.clear()
        
        id_to_joint = {i: j for i, j in enumerate(self.pose['joints'])}
        
        # RTMW3D coords are usually camera-space meters
        # We want to center the plot on the user for better visibility
        # pelvic_root is usually index 11/12 (hips)
        try:
            root_x = (id_to_joint[11]['x'] + id_to_joint[12]['x']) / 2
            root_y = (id_to_joint[11]['y'] + id_to_joint[12]['y']) / 2
            root_z = (id_to_joint[11]['z'] + id_to_joint[12]['z']) / 2
        except:
            root_x, root_y, root_z = 0, 0, 0

        # Plot points
        X, Y, Z = [], [], []
        colors = []
        for i, j in id_to_joint.items():
            if j['c'] < 0.2: continue
            color = np.array(COLORS[self.get_joint_group(j['name'])]) / 255.0
            # Flip Y and Z for better natural visualization (MMPose Y is down)
            X.append(j['x'] - root_x)
            Y.append(-(j['y'] - root_y))
            Z.append(j['z'] - root_z)
            colors.append(color)
        
        self.ax.scatter(X, Z, Y, c=colors, s=15)
        
        # Plot links
        if self.skeleton_links:
            for start_idx, end_idx in self.skeleton_links:
                if start_idx in id_to_joint and end_idx in id_to_joint:
                    j1, j2 = id_to_joint[start_idx], id_to_joint[end_idx]
                    if j1['c'] > 0.2 and j2['c'] > 0.2:
                        color = np.array(COLORS[self.get_joint_group(j1['name'])]) / 255.0
                        self.ax.plot(
                            [j1['x'] - root_x, j2['x'] - root_x],
                            [j1['z'] - root_z, j2['z'] - root_z],
                            [-(j1['y'] - root_y), -(j2['y'] - root_y)],
                            c=color, alpha=0.5
                        )
        
        # Appearance
        self.ax.set_xlabel('Lateral')
        self.ax.set_ylabel('Depth')
        self.ax.set_zlabel('Height')
        
        # Fixed box around root (1.5 meters range)
        r = 1.0
        self.ax.set_xlim(-r, r)
        self.ax.set_ylim(-r, r) 
        self.ax.set_zlim(-r, r)
        
        self.ax.view_init(elev=15, azim=70) # Classic 3D pose view
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def render(self):
        if self.frame is None: return
        display_img = self.frame.copy()
        h, w = display_img.shape[:2]
        
        # 2D Draw
        if self.pose:
            id_to_coords = {}
            id_to_joint = {i: j for i, j in enumerate(self.pose['joints'])}
            
            for i, j in id_to_joint.items():
                if 'px' in j and 'py' in j:
                    id_to_coords[i] = (int(j['px'] * w), int(j['py'] * h))
                else:
                    id_to_coords[i] = (int(j['x'] * w), int(j['y'] * h))

            # Links
            for start_idx, end_idx in self.skeleton_links:
                if start_idx in id_to_coords and end_idx in id_to_coords:
                    j1 = id_to_joint[start_idx]
                    j2 = id_to_joint[end_idx]
                    if j1['c'] > 0.3 and j2['c'] > 0.3:
                        color = COLORS[self.get_joint_group(j1['name'])]
                        cv2.line(display_img, id_to_coords[start_idx], id_to_coords[end_idx], color, 2, cv2.LINE_AA)
            
            # Points
            for i, coords in id_to_coords.items():
                j = id_to_joint[i]
                if j['c'] > 0.3:
                    color = COLORS[self.get_joint_group(j['name'])]
                    cv2.circle(display_img, coords, 3, color, -1, cv2.LINE_AA)

        # UI Overlay (Premium Glassmorphism-style)
        overlay = display_img.copy()
        cv2.rectangle(overlay, (w - 300, 10), (w - 10, 180), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, display_img, 0.3, 0, display_img)
        
        p_x = w - 280
        cv2.putText(display_img, "ZENFIT LIVE INSIGHTS", (p_x, 40), cv2.FONT_HERSHEY_DUPLEX, 0.6, (200, 200, 200), 1)
        
        if self.state:
            status_color = (0, 255, 0) if self.state['name'] != "none" else (100, 100, 100)
            cv2.putText(display_img, f"MODEL: {self.state['name'].upper()}", (p_x, 80), cv2.FONT_HERSHEY_DUPLEX, 0.7, status_color, 2)
            cv2.putText(display_img, f"PHASE: {self.state['phase'].upper()}", (p_x, 110), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(display_img, f"REPS:  {self.state['repCount']}", (p_x, 140), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 255), 2)
        
        # Progress Bar
        cv2.rectangle(display_img, (0, h-10), (int(w * (self.frame_idx/self.total_frames)), h), (0, 165, 255), -1)

        cv2.imshow("ZenFit Premium Sandbox", display_img)

    def print_dump(self):
        print(f"\n📑 --- DUMP FRAME {self.frame_idx} ---")
        if self.pose:
            print(f"Detected {len(self.pose['joints'])} keypoints.")
            # Print only first 3 for brevity in console unless asked
            print("First 3 keypoints preview:")
            for j in self.pose['joints'][:3]:
                print(f"  - {j['name']}: pos=({j['x']:.2f}, {j['y']:.2f}, {j['z']:.2f}) conf={j['c']:.2f}")
        if self.state:
            print(f"State Summary: {self.state}")
        print("--------------------------\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("-v", "--video", type=str, default=r"D:\epitech\zenfit\docs\squat.mp4")
    parser.add_argument("-m", "--model", type=str, default="l", choices=["l", "x"])
    args = parser.parse_args()

    VIDEO_PATH = args.video
    if not os.path.exists(VIDEO_PATH):
        print(f"❌ Video not found at: {VIDEO_PATH}")
        sys.exit(1)
        
    sandbox = ZenFitSandbox(VIDEO_PATH, model_size=args.model)
    if args.smoke_test:
        print("🔍 Smoke Test Mode: Processing first frame...")
        ret, frame = sandbox.cap.read()
        if ret:
            sandbox.frame = frame
            sandbox.process()
            if sandbox.pose and len(sandbox.pose['joints']) > 100:
                print(f"✅ Success! Detected {len(sandbox.pose['joints'])} joints.")
            else:
                print("❌ Failure: Pose detection returned no/insufficient joints.")
        else:
            print("❌ Failure: Could not read first frame.")
        sys.exit(0)
    
    sandbox.run()
