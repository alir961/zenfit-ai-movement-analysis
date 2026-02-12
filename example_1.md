([Past chat][1])([Past chat][1])([Past chat][1])([Past chat][2])

Oui. Avec ce que tu as maintenant (poids `.pth` + clone local de MMPose), on peut faire un test RTMW3D propre et déterministe **sans ambiguïté**.

Le point clé: ton checkpoint **ne suffit pas** à lui seul. Pour charger `RTMW3DHead`, il faut aussi la config et les modules Python du projet RTMPose3D (enregistrés dans le registry). C’est exactement le type de cas couvert par `custom_imports` dans MMEngine. ([mmengine.readthedocs.io][3])
Et ta confusion sur “où sont les fichiers RTMW3D” est légitime: un ticket docs officiel signale que la localisation n’était pas claire. ([GitHub][4])

---

## 1) Ce que tu dois figer (versions et base saine)

* MMPose 1.x demande au minimum Python 3.7+, CUDA 9.2+, PyTorch 1.8+ (et PyTorch 2.0 est compatible). ([MMPose][5])
* Pour MMPose 1.3.2, la matrice de compatibilité indique `mmcv>=2.0.1` et `mmengine>=0.9.0`. ([MMPose][6])
* Installation MMCV via `mim` est la voie recommandée, et il ne faut **pas** installer `mmcv` et `mmcv-lite` ensemble. ([mmcv.readthedocs.io][7])

---

## 2) Structure attendue sur ton disque

Tu as déjà indiqué :

* `D:\epitech\zenfit\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth`
* `D:\epitech\zenfit\rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.pth`
* `D:\epitech\zenfit\third_party\mmpose\projects\rtmpose3d`

Très bien.
Le nom exact `rtmw3d-l_8xb64_cocktail14-384x288.py` + checkpoint correspondant apparaît bien dans un exemple MMPose (issue technique) — ça confirme le couple config/poids attendu. ([GitHub][8])

---

## 3) Procédure exacte (Windows, pas à pas)

### Étape A — Installer l’environnement

Dans **PowerShell**:

```powershell
cd D:\epitech\zenfit
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -U pip setuptools wheel
pip install -U openmim
mim install mmengine
mim install "mmcv>=2.0.1"
mim install "mmdet>=3.1.0"
```

Puis installer MMPose en editable depuis ton clone:

```powershell
cd D:\epitech\zenfit\third_party\mmpose
pip install -r requirements.txt
pip install -v -e .
```

Ces commandes sont alignées avec les recommandations d’installation MMPose (source + editable) et la chaîne MMEngine/MMCV via MIM. ([MMPose][5])

---

### Étape B — Forcer le PythonPath du clone (important)

Toujours dans PowerShell (session courante) :

```powershell
$env:PYTHONPATH="D:\epitech\zenfit\third_party\mmpose;$env:PYTHONPATH"
```

C’est crucial pour que les imports projet (`projects.rtmpose3d...`) soient visibles lors du parsing config/custom modules. ([mmengine.readthedocs.io][3])

---

### Étape C — Smoke test “le head custom est bien chargé”

```powershell
python -c "from mmengine.config import Config; cfg=Config.fromfile(r'D:\epitech\zenfit\third_party\mmpose\projects\rtmpose3d\configs\rtmw3d-l_8xb64_cocktail14-384x288.py'); print(cfg.model['head']['type'])"
```

Attendu: `RTMW3DHead`
Si ça casse ici, **inutile** d’aller plus loin (registry/custom import pas OK).

---

## 4) Script de test complet RTMW3D (L ou X), avec sortie JSON + vidéo overlay

Crée `D:\epitech\zenfit\test_rtmw3d_video.py` :

