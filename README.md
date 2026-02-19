# ZenFit / Speedy Learning

Ce repo contient plusieurs espaces, mais le workflow principal actuel est `speedy_learning`:
- pipeline detection/pose (YOLOX + RTMW3D)
- parsing dataset `pose_raw17_transformed`
- entrainement CUDA + sauvegarde des poids

## Prerequis
- Windows + PowerShell
- Python 3.10+
- NVIDIA GPU + drivers CUDA (pour training full GPU)
- Optionnel: `just` pour automatiser les commandes
- Git Clone: `third_party` https://github.com/open-mmlab/mmpose

## Installation (recommandee via `just`)
Depuis la racine du repo:

```powershell
just speedy-install
```

Ou en detail:

```powershell
just speedy-venv-create
just speedy-venv-install
just speedy-third-party-ensure
just speedy-onnx-prepare
just speedy-ort-fix
```

Verification rapide:

```powershell
just speedy-venv-doctor
```

## Lancer le serveur Speedy Learning

```powershell
just speedy-dev
```

Le viewer est servi sur `http://127.0.0.1:8000` (ou port libre suivant).

## Construire les donnees d'entrainement
Le parser produit les donnees depuis `datasets/*.mp4` en utilisant `pose_raw17_transformed`.

```powershell
python speedy_learning/parser_dataset_pytorch.py --datasets-dir datasets --output-dir datasets --stride 1 --sequence-len 120 --sequence-step 30 --val-ratio 0.2
```

Sorties generees:
- `datasets/videos/*.jsonl`
- `datasets/samples/train.npz`
- `datasets/samples/val.npz`
- `datasets/samples/index_train.json`
- `datasets/samples/index_val.json`
- `datasets/manifest.json`
- `datasets/stats.json`

## Entrainer le modele (CUDA)
Script principal:

```powershell
python speedy_learning/train_cuda_live.py
```

Fonctionnalites training:
- Full CUDA + AMP
- Dropout configurable (`--dropout`)
- Label smoothing (`--label-smoothing`)
- Scheduler LR warmup + cosine (`--scheduler cosine`)
- Eval live par batch + plot
- Sauvegarde auto du meilleur checkpoint (best val accuracy, tie-break val loss)

Exemple court:

```powershell
python speedy_learning/train_cuda_live.py --epochs 10 --batch-size 4 --eval-every-batches 2
```

## Resultats et poids
Dossier de sortie training:
- `datasets/training_outputs/`

Fichiers importants:
- `datasets/training_outputs/best_model.pt`
- `datasets/training_outputs/last_model.pt`
- `datasets/training_outputs/checkpoint_epoch_*.pt`
- `datasets/training_outputs/live_metrics.png`
- `datasets/training_outputs/live_metrics_history.json`

## Charger les poids
Exemple minimal:

```python
from pathlib import Path
import torch
from speedy_learning.models.movement_classification import GraphBiasedSTTransformer, ModelCfg
from speedy_learning.backend.skeleton_map import RAW17_EDGES

ckpt_path = Path("datasets/training_outputs/best_model.pt")
ckpt = torch.load(ckpt_path, map_location="cuda" if torch.cuda.is_available() else "cpu")

cfg = ModelCfg(**ckpt["cfg"])
model = GraphBiasedSTTransformer(
    num_joints=17,
    edges=[(int(a), int(b)) for a, b in RAW17_EDGES],
    cfg=cfg,
)
model.load_state_dict(ckpt["model_state_dict"])
model.eval()

print("Best val acc:", ckpt.get("best_val_acc"))
print("Best val loss:", ckpt.get("best_val_loss"))
print("Label map:", ckpt.get("label_map"))
```

## Commandes utiles
- Test rapide pipeline inference:

```powershell
just speedy-test
```

- Regenerer lock requirements speedy:

```powershell
just speedy-venv-freeze
```
