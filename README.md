# ZenFit MVP

## Structure
- `workspace/frontend` Next.js app
- `workspace/backend` Socket.IO + RTMW3D runtime
- `docs` architecture, socket events, debug metrics

## Frontend

```
cd workspace/frontend
bun install
bun run dev
```

## Backend

```
cd workspace/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Scripts

```
./scripts/dev.ps1
./scripts/lint.ps1
./scripts/test.ps1
./scripts/build.ps1
```
