[BLOC 1/4] — WS-POSE3D (ML / Inference) — BRANCHE: feat/pose3d-runtime — DEADLINE: 28/01/2026

OBJECTIF
Produire un module “Pose 3D temps réel” (caméra → joints 3D + confidence) stable, testable, et consommable par les autres blocs via une interface unique (PoseFrame).

BRANCHE & RÈGLES
- Travailler UNIQUEMENT sur: feat/pose3d-runtime
- PR vers: develop (ou main si votre repo n’a pas develop)
- Aucun changement dans l’avatar/retargeting/UI: ce bloc ne touche qu’au runtime pose + I/O.

LIVRABLES (à committer)
1) Contrat de données figé: /packages/contracts/src/PoseFrame.ts (ou /contracts/PoseFrame.json)
   - PoseFrame = { t, space, joints[] } 
   - joints[] = { name, x, y, z, c } (c = confidence)
2) Module d’inférence:
   - /packages/pose3d/ (ou /backend/pose3d/)
   - API: infer(frameRGB) => PoseFrame
   - Option: pipeline en WebWorker (si côté front) OU service backend minimal (si côté serveur)
3) Normalisation minimale I/O:
   - noms de joints cohérents (liste figée dans /packages/contracts/joints.list)
4) Bench & tests:
   - /packages/pose3d/scripts/bench.ts : FPS + latence moyenne
   - /packages/pose3d/tests/poseframe.test.ts : valide schéma + valeurs finies
5) “Demo minimal” (sans UI fancy):
   - une page/test ou script qui affiche le squelette 2D overlay (juste pour valider que ça tourne)

DEFINITION OF DONE (DoD) au 28/01/26
- PoseFrame valide à chaque frame (pas de NaN, pas d’inf)
- 20 FPS minimum desktop, et un mode “perf” (downscale) pour mobile
- Liste de joints stable + documentée (README du module)
- Exemple d’appel clair: 10 lignes de code qui retournent PoseFrame

CHECKLIST TECHNIQUE
- Gestion des erreurs caméra (permission, device absent)
- Stratégie fallback si confidence trop basse (marquer c faible, pas inventer)
- Sortie “space” = "camera" (si world non géré au MVP)

INTERFACE GARANTIE POUR LES AUTRES BLOCS
- Ils ne doivent dépendre QUE de PoseFrame + joints.list, rien d’autre.