# PROJET ZENFIT - PLAN DE REFONTE UI/UX (CYBER-ZEN)

Ce document détaille la stratégie de refonte visuelle pour atteindre un rendu **Premium**, inspiré par l'esthétique "Harmonie & Mouvement".

## 1. VISION ARTISTIQUE

- **Concept** : "Cyber-Zen" — Mélange de minimalisme japonais (calme, espace) et de tech futuriste (néon, dark mode).
- **Thème** : Dark Mode intégral (`--black`) avec des accents néons (`--mint-leaf`).
- **Texture** : Glassmorphisme (flou d'arrière-plan), bordures fines lumineuses, ombres portées colorées (glow).

## 2. SYSTÈME DE COULEURS (PROPOSITION)

| Token              | Valeur    | Usage                                       |
| ------------------ | --------- | ------------------------------------------- |
| `--black`          | `#020100` | Fond principal (Inky Dark)                  |
| `--mint-leaf`      | `#00cc99` | CTA, Logo accent, Bordures actives          |
| `--jasmine`        | `#ffee88` | Points de focus secondaires, alertes douces |
| `--majorelle-blue` | `#724cf9` | Dégradés subtils, Glow secondaire           |
| `--lavender`       | `#e8e1ef` | Texte secondaire, contrastes doux           |

## 3. DISPOSITION LOGIQUE (ASCII)

### A. Live Coach Page (Mobile-First Centered Layout)

```text
+-------------------------------------------------------------+
| [PROJECT]              Z E N F I T (logo)           [SOUND] |
+-------------------------------------------------------------+
|                                                             |
|                                                             |
|                          ( 調 和 )                          |
|                    HARMONIE & MOUVEMENT                     |
|                                                             |
|                                                             |
|                    +------------------+                     |
|                    |     SESSION      |                     |
|                    |     LIVE R3F     |                     |
|                    |    (Avatar)      |                     |
|                    +------------------+                     |
|                                                             |
|            +-----------------------------------+            |
|            | icon  Coach postural intelligent.  |            |
|            |                                   |            |
|            |        [    COMMENCER ->    ]     |            |
|            +-----------------------------------+            |
|                                                             |
+-------------------------------------------------------------+
```

### B. Admin Debug Page (Hybrid Dashboard)

```text
+-------------------------------------------------------------+
| < BACK               A D M I N   D E B U G           [STATS]|
+-------------------------------------------------------------+
| +------------------------+   +----------------------------+ |
| |       VIDEO FEED       |   |      GEOMETRIC RIG         | |
| | (Raw Pose Detection)   |   | (Normalized Skeleton)      | |
| +------------------------+   +----------------------------+ |
|                                                             |
| +---------------------------------------------------------+ |
| |                     METRICS PANEL                       | |
| | Joint: Confidence | Distances | Body Scale | Normaliz.  | |
| +---------------------------------------------------------+ |
+-------------------------------------------------------------+
```

## 4. ARCHITECTURE CSS (Dossier /styles)

Pour éviter de polluer `globals.css`, nous pistons les fichiers suivants :

- `styles/tokens.css` : Variables uniquement (Couleurs, Typo, Radius).
- `styles/layout.css` : Grilles, Flexbox, Containment.
- `styles/typography.css` : Styles de texte (Harmonie, Display, Body).
- `styles/glass.css` : Classes utilitaires pour le glassmorphisme et les effets neon.
- `styles/components/` :
  - `button.css` : Styles premium pour les pills et glows.
  - `coach-card.css` : Carte panda et feedback live.
  - `video-container.css` : Styles pour le flux caméra et les skeletons.

## 5. PLAN D'ACTION UX

1. **Phase Alpha (Tokens)** : Mettre à jour `tokens.css` pour forcer le mode sombre et les nouvelles palettes.
2. **Phase Bêta (Layout)** : Implémenter le conteneur centré (`max-width: 600px`) pour la page principale pour simuler l'expérience mobile premium vue dans l'image.
3. **Phase Gamma (Effets)** : Appliquer les filtres `backdrop-filter: blur()` et les bordures néons.
4. **Phase Delta (Typography)** : Intégrer des Google Fonts premium (ex: Space Grotesk pour le côté technique, Noto Sans JP pour l'élégance).

---

_ZenFit - L'harmonie par la précision._
