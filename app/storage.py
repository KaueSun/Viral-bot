from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DB_PATH = Path("data/state.json")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class JsonStore:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        if not self.path.exists():
            self._write({"clips": []})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_clip(self, item: dict[str, Any]) -> None:
        data = self._read()
        data["clips"].append(item)
        self._write(data)

    def list_clips(self) -> list[dict[str, Any]]:
        return self._read().get("clips", [])

    def update_publish_status(self, clip_id: str, status: str) -> bool:
        data = self._read()
        updated = False
        for clip in data.get("clips", []):
            if clip["id"] == clip_id:
                clip["publish_status"] = status
                updated = True
                break
        if updated:
            self._write(data)
        return updated


store = JsonStore()