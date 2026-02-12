
import onnx
from onnxconverter_common import float16
import argparse
import os

def convert_to_fp16(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        return

    print(f"🚀 Converting {input_path} to FP16...")
    try:
        model = onnx.load(input_path)
        model_fp16 = float16.convert_float_to_float16(model)
        onnx.save(model_fp16, output_path)
        print(f"✅ Successfully saved FP16 model to {output_path}")
    except Exception as e:
        print(f"❌ Conversion failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="rtmw3d_l.onnx")
    parser.add_argument("-o", "--output", default="rtmw3d_l_fp16.onnx")
    args = parser.parse_args()
    
    convert_to_fp16(args.input, args.output)