```python
import os
import json
import cv2
import numpy as np
from mmpose.apis import init_model, inference_topdown

# ========= CONFIG UTILISATEUR =========
ROOT = r"D:\epitech\zenfit"
VIDEO_PATH = os.path.join(ROOT, "docs", "squat.mp4")
MODEL_SIZE = "l"  # "l" ou "x"

CFG_MAP = {
    "l": os.path.join(
        ROOT, "third_party", "mmpose", "projects", "rtmpose3d", "configs",
        "rtmw3d-l_8xb64_cocktail14-384x288.py"
    ),
    "x": os.path.join(
        ROOT, "third_party", "mmpose", "projects", "rtmpose3d", "configs",
        "rtmw3d-x_8xb64_cocktail14-384x288.py"
    ),
}
CKPT_MAP = {
    "l": os.path.join(ROOT, "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"),
    "x": os.path.join(ROOT, "rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.pth"),
}

OUT_DIR = os.path.join(ROOT, "outputs", f"rtmw3d_{MODEL_SIZE}_test")
os.makedirs(OUT_DIR, exist_ok=True)

CFG = CFG_MAP[MODEL_SIZE]
CKPT = CKPT_MAP[MODEL_SIZE]

# ========= UTILS =========
def to_numpy(x):
    if x is None:
        return None
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    elif hasattr(x, "cpu") and hasattr(x, "numpy"):
        x = x.cpu().numpy()
    return np.asarray(x)

def maybe_normalized_to_pixels(kps_xy, w, h):
    # Si coords dans [0,1], conversion px ; sinon on garde.
    if kps_xy is None or len(kps_xy) == 0:
        return kps_xy
    max_x = np.nanmax(kps_xy[:, 0])
    max_y = np.nanmax(kps_xy[:, 1])
    if max_x <= 2.0 and max_y <= 2.0:
        kps_xy = kps_xy.copy()
        kps_xy[:, 0] *= w
        kps_xy[:, 1] *= h
    return kps_xy

def get_first_person_instances(data_samples):
    if not data_samples:
        return None
    ds = data_samples[0]
    if not hasattr(ds, "pred_instances"):
        return None
    return ds.pred_instances

# ========= CHECKS =========
for p in [VIDEO_PATH, CFG, CKPT]:
    if not os.path.exists(p):
        raise FileNotFoundError(f"Fichier introuvable: {p}")

device = "cuda:0" if cv2.cuda.getCudaEnabledDeviceCount() > 0 else "cpu"
print(f"Device: {device}")
print(f"Config: {CFG}")
print(f"Checkpoint: {CKPT}")

# ========= LOAD MODEL =========
model = init_model(CFG, CKPT, device=device)

dataset_meta = getattr(model, "dataset_meta", {}) or {}
skeleton_links = dataset_meta.get("skeleton_links", [])
print(f"skeleton_links chargés: {len(skeleton_links)}")

# ========= VIDEO IO =========
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    raise RuntimeError(f"Impossible d'ouvrir la vidéo: {VIDEO_PATH}")

fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

out_video = os.path.join(OUT_DIR, f"overlay_rtmw3d_{MODEL_SIZE}.mp4")
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(out_video, fourcc, fps, (w, h))

pred_json = os.path.join(OUT_DIR, f"predictions_rtmw3d_{MODEL_SIZE}.json")
records = []

frame_idx = 0
detected_frames = 0
first_3d_shape = None

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Pour un test mono-personne (ex squat), on infère directement sur l'image.
    # Si vous avez plusieurs personnes, ajoutez une détection bbox dédiée.
    data_samples = inference_topdown(model, frame)
    pred = get_first_person_instances(data_samples)

    overlay = frame.copy()
    rec = {
        "frame_idx": frame_idx,
        "has_person": False,
        "keypoints_2d": None,
        "scores": None,
        "keypoints_3d": None
    }

    if pred is not None:
        kps = to_numpy(getattr(pred, "keypoints", None))
        scores = to_numpy(getattr(pred, "keypoint_scores", None))
        kps3d = to_numpy(getattr(pred, "keypoints_3d", None))

        if kps is not None and kps.ndim == 3:
            kps = kps[0]  # [K, C]
        if scores is not None and scores.ndim == 2:
            scores = scores[0]  # [K]
        if kps3d is not None and kps3d.ndim == 3:
            kps3d = kps3d[0]  # [K, 3]

        if kps is not None and kps.shape[0] > 0:
            detected_frames += 1
            rec["has_person"] = True

            if scores is None:
                scores = np.ones((kps.shape[0],), dtype=np.float32)

            kps_xy = kps[:, :2].astype(np.float32)
            kps_xy = maybe_normalized_to_pixels(kps_xy, w, h)

            # Draw points
            for i, (x, y) in enumerate(kps_xy):
                s = float(scores[i]) if i < len(scores) else 1.0
                if s >= 0.3:
                    cv2.circle(overlay, (int(x), int(y)), 3, (0, 255, 255), -1, cv2.LINE_AA)

            # Draw skeleton
            for link in skeleton_links:
                a, b = int(link[0]), int(link[1])
                if a < len(kps_xy) and b < len(kps_xy):
                    sa = float(scores[a]) if a < len(scores) else 1.0
                    sb = float(scores[b]) if b < len(scores) else 1.0
                    if sa >= 0.3 and sb >= 0.3:
                        xa, ya = kps_xy[a]
                        xb, yb = kps_xy[b]
                        cv2.line(overlay, (int(xa), int(ya)), (int(xb), int(yb)),
                                 (0, 165, 255), 2, cv2.LINE_AA)

            rec["keypoints_2d"] = kps_xy.tolist()
            rec["scores"] = scores.astype(float).tolist()

            if kps3d is not None:
                rec["keypoints_3d"] = kps3d.astype(float).tolist()
                if first_3d_shape is None:
                    first_3d_shape = list(kps3d.shape)

    # HUD
    cv2.putText(
        overlay,
        f"RTMW3D-{MODEL_SIZE.upper()} | frame={frame_idx}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    writer.write(overlay)
    records.append(rec)
    frame_idx += 1

cap.release()
writer.release()

with open(pred_json, "w", encoding="utf-8") as f:
    json.dump(
        {
            "model_size": MODEL_SIZE,
            "config": CFG,
            "checkpoint": CKPT,
            "video": VIDEO_PATH,
            "frames_total": frame_idx,
            "frames_with_person": detected_frames,
            "first_3d_shape": first_3d_shape,
            "records": records
        },
        f,
        ensure_ascii=False
    )

print("Terminé.")
print(f"Vidéo overlay : {out_video}")
print(f"JSON prédictions : {pred_json}")
print(f"Frames traitées : {frame_idx}")
print(f"Frames avec personne : {detected_frames}")
print(f"Shape 3D (première frame valide) : {first_3d_shape}")
```

