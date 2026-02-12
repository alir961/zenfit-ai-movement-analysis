
from mmpose.apis import MMPoseInferencer
import sys
import numpy as np
import pprint

try:
    model_alias = 'rtmw-l_8xb320-270e_cocktail14-384x288'
    inf = MMPoseInferencer(pose2d=model_alias)
    
    img = np.zeros((384, 288, 3), dtype=np.uint8)
    res_gen = inf(img, return_vis=False)
    res = next(res_gen)
    
    p0 = res['predictions'][0]
    # Sometimes it's a list containing a dict, sometimes just a dict
    if isinstance(p0, list): p0 = p0[0]
    
    if 'pred_instances' in p0:
        instances = p0['pred_instances']
        print("Instances keys:", instances.keys())
        
        for k in ['keypoints', 'keypoints_3d', 'keypoint_scores', 'scores']:
            if k in instances:
                val = np.asarray(instances[k])
                print(f"{k} shape: {val.shape}")
                if k == 'keypoints' and val.shape[1] >= 3:
                    print(f"Sample {k}: {val[0]}")
    else:
        print("No pred_instances found. Checking top level of prediction.")
        print("Keys:", p0.keys())

except Exception as e:
    print(f"Error: {e}")
