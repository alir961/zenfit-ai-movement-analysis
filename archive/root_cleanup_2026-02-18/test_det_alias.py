
try:
    from mmdet.apis import DetInferencer
    # Try a simple one
    inferencer = DetInferencer('rtmdet_m_8xb32-300e_coco', device='cpu')
    print(f"✅ Success! Loaded {inferencer.model.__class__.__name__}")
except Exception as e:
    print(f"❌ Error: {e}")
