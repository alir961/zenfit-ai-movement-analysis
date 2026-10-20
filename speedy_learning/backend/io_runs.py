from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional


def ensure_session_id(session_id: Optional[str] = None) -> str:
    if session_id and session_id.strip():
        return session_id.strip()
    return f"sess_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def session_dir(base_runs: Path, session_id: str) -> Path:
    p = base_runs / session_id
    p.mkdir(parents=True, exist_ok=True)
    (p / "snapshots").mkdir(parents=True, exist_ok=True)
    return p


def append_frame(base_runs: Path, session_id: str, record: Dict) -> Path:
    sdir = session_dir(base_runs, session_id)
    path = sdir / "frames.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def save_stats(base_runs: Path, session_id: str, stats: Dict) -> Path:
    sdir = session_dir(base_runs, session_id)
    path = sdir / "stats.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return path


def load_stats(base_runs: Path, session_id: str) -> Optional[Dict]:
    path = base_runs / session_id / "stats.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
