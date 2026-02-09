[BLOC 4/4] — WS-APP (Web mobile/desktop + UI + Exercices + Intégration) — BRANCHE: feat/webapp-coach — DEADLINE: 28/01/2026

OBJECTIF
Livrer l’application web utilisable: caméra live + overlay + avatar 3D + détection d’exercices + scoring + feedback temps réel. Ce bloc assemble BLOC 1 + 2 + 3 sans modifier leur logique interne.

BRANCHE & RÈGLES
- Travailler UNIQUEMENT sur: feat/webapp-coach
- PR vers: develop
- Vous ne touchez pas aux modules internes des autres blocs sauf via leurs APIs/contrats.

LIVRABLES (à committer)
1) Web app (responsive mobile + desktop):
   - /apps/web/ (Next.js/Vite — selon votre stack)
   - pages:
     - / (caméra + squelette overlay + bouton start/stop)
     - /avatar (caméra + avatar 3D synchronisé)
     - /coach (exercice sélectionné + feedback)
2) Intégration pipeline temps réel:
   - camera frames → pose3d.infer → retarget → render avatar
   - exécuter l’inférence dans Worker si possible (latence UI)
3) Moteur exercices (MVP):
   - /packages/exercises/
   - ExerciseSpec (JSON/YAML) + 2 exercices minimum (ex: squat + fente)
   - rep counting (FSM) + score probabiliste simple:
     - p_correct = exp(-D^2 / (2σ^2)) (D = distance/DTW ou distance features)
   - feedback erreurs basiques (genoux, dos, amplitude) via seuils sur angles
4) UX minimale mais propre:
   - indicateur quality (0..1)
   - compteur reps
   - message “corrige X”
5) Build/Run + CI:
   - scripts: dev, build, test
   - lint + tests de contrats (PoseFrame/RigMap)
   - si vous avez CI: un check “bundle size” / “typecheck” est un plus

DEFINITION OF DONE (DoD) au 28/01/26
- Sur téléphone + desktop:
  - la caméra s’ouvre
  - le squelette bouge en live
  - l’avatar suit les mouvements (même si perfectible)
  - au moins 2 exercices détectés + reps + score + feedback
- Un README “run local” (5 lignes max) + 1 vidéo de démo (même courte)

INTEGRATION CONTRACT (IMPORTANT)
- Vous consommez strictement:
  - PoseFrame (BLOC 1)
  - avatar .glb + bones.md + blendshapes.md (BLOC 2)
  - retarget(...) (BLOC 3)
- Si quelque chose manque: vous ouvrez une issue, vous ne “patch” pas en direct dans leurs branches.