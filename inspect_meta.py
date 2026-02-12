
from mmpose.apis import MMPoseInferencer
import sys
import pprint

try:
    model_alias = 'rtmw-l_8xb320-270e_cocktail14-384x288'
    print(f"Inspecting metadata for: {model_alias}")
    inf = MMPoseInferencer(pose2d=model_alias)
    
    vis = getattr(inf, "visualizer", None)
    if vis:
        meta = getattr(vis, "dataset_meta", {})
        print("Dataset Meta keys:")
        print(meta.keys())
        # Print some interesting values
        for k in ['num_keypoints', 'keypoint_id2name', 'skeleton_links', 'sigmas']:
            if k in meta:
                print(f"{k}: {type(meta[k])}")
                if k == 'num_keypoints': print(f"  Value: {meta[k]}")
    else:
        print("No visualizer found.")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
