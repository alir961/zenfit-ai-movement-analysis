[BLOC 2/4] — WS-AVATAR3D (Modèles H/F + Rig + Blendshapes) — BRANCHE: feat/avatar-rig-blend — DEADLINE: 28/01/2026

OBJECTIF
Fournir 2 avatars (H/F) utilisables en production web: rig humanoïde propre + morph targets (blendshapes) pour muscles/corpulence + scaling facile.

BRANCHE & RÈGLES
- Travailler UNIQUEMENT sur: feat/avatar-rig-blend
- PR vers: develop
- Aucun code ML ni retargeting: ce bloc livre des assets + docs d’import + mapping os.

LIVRABLES (à committer)
1) Assets glTF/GLB (ou VRM si vous standardisez VRM):
   - /assets/avatars/male.glb
   - /assets/avatars/female.glb
2) Skeleton stable:
   - bone naming documenté: /assets/avatars/bones.md
   - bind pose fixée (T-pose ou A-pose), même convention pour H et F
3) Blendshapes (morph targets):
   - Minimum 6 “muscles groups” + 3 “body morph”:
     - muscles: biceps, pectoraux, deltoïdes, abdos, quadriceps, mollets (exemple)
     - morph: thin, average, bulk (ou “fat” selon votre approche)
   - Document slider ranges: /assets/avatars/blendshapes.md
4) Gabarits & scaling:
   - une méthode simple pour “adapter la taille”: scale global + proportions (si vous avez)
   - notes Blender: /assets/avatars/pipeline_blender.md
5) Scène de test:
   - /assets/avatars/test_scene.blend (ou un glTF viewer setup)
   - vérifie que les morphs bougent sans casser la skin

DEFINITION OF DONE (DoD) au 28/01/26
- Import Three.js: l’avatar s’affiche, matériaux OK, skeleton OK, animations/pose possibles
- Blendshapes visibles et pilotables (0→1) sans glitch majeur
- H & F partagent la même convention d’os (ou mapping explicite si différent)
- Export final léger (objectif: éviter un GLB énorme)

CONTRAINTES IMPORTANTES
- Garder le pipeline reproductible (notes exactes d’export)
- Ne pas dépendre d’un outil/licence bloquante pour redistribuer le projet
- S’assurer que la topologie supporte les morph targets sans artefacts extrêmes

INTERFACE GARANTIE POUR LES AUTRES BLOCS
- Les autres ne consomment QUE:
  - le fichier .glb/.vrm
  - bones.md (noms des os)
  - blendshapes.md (noms des morph targets)