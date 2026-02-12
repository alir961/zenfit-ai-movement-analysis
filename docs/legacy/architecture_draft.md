# Architecture & Flux ZenFit (Brouillon)

Ceci est la représentation de l'architecture actuelle.
**Veuillez modifier ce fichier** pour ajouter, supprimer ou réorganiser les fonctionnalités et les pages selon vos besoins.

---

## 🏗️ Structure Globale

### 📱 **Page: Accueil (`/`)**
L'application est une Single Page App (SPA) gérée par des états.

#### 📦 Composants de Fond (Toujours actifs)
*   **[Background]** Fond noir "Zen" + Bruit visuel (Noise Overlay).
*   **[CameraFeed]** Flux Webcam (Opacité réduite).
*   **[PoseOverlay]** Dessin du squelette (Actuellement désactivé sur demande).

#### 🔄 États de l'Interface (Flow Utilisateur)

1.  **[État: IDLE] - Écran d'Accueil**
    *   **Titre** : "HARMONIE" (Corps & Esprit).
    *   **Action** : Bouton "COMMENCER"
        *   *Transition* -> Vers l'état `CALIBRATING`.

2.  **[État: CALIBRATING] - Écran de Calibration**
    *   **Texte** : "Prêt à commencer ?"
    *   **Action** : Bouton "MODE LIBRE"
        *   *Transition* -> Vers l'état `ACTIVE`.

3.  **[État: COUNTDOWN] - Compte à rebours**
    *   **Visuel** : Cercle qui se remplit + Chiffres (3, 2, 1).
    *   *Transition Auto* -> Vers l'état `ACTIVE` à la fin.

4.  **[État: ACTIVE] - Mode Performance (Entraînement)**
    *   **[HUD]** : Score (%) et Combo (xN) affichés en haut.
    *   **[PoseOverlay3D]** : Canvas 3D (R3F) superposé.
        *   *Contenu* : Cube Vert (Base pour IK).
    *   **Action** : Bouton "Arrêter" (Carré Rouge).
        *   *Transition* -> Retour à l'état `IDLE` (Reset).

---

## 🧠 Logique & Données

*   **[Hook] `usePoseDetection`** : Gère la boucle de la caméra.
*   **[Store] `poseStore`** : Gère l'état global.
*   **[Composant] `AvatarCanvas`** : Gère le rendu 3D (Three.js Fiber).
*   **[Worker] `pose.worker`** : Analyse l'image en arrière-plan.