Lancement:

```powershell
cd D:\epitech\zenfit
$env:PYTHONPATH="D:\epitech\zenfit\third_party\mmpose;$env:PYTHONPATH"
python .\test_rtmw3d_video.py
```

---

## 5) Ce que le dev va récupérer et comment l’afficher

Avec ce script, il récupère :

1. **Vidéo overlay** : `outputs/rtmw3d_l_test/overlay_rtmw3d_l.mp4`

   * Affichage direct des keypoints/squelette 2D superposés sur la vidéo.

2. **Fichier JSON complet** : `outputs/rtmw3d_l_test/predictions_rtmw3d_l.json`

   * Par frame: présence personne, keypoints 2D, scores, keypoints 3D (si exposés par le modèle).

Pour un pipeline basé sur `MMPoseInferencer`, les sorties officielles sont `pred_out_dir` (JSON) et `vis_out_dir` (visualisations), et `out_dir` combine les deux. ([MMPose][9])

---

## 6) Important pour éviter les faux positifs de “ça marche”

* **Ne pas utiliser seulement un alias** si tu veux **forcer RTMW3D-L local**.
  L’alias 3D documenté (`human3d`) existe, mais pour garantir TON modèle local, passe **config path + checkpoint path** explicitement. ([MMPose][9])
* En top-down, un détecteur est souvent nécessaire; pour un flux mono-personne déjà cadré, `det_model='whole_image'` est prévu pour bypasser le détecteur. ([MMPose][9])
* Si erreur `mmcv.ops` / `_ext`, corrige le couple PyTorch/CUDA puis réinstalle MMCV (ordre d’installation important). ([MMPose][5])

