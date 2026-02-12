Tu as raison: **tes mesures locales sont cohérentes** avec ton stack actuel, et elles ne ressemblent pas aux chiffres “marketing” NPU/TensorRT qu’on voit parfois.

En lisant ton tableau, voilà ce qui ressort clairement.

## 1) Ce que disent *tes* benchmarks (réel terrain)

### Détection seule (`det_only_ms`, profil `cuda_cpu`)

* `yolox_tiny_humanart fp32`: **7.484 ms**
* `yolox_s_humanart fp32`: **16.154 ms**
* `rtmdet_nano fp32`: **15.179 ms**
* `rtmdet_tiny fp32`: **15.154 ms**
* `person_foot_qualcomm int8`: **14.228 ms**

Donc, avec **ton pipeline ONNX Runtime actuel**, **aucun modèle ne passe < 5 ms** en détection seule.

### Pipeline complet (`total_ms`, détecteur + pose)

* meilleur cas chez toi ~**24.787 ms** (`yolox_tiny fp32 + pose fp16`)
* donc très loin de < 5 ms end-to-end (normal, la pose coûte beaucoup).

---

## 2) Pourquoi tu n’as pas les mêmes chiffres que les benchmarks publics

C’est normal pour 4 raisons techniques majeures :

1. **Protocoles différents**
   Beaucoup de chiffres publics sont mesurés sur NPU mobile ou TensorRT, parfois “model-only”, avec conditions spécifiques. Toi tu mesures un vrai pipeline ORT + postprocess + pose.

2. **Fallback CPU silencieux possible avec CUDA EP**
   ONNX Runtime peut placer certains ops sur CPU si CUDA EP ne les supporte pas/juge non optimal, ce qui plombe la latence. ORT le documente explicitement dans sa section troubleshooting. ([ONNX Runtime][1])

3. **INT8 plus lent que FP32/FP16 sur CUDA EP**
   Ce que tu observes (INT8 très lent) est un comportement connu dans plusieurs cas ORT/CUDA, notamment quand l’exécution n’exploite pas le chemin le plus optimisé ou subit des coûts de conversion/fallback. ([GitHub][2])

4. **Ton erreur FP16 ONNX est réelle et connue**
   `Type (tensor(float16)) ... does not match expected type (tensor(float))` correspond à des problèmes de cohérence de types dans certains graphes convertis FP16 (Cast/output signatures). C’est un pattern déjà signalé côté ORT. ([GitHub][3])

---

## 3) Conclusion brute selon ton objectif

Tu voulais :
[
\text{accuracy} > \text{YOLOX_tiny_humanart} \quad \land \quad \text{det_latency} < 5\text{ ms}
]

Avec **ta stack actuelle (ONNX Runtime + CUDA/CPU)**:

* en l’état, **pas atteint** (même le meilleur `det_only_ms` est ~7.5 ms).

Et c’est important: ton benchmark est plus crédible pour ton produit que des chiffres externes.

---

## 4) Plan concret pour passer sous 5 ms (réaliste)

### A. Corriger d’abord la voie FP16 (priorité absolue)

Ton FP16 échoue au load: tant que ce point n’est pas réglé, tu perds le levier principal de perf GPU.

* Ré-export propre ONNX FP16 avec I/O et Cast cohérents.
* Vérifier la signature exacte des outputs (dtype attendu vs réel).
* Éviter les bricolages partiels de conversion qui laissent des Cast incohérents.
  (les issues ORT que j’ai citées vont dans ce sens). ([GitHub][3])

### B. Vérifier le placement des nœuds (anti-fallback)

* Active logs verboses ORT + profiling JSON.
* Objectif: **0 op critique sur CPU** côté détecteur.
* ORT recommande explicitement cette vérification quand GPU est “anormalement lent”. ([ONNX Runtime][1])

### C. Tester TensorRT EP (pas seulement CUDA EP)

Sur NVIDIA, TensorRT EP est souvent nettement meilleur pour détecteurs (fusion/precision kernels). ([NVIDIA Developer][4])

### D. Réduire la résolution d’entrée détecteur

Si tu passes de 640 vers 512/448 (avec retuning seuil/NMS), le coût peut fortement baisser.

### E. Mesurer proprement la latence

Toujours comparer :

* warmup fixe,
* même batch=1,
* mêmes dimensions,
* mêmes pre/post,
* P50/P90/P99 séparés détecteur vs pose.

---

## 5) Recommandation “modèle” dans ton contexte immédiat

Vu **tes chiffres**, le meilleur point de départ reste :

* **`yolox_tiny_humanart fp32`** (c’est le plus rapide chez toi aujourd’hui en détection seule),
* puis **accélération runtime** (FP16 corrigé + TensorRT EP + zéro fallback) avant de changer d’architecture.

Pourquoi: changer de modèle maintenant sans corriger runtime risque juste de déplacer le problème.

---

Si tu veux, je te fais au prochain message un **checklist exécutable** (commandes ORT/TensorRT + flags session options + protocole de bench) pour diagnostiquer en 30 minutes exactement **où partent tes millisecondes** et viser concrètement `< 5 ms` détection.

[1]: https://onnxruntime.ai/docs/performance/tune-performance/troubleshooting.html?utm_source=chatgpt.com "Troubleshooting | onnxruntime"
[2]: https://github.com/microsoft/onnxruntime/issues/24807?utm_source=chatgpt.com "[Performance] Slow inference on CUDA V100 int8 #24807"
[3]: https://github.com/microsoft/onnxruntime/issues/25522?utm_source=chatgpt.com "Type mismatch error when loading a Float16 model · Issue #25522 · microsoft/onnxruntime · GitHub"
[4]: https://developer.nvidia.com/blog/end-to-end-ai-for-nvidia-based-pcs-cuda-and-tensorrt-execution-providers-in-onnx-runtime/?utm_source=chatgpt.com "CUDA and TensorRT Execution Providers in ONNX Runtime"
