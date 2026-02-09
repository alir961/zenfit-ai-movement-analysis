[BLOC 3/4] — WS-RETARGET (Joints → Bones + Quaternions + Calibration morpho) — BRANCHE: feat/retarget-engine — DEADLINE: 28/01/2026

OBJECTIF
Transformer PoseFrame (positions 3D) en rotations d’os (quaternions) + paramètres morpho (taille/proportions) pour piloter l’avatar en temps réel.

BRANCHE & RÈGLES
- Travailler UNIQUEMENT sur: feat/retarget-engine
- PR vers: develop
- Ne pas modifier les assets avatars (BLOC 2) ni l’inférence pose (BLOC 1).
- Vous dépendez seulement de:
  - PoseFrame + joints.list (BLOC 1)
  - bones.md + blendshapes.md + fichiers .glb (BLOC 2)

LIVRABLES (à committer)
1) RigMap (contrat de mapping joints→bones):
   - /packages/contracts/src/RigMap.ts (ou /contracts/rigmap.json)
   - Ex: "LeftUpperArm" <- ("left_shoulder","left_elbow")
2) Retargeter runtime:
   - /packages/retarget/ (TypeScript)
   - API:
     - retarget(poseFrame, rig, rigMap) => { boneRotations, morphParams, quality }
3) Maths/quaternions + conventions d’axes:
   - /packages/retarget/docs/axes_conventions.md
   - gestion left/right, parent-child, twist (même si twist minimal MVP)
4) Calibration morpho (MVP pragmatique):
   - estimations segments (bras, avant-bras, cuisse, tibia)
   - ratios normalisés (par “taille squelette”)
   - morphParams = { heightScale, shoulderWidthRatio, hipWidthRatio, bulkHint? }
5) Tests:
   - /packages/retarget/tests/retarget.test.ts (pose synthétique → rotations finies)
   - un script “playback” sur une petite séquence JSON (même 3 secondes)

DEFINITION OF DONE (DoD) au 28/01/26
- Sur un PoseFrame valide: aucune rotation NaN, pas d’explosion (clamp/guard)
- Avatar suit correctement 3 actions simples (lever bras, squat approximatif, rotation tronc)
- RigMap + conventions documentées (sinon tout casse en intégration)
- Sortie “quality” (0..1) basée sur confidence moyenne + stabilité (utile pour UI)

GARANTIES POUR LES AUTRES BLOCS
- Ils reçoivent un objet stable:
  - boneRotations: Record<BoneName, Quaternion>
  - morphParams: Record<string, number>
  - quality: number
- Aucun accès direct à vos internals.