---

## 7) Bloc “prompt dev” prêt à copier-coller

```text
Tu dois implémenter un test RTMW3D local, déterministe, sous Windows, en utilisant EXCLUSIVEMENT:

- Config RTMW3D-L locale:
  D:\epitech\zenfit\third_party\mmpose\projects\rtmpose3d\configs\rtmw3d-l_8xb64_cocktail14-384x288.py
- Checkpoint RTMW3D-L local:
  D:\epitech\zenfit\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth
- Vidéo d’entrée:
  D:\epitech\zenfit\docs\squat.mp4

Contraintes:
1) Ne pas utiliser d’alias abstrait pour le modèle 3D; charger explicitement config+checkpoint locaux.
2) Utiliser init_model + inference_topdown pour éviter les ambiguïtés de registry.
3) Forcer PYTHONPATH vers D:\epitech\zenfit\third_party\mmpose.
4) Sorties obligatoires:
   - overlay_rtmw3d_l.mp4 (squelette dessiné)
   - predictions_rtmw3d_l.json (par frame: keypoints2d, scores, keypoints3d si dispo)
5) Ajouter un résumé console final:
   - frames_total
   - frames_with_person
   - shape du tenseur 3D détecté sur première frame valide
6) Ajouter des checks d’existence de fichiers (config, ckpt, vidéo), et fail fast avec message clair.
7) Prévoir un switch MODEL_SIZE = {"l","x"} avec map explicite des chemins de poids.

Critère d’acceptation:
- Le script s’exécute sans erreur
- Les fichiers de sortie sont générés
- Le JSON contient des keypoints non vides sur les frames où la personne est visible
- La vidéo overlay montre des joints cohérents sur la posture de squat
```

---

Si tu veux, je peux maintenant te faire une **version 2** du script avec:

* affichage 3D temps réel (matplotlib),
* filtrage temporel (stabilisation),
* compteur de reps (phase up/down) branché sur tes keypoints 3D.

[1]: https://chatgpt.com/c/698c9fac-1d3c-838e-be73-e47971205e57 "Installation RTMW3D Guide"
[2]: https://chatgpt.com/c/19d7416c-7517-441b-a23b-da35b2c9a004 "Conan CMake OpenGL Setup"
[3]: https://mmengine.readthedocs.io/en/latest/advanced_tutorials/config.html "Config — mmengine 0.11.0rc2 documentation"
[4]: https://github.com/open-mmlab/mmpose/issues/3167 "[Docs] RTMPose3D · Issue #3167 · open-mmlab/mmpose · GitHub"
[5]: https://mmpose.readthedocs.io/en/latest/installation.html "Installation — MMPose 1.3.2 documentation"
[6]: https://mmpose.readthedocs.io/en/latest/faq.html "FAQ — MMPose 1.3.2 documentation"
[7]: https://mmcv.readthedocs.io/en/latest/get_started/installation.html "Installation — mmcv 2.2.0 documentation"
[8]: https://github.com/open-mmlab/mmpose/issues/3245 "[Docs] How to convert rtmpose3d to tensorRT · Issue #3245 · open-mmlab/mmpose · GitHub"
[9]: https://mmpose.readthedocs.io/en/latest/user_guides/inference.html "Inference with existing models — MMPose 1.3.2 documentation"
