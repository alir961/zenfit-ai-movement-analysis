## 🎯 PROMPT — Migration / Création page Web vers Next.js + Three.js (latest)

> **Rôle**
> Tu es un **Senior Frontend / WebGL Engineer** spécialisé en **Next.js App Router, Three.js, Web Workers et WebRTC**.

> **Objectif**
> Créer une **page web équivalente à une page HTML existante** (caméra + overlay + rendu 3D), mais **adaptée à Next.js (dernière version stable)** avec **Three.js moderne**, architecture propre, performante et prête pour une app temps réel.

---

### 🔧 Stack technique imposée (versions récentes)

* **Next.js (App Router)** – dernière version stable
* **React 18+**
* **Three.js (latest)**
* **@react-three/fiber**
* **@react-three/drei**
* **TypeScript**
* **Web Workers** pour calcul lourd (inférence / pose)
* **WebRTC / getUserMedia** pour la caméra
* **pnpm** comme gestionnaire de paquets (par défaut)

---

### 📁 Structure attendue

```
apps/web/
├─ app/
│  ├─ page.tsx              # caméra + overlay squelette
│  ├─ avatar/page.tsx       # caméra + avatar 3D synchronisé
│  ├─ coach/page.tsx        # exercice + feedback
│  ├─ layout.tsx
│  └─ globals.css
├─ components/
│  ├─ CameraFeed.tsx
│  ├─ PoseOverlay.tsx
│  ├─ AvatarCanvas.tsx
│  └─ UIControls.tsx
├─ workers/
│  └─ pose.worker.ts
├─ lib/
│  ├─ posePipeline.ts
│  └─ contracts.ts
├─ public/
│  └─ avatar.glb
└─ package.json
```

---

### 📦 Dépendances à configurer (versions actuelles)

* `three`
* `@react-three/fiber`
* `@react-three/drei`
* `zustand` (state temps réel)
* `classnames`
* `stats.js` (optionnel debug perf)
* `eslint`, `typescript`, `prettier`

Inclure :

* scripts `dev`, `build`, `lint`, `typecheck`
* config ESLint compatible Next
* config TS stricte

---

### 🎥 Fonctionnalités à implémenter

1. **Caméra live**

   * `navigator.mediaDevices.getUserMedia`
   * compatible mobile + desktop
   * fallback erreur permission

2. **Overlay squelette**

   * Canvas 2D au-dessus de la vidéo
   * rendu depuis un objet `PoseFrame`

3. **Avatar 3D**

   * rendu via `<Canvas />` (react-three-fiber)
   * chargement `.glb`
   * synchronisation des bones depuis `retarget(...)`

4. **Pipeline temps réel**

```
Camera → PoseFrame → Worker → retarget → Three.js
```

5. **Web Worker**

   * aucune logique lourde sur le thread UI
   * communication via `postMessage`

---

### ⚠️ Contraintes importantes

* ❌ Pas de modification de logique métier externe
* ✅ Consommer uniquement des APIs/contrats
* ✅ Code compatible SSR mais rendu caméra **client-only**
* ✅ Séparer clairement UI / calcul / rendu

---

### 🧠 Bonnes pratiques exigées

* `use client` uniquement où nécessaire
* lazy loading du Canvas 3D
* resize observer pour responsive
* cleanup caméra / worker à l’unmount
* types stricts pour PoseFrame / RigMap

---

### 📄 Livrables générés par l’IA

* Code complet prêt à lancer
* `package.json` à jour
* Exemple de composant Camera
* Exemple de Web Worker
* Instructions `pnpm install && pnpm dev`

---

Si tu veux, au prochain message je peux :

* 🔹 adapter ce prompt **exactement à ton HTML actuel**
* 🔹 générer **le package.json réel** (versions exactes)
* 🔹 générer **la page `/app/page.tsx` complète**
* 🔹 ou te faire un **starter repo monorepo (apps/packages)**
