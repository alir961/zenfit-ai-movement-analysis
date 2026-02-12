
from mmpose.apis import MMPoseInferencer
import numpy as np
import sys
import pprint

try:
    model_alias = 'rtmw-l_8xb320-270e_cocktail14-384x288'
    print(f"Testing model as pose3d: {model_alias}")
    
    # Try initializing as pose3d
    try:
        inf = MMPoseInferencer(pose3d=model_alias)
        print("Successfully initialized as pose3d.")
    except Exception as e:
        print(f"Failed to initialize as pose3d: {e}")
        print("Falling back to pose2d initialization to inspect keys further.")
        inf = MMPoseInferencer(pose2d=model_alias)

    # Create a blank image
    img = np.zeros((384, 288, 3), dtype=np.uint8)
    
    # Run inference
    result_generator = inf(img, return_vis=False)
    result = next(result_generator)
    
    if isinstance(result, dict):
        predictions = result.get('predictions', [])
        if predictions and isinstance(predictions, list):
            # Inspect first person
            p0 = predictions[0]
            if isinstance(p0, list): p0 = p0[0]
            
            print(f"Keys in prediction: {p0.keys()}")
            
            k2 = p0.get('keypoints', [])
            k3 = p0.get('keypoints_3d', [])
            
            print(f"Keypoints 2D count: {len(k2)}")
            print(f"Keypoints 3D count: {len(k3)}")
            
            if len(k3) > 0:
                print("SUCCESS: 3D keypoints detected.")
            else:
                print("Checking for 'keypoints' content (maybe it contains 3D?).")
                if len(k2) > 0:
                    sample = k2[0]
                    print(f"Sample keypoint shape/content: {sample}")
                    if len(sample) >= 3:
                        print("It seems 'keypoints' itself contains 3 axes!")
    else:
        print("Unexpected result structure.")
        pprint.pprint(result)

except Exception as e:
    print(f"Error during verification: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
