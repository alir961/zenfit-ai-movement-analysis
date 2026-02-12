
from mmpose.apis import MMPoseInferencer
import sys

try:
    # Use list_models method which is usually internal or available on registry
    # Actually, MMPoseInferencer.list_models is what I used before.
    
    # Let's check internal aliases mapping if possible
    from mmpose.apis.inferencers.mmpose_inferencer import MMPoseInferencer as MPI
    # Inspect aliases
    # MPI.model_aliases is usually a dict
    if hasattr(MPI, 'model_aliases'):
        aliases = MPI.model_aliases
        print("Model Aliases keys:")
        # Filter for 3D and RTMW
        filtered = {k: v for k, v in aliases.items() if '3d' in k.lower() or 'rtm' in k.lower()}
        import pprint
        pprint.pprint(filtered)
    else:
        print("MMPoseInferencer does not have model_aliases attribute.")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
