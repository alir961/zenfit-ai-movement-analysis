set shell := ["bash", "-cu"]
set windows-shell := ["powershell", "-NoProfile", "-Command"]

venv_dir := "workspace/backend/.venv"
py := venv_dir + "/Scripts/python.exe"
speedy_venv_dir := "speedy_learning/.venv"
speedy_py := speedy_venv_dir + "/Scripts/python.exe"
script_ext := if os_family() == "windows" { "ps1" } else { "sh" }

setup-venv:
  ./scripts/setup-venv.{{script_ext}}

doctor-venv:
  ./scripts/doctor-venv.{{script_ext}}

install-mm:
  ./scripts/install-mm.{{script_ext}}

build-frontend:
  ./scripts/build-frontend.{{script_ext}}

dev-frontend:
  ./scripts/dev-frontend.{{script_ext}}

build-backend:
  ./scripts/build-backend.{{script_ext}}

dev-backend:
  ./scripts/dev-backend.{{script_ext}}

dev:
  ./scripts/dev.{{script_ext}}

lint:
  ./scripts/lint.{{script_ext}}

test:
  ./scripts/test.{{script_ext}}

build:
  ./scripts/build.{{script_ext}}

speedy-venv-create:
  {{ if os_family() == "windows" { "if (!(Test-Path \"" + speedy_venv_dir + "\")) { python -m venv \"" + speedy_venv_dir + "\" }" } else { "if [ ! -d \"" + speedy_venv_dir + "\" ]; then python3 -m venv \"" + speedy_venv_dir + "\"; fi" } }}
  {{ if os_family() == "windows" { speedy_py + " -m pip install --upgrade pip wheel setuptools==60.2.0" } else { speedy_venv_dir + "/bin/python -m pip install --upgrade pip wheel setuptools==60.2.0" } }}

speedy-venv-install:
  {{ if os_family() == "windows" {
    "$attempts = 3; " +
    "$ok = $false; " +
    "for ($i = 1; $i -le $attempts; $i++) { " +
      "Write-Host \"[speedy] pip install attempt $i/$attempts\" -ForegroundColor Cyan; " +
      "& \"" + speedy_py + "\" -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 -r speedy_learning/backend/requirements.txt; " +
      "if ($LASTEXITCODE -eq 0) { $ok = $true; break }; " +
      "if ($i -lt $attempts) { Write-Warning \"[speedy] pip install failed, retry in 5s...\"; Start-Sleep -Seconds 5 } " +
    "}; " +
    "if (-not $ok) { throw \"speedy-venv-install failed after $attempts attempts\" }"
  } else { speedy_venv_dir + "/bin/python -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 -r speedy_learning/backend/requirements.txt" } }}

speedy-third-party-ensure:
  {{ if os_family() == "windows" { "./scripts/speedy-third-party-ensure.ps1" } else { "./scripts/speedy-third-party-ensure.sh" } }}

speedy-onnx-prepare:
  just speedy-third-party-ensure
  {{ if os_family() == "windows" { "./scripts/speedy-prepare-onnx.ps1 -PythonExe \"" + speedy_py + "\"" } else { "PYTHON_EXE=" + speedy_venv_dir + "/bin/python ./scripts/speedy-prepare-onnx.sh" } }}

speedy-venv-doctor:
  {{ if os_family() == "windows" { speedy_py + " -c \"import sys; print(sys.executable); print('prefix=', sys.prefix)\"" } else { speedy_venv_dir + "/bin/python -c \"import sys; print(sys.executable); print('prefix=', sys.prefix)\"" } }}
  {{ if os_family() == "windows" { speedy_py + " -m pip --version" } else { speedy_venv_dir + "/bin/python -m pip --version" } }}
  {{ if os_family() == "windows" { speedy_py + " -c \"import onnxruntime as ort; print(ort.get_available_providers())\"" } else { speedy_venv_dir + "/bin/python -c \"import onnxruntime as ort; print(ort.get_available_providers())\"" } }}

speedy-venv-freeze:
  {{ if os_family() == "windows" { speedy_py + " -m pip freeze > speedy_learning/backend/requirements.txt" } else { speedy_venv_dir + "/bin/python -m pip freeze > speedy_learning/backend/requirements.txt" } }}

speedy-ort-fix:
  {{ if os_family() == "windows" { "./scripts/speedy-ort-cuda.ps1 -PythonExe \"" + speedy_py + "\" -InstallDeps -DoctorOnly" } else { "PYTHON_EXE=" + speedy_venv_dir + "/bin/python INSTALL_DEPS=1 DOCTOR_ONLY=1 ./scripts/speedy-ort-cuda.sh" } }}

speedy-dev:
  just speedy-third-party-ensure
  {{ if os_family() == "windows" { "./scripts/speedy-prepare-onnx.ps1 -PythonExe \"" + speedy_py + "\"" } else { "PYTHON_EXE=" + speedy_venv_dir + "/bin/python ./scripts/speedy-prepare-onnx.sh" } }}
  {{ if os_family() == "windows" { "./scripts/speedy-ort-cuda.ps1 -PythonExe \"" + speedy_py + "\" -RunScript \"speedy_learning/run_dev.py\"" } else { "PYTHON_EXE=" + speedy_venv_dir + "/bin/python RUN_SCRIPT=speedy_learning/run_dev.py ./scripts/speedy-ort-cuda.sh" } }}

speedy-test:
  {{ if os_family() == "windows" { speedy_py + " speedy_learning/run_test.py" } else { speedy_venv_dir + "/bin/python speedy_learning/run_test.py" } }}

speedy-install:
  just speedy-venv-create
  just speedy-venv-install
  just speedy-third-party-ensure
  just speedy-onnx-prepare
  just speedy-ort-fix
  just speedy-venv-doctor
