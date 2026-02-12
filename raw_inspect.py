
from mmpose.apis import MMPoseInferencer
import sys
import numpy as np

try:
    # Try the shortest rtmw-l alias
    model_alias = 'rtmw-l'
    print(f"Testing model: {model_alias}")
    inf = MMPoseInferencer(pose2d=model_alias)
    
    img = np.zeros((256, 192, 3), dtype=np.uint8)
    res_gen = inf(img, return_vis=False)
    res = next(res_gen)
    
    pred = res['predictions'][0]
    if isinstance(pred, list): pred = pred[0]
    
    kpts = pred.get('keypoints', [])
    if kpts:
        k0 = kpts[0]
        print(f"Raw keypoint 0: {k0}")
        print(f"Raw keypoint 0 type: {type(k0)}")
    
    k3 = pred.get('keypoints_3d', [])
    if k3:
        print(f"Found keypoints_3d: {k3[0]}")
    else:
        print("No keypoints_3d found.")
    
    # Check if there is a 'joints_3d' or similar
    all_keys = pred.keys()
    print(f"All keys in prediction: {list(all_keys)}")

except Exception as e:
    print(f"Error: {e}")
