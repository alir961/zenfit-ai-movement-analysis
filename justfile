set shell := ["powershell", "-NoProfile", "-Command"]

venv_dir := "workspace/backend/.venv"
py := venv_dir + "/Scripts/python.exe"

# ==============================================================================
# ENVIRONMENT SETUP & DIAGNOSTICS (BACKEND)
# ==============================================================================

# Pourquoi "Torch avant MIM/MMCV": 
# MMCV dépend fortement du couple Torch/CUDA; installer Torch d'abord permet à MIM de 
# résoudre les bons binaires, en évitant de basculer vers des builds source inutiles.
# Pourquoi utiliser MIM: 
# Installation recommandée par OpenMMLab pour simplifier la résolution des dépendances MMCV/MMEngine.
# Pourquoi pinner/stabiliser setuptools (69.5.1): 
# La version 70+ a supprimé 'pkg_resources', ce qui casse les builds source de MMCV. 
# En le pinnant et en utilisant --no-build-isolation, on garantit sa présence.
# Pourquoi séparer les checks finaux: 
# Détecter immédiatement les conflits transitoires et valider les imports runtime.

# Créer et configurer l'environnement virtuel robuste (Backend)
setup-venv:
    @echo "--- [1/6] Initialisation du venv dans {{venv_dir}} ---"
    if (!(Test-Path "{{venv_dir}}")) { python -m venv "{{venv_dir}}" }

    @echo "--- [2/6] Mise à jour des outils de packaging (pin setuptools 69.5.1) ---"
    {{py}} -m pip install --upgrade pip wheel "setuptools==69.5.1" packaging

    @echo "--- [3/6] Vérification/Installation de la stack Torch/CUDA ---"
    # On force Torch 2.4.1 pour maximiser la compatibilité avec les roues OpenMMLab.
    {{py}} -m pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
    {{py}} -c "import torch; print(f'Torch {torch.__version__} valide (CUDA: {torch.version.cuda})')"

    @echo "--- [4/6] Installation de OpenMMLab (MIM, MMEngine, MMCV) ---"
    {{py}} -m pip install openmim mmengine
    # On tente l'installation via MIM d'abord (recherche de roues pré-buildées)
    # Si ça échoue (pas de roue pour cu129), le build source utilisera le setuptools du venv
    # grâce à --no-build-isolation (on évite ainsi l'erreur pkg_resources).
    {{py}} -m pip install "mmcv>=2.0.1" --no-build-isolation -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html

    @echo "--- [5/6] Installation des requirements projet ---"
    if (Test-Path "workspace/backend/requirements.txt") { {{py}} -m pip install -r workspace/backend/requirements.txt }

    @echo "--- [6/6] Vérifications finales ---"
    just doctor-venv

# Exécuter les diagnostics de l'environnement virtuel
doctor-venv:
    @echo "=== [ZenFit Backend Diagnostic] ==="
    @echo "Python:     " $({{py}} --version)
    @echo "Pip:        " $({{py}} -m pip --version)
    @echo "Setuptools: " $({{py}} -c "import setuptools; print(setuptools.__version__)")
    @echo "--- Statut Torch / CUDA ---"
    {{py}} -c "import torch; print(f'Torch: {torch.__version__} | CUDA: {torch.version.cuda} | GPU: {torch.cuda.is_available()}')"
    @echo "--- Statut OpenMMLab ---"
    {{py}} -c "import mmcv; import mmengine; print(f'MMCV: {mmcv.__version__} | MMEngine: {mmengine.__version__}')"
    {{py}} -c "try: import mmpose; print(f'MMPose: {mmpose.__version__}'); except: print('MMPose: Non installé')"
    @echo "--- Intégrité Pip ---"
    {{py}} -m pip check
    @echo "===================================="

# Installation spécifique/forcée des composants OpenMMLab
install-mm:
    {{py}} -m pip install openmim mmengine
    {{py}} -m pip install "mmcv>=2.0.1" --no-build-isolation -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html

# ==============================================================================
# SUB-PROJECT TARGETS
# ==============================================================================

# --- Frontend ---

# Build frontend production bundle
build-frontend:
  ./scripts/build-frontend.ps1

# Run frontend dev server
dev-frontend:
  ./scripts/dev-frontend.ps1

# --- Backend ---

# Installer les dépendances backend (venv)
build-backend:
  ./scripts/build-backend.ps1

# Lancer le backend dev server
dev-backend:
  ./scripts/dev-backend.ps1

# --- Global ---

# Lancer le Frontend et le Backend (orchestration script)
dev:
  ./scripts/dev.ps1

# Lancer les linters
lint:
  ./scripts/lint.ps1

# Lancer les tests
test:
  ./scripts/test.ps1

# Build global (Frontend + Backend)
build:
  ./scripts/build.ps1

# ==============================================================================
# SPEEDY LEARNING (ONNX CUDA/cuDNN bootstrap)
# ==============================================================================

# Diagnostic + install deps CUDA/cuDNN Python for ONNXRuntime.
speedy-ort-fix:
  ./scripts/speedy-ort-cuda.ps1 -PythonExe "{{py}}" -InstallDeps -DoctorOnly

# Launch speedy_learning dev server with CUDA/cuDNN DLL PATH bootstrap.
speedy-dev:
  ./scripts/speedy-ort-cuda.ps1 -PythonExe "{{py}}" -RunScript "speedy_learning/run_dev.py"
