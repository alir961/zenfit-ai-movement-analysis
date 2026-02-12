
import sys
import os
import torch
import torch.nn as nn
import argparse
import warnings

# Backend setup
sys.path.append(os.path.join(os.getcwd(), "workspace", "backend"))
from app.processing.rtmw3d_runtime import RTMW3DRunner

class RTMW3DWrapper(nn.Module):
    """
    Wrapper to bypass MMEngine data structures and export pure tensor I/O.
    """
    def __init__(self, pose_model):
        super().__init__()
        self.model = pose_model
        
    def forward(self, x):
        # 1. Manually run data preprocessor
        # x is [B, C, H, W] (e.g. 1, 3, 384, 288)
        # MMpose expects 'inputs' and 'data_samples'.
        # But for export, we often can just call extract_feat -> head.predict
        
        # In RTMPose/RTMW3D:
        # x = self.model.data_preprocessor(inputs=x, data_samples=None) # Takes dict?
        # Let's assume input x is already normalized or we include normalization
        
        # Typically:
        feats = self.model.extract_feat(x)
        
        # Head forward
        # The head usually returns predictions. 
        # rtmcc_head.forward(feats) returns tuple of SimCC maps (x, y)
        return self.model.head.forward(feats)

def export_onnx(model_size="l", output_file="rtmw3d.onnx"):
    print(f"🚀 Exporting RTMW3D-{model_size.upper()} to ONNX...")
    
    # 1. Load Model
    # Important: Load on CPU to avoid CUDA complex ops during trace if possible, 
    # but some ops might require CUDA. Let's try CPU first.
    runner = RTMW3DRunner(model_size=model_size, device="cpu") 
    
    if not hasattr(runner, "_pose_model"):
        print("❌ Error: Runner has no _pose_model")
        return

    model = runner._pose_model
    model.eval()
    
    # 2. Wrap Model
    wrapper = RTMW3DWrapper(model)
    
    # Input Shape (Batch, Channel, Height, Width)
    # RTMW3D-L uses 288x384 (W, H) or 384x288? 
    # Config often says: input_size=(288, 384) -> [w, h]
    # So tensor is [1, 3, 384, 288]
    dummy_input = torch.randn(1, 3, 384, 288)
    
    print("Example input shape:", dummy_input.shape)
    
    # 3. Export
    try:
        torch.onnx.export(
            wrapper,
            dummy_input,
            output_file,
            input_names=['input'],
            output_names=['simcc_x', 'simcc_y'],
            opset_version=11,
            do_constant_folding=True,
            dynamic_axes={'input': {0: 'batch_size'}}
        )
        print(f"✅ Exported to {output_file}")
    except Exception as e:
        print(f"❌ Export Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", default="l")
    parser.add_argument("-o", "--output", default="rtmw3d_l.onnx")
    args = parser.parse_args()
    
    export_onnx(args.model, output_file=args.output)
