
from mmpose.apis import MMPoseInferencer
import inspect
import sys
import numpy as np

try:
    inf = MMPoseInferencer(pose2d='rtmw-l_8xb1024-270e_cocktail14-256x192')
    print("MMPoseInferencer.__call__ parameters:")
    print(list(inspect.signature(inf.__call__).parameters.keys()))
    
    img = np.zeros((256, 192, 3), dtype=np.uint8)
    
    # Try with return_datasamples if it sounds right
    res_gen = inf(img, return_vis=False, return_datasamples=True)
    res = next(res_gen)
    
    print(f"Result type: {type(res)}")
    if not isinstance(res, dict):
        print("Got a non-dict result! Likely a DataSample.")
        if hasattr(res, 'pred_instances'):
            print("Pred instances keys:", res.pred_instances.keys())
            if 'keypoints_3d' in res.pred_instances:
                print("SUCCESS: Found keypoints_3d!")
            else:
                print("Still no keypoints_3d.")
    else:
        print("Result is still a dict.")
        print("Keys:", res.keys())
        if 'predictions' in res:
            p0 = res['predictions'][0]
            if isinstance(p0, list): p0 = p0[0]
            print("Prediction keys:", p0.keys())

except Exception as e:
    print(f"Error: {e}")
