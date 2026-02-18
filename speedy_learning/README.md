# Speedy Learning Lab

Standalone lab pour `viewer.html` + pipeline YOLOX/RTMW3D, avec runtime local piloté par `just`.

## Prérequis
- Windows + PowerShell
- Python 3.10+
- `just` installé
- GPU CUDA optionnel (fallback CPU automatique)

## Quickstart
```powershell
just speedy-venv-create
just speedy-venv-install
just speedy-ort-fix
just speedy-dev
```

Le serveur démarre sur `http://127.0.0.1:8000` (ou port suivant libre).

## Validation rapide
1. Ouvrir `http://127.0.0.1:8000/health`
2. Vérifier `providers` (CUDA/CPU)
3. Vérifier les logs dans `speedy_learning/logs/server.log`

## Variables d'environnement runtime
- `ZENFIT_LOG_LEVEL` (default: `INFO`)
- `ZENFIT_DEBUG_STAGES` (default: `0`)
- `ZENFIT_VERBOSE_CAMERA` (default: `0`)
- `ZENFIT_ORT_CPU_ONLY` (auto géré par le bootstrap si CUDA invalide)

Exemple debug:
```powershell
$env:ZENFIT_LOG_LEVEL="DEBUG"
$env:ZENFIT_DEBUG_STAGES="1"
$env:ZENFIT_VERBOSE_CAMERA="1"
just speedy-dev
```

## Maintenance du lock requirements
Le lock officiel est:
- `speedy_learning/backend/requirements.txt`

Après une mise à jour dépendances:
```powershell
just speedy-venv-freeze
```

## Dépannage CUDA (cudnn64_9.dll)
Si `cudnn64_9.dll` ne peut pas être chargé:
1. Lancer `just speedy-ort-fix`
2. Vérifier Python/prefix affichés (doivent pointer vers `speedy_learning/.venv`)
3. Le script active automatiquement `ZENFIT_ORT_CPU_ONLY=1` pour éviter le flood d'erreurs et garder le runtime fonctionnel.

## Outils diagnostics (conservés)
Les scripts debug backend (`_debug_*`, dataset checks) sont conservés mais ne font pas partie du chemin runtime principal.

## Dataset training (pose_raw17_transformed)
Pipeline recommande:
1. Parser les videos en JSONL + samples
2. Entrainer en CUDA avec `train_cuda_live.py`
3. Charger `best_model.pt` pour inference/eval

### 1) Construire les donnees
Commande (depuis la racine repo):
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

### 2) Entrainer le modele (full CUDA)
Commande standard:
```powershell
python speedy_learning/train_cuda_live.py
```

La version actuelle inclut:
- AMP CUDA
- Dropout configurable (`--dropout`)
- Label smoothing (`--label-smoothing`)
- LR scheduler warmup + cosine (`--scheduler cosine`)
- Eval live + plot

Artefacts training:
- `datasets/training_outputs/best_model.pt`
- `datasets/training_outputs/last_model.pt`
- `datasets/training_outputs/checkpoint_epoch_*.pt`
- `datasets/training_outputs/live_metrics.png`
- `datasets/training_outputs/live_metrics_history.json`

Exemple run court:
```powershell
python speedy_learning/train_cuda_live.py --epochs 10 --batch-size 4 --eval-every-batches 2
```

### 3) Charger les poids
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
```

`ckpt["label_map"]` donne le mapping classes (`jumping_jacks`, `push_up`, `squat`).
