from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DB_PATH = Path("data/state.db")
LEGACY_JSON_PATH = Path("data/state.json")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_COLUMNS = ["nao_postados", "a_postar", "programados", "postados"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteStore:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._init_db()
        self._maybe_import_legacy_json()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    creator_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_value TEXT,
                    source_title TEXT,
                    source_path TEXT,
                    include_subtitles INTEGER NOT NULL DEFAULT 1,
                    final_title TEXT,
                    final_video_path TEXT,
                    final_thumbnail_path TEXT,
                    final_duration_seconds REAL,
                    subtitle_font TEXT NOT NULL,
                    subtitle_color TEXT NOT NULL,
                    cut_style TEXT NOT NULL,
                    top_n INTEGER NOT NULL,
                    min_clip_seconds INTEGER NOT NULL,
                    max_clip_seconds INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    message TEXT,
                    error_message TEXT,
                    clips_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS clips (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    creator_name TEXT NOT NULL,
                    source_type TEXT,
                    source_title TEXT,
                    source_path TEXT,
                    clip_path TEXT,
                    subtitle_path TEXT,
                    thumbnail_path TEXT,
                    start_seconds REAL,
                    end_seconds REAL,
                    duration_seconds REAL,
                    score REAL,
                    title TEXT,
                    caption TEXT,
                    hashtags_text TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    include_subtitles INTEGER NOT NULL DEFAULT 1,
                    subtitle_font TEXT,
                    subtitle_color TEXT,
                    cut_style TEXT,
                    board_column TEXT NOT NULL,
                    publish_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_clips_job_id ON clips(job_id);
                CREATE INDEX IF NOT EXISTS idx_clips_board_column ON clips(board_column);
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
                """
            )
            self._ensure_column(conn, "jobs", "final_title", "TEXT")
            self._ensure_column(conn, "jobs", "final_video_path", "TEXT")
            self._ensure_column(conn, "jobs", "final_thumbnail_path", "TEXT")
            self._ensure_column(conn, "jobs", "final_duration_seconds", "REAL")
            self._ensure_column(conn, "jobs", "include_subtitles", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "clips", "include_subtitles", "INTEGER NOT NULL DEFAULT 1")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    def _maybe_import_legacy_json(self) -> None:
        if not LEGACY_JSON_PATH.exists():
            return

        with self._connect() as conn:
            has_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] > 0
            has_clips = conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0] > 0
        if has_jobs or has_clips:
            return

        try:
            data = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        for legacy_clip in data.get("clips", []):
            clip_id = legacy_clip.get("id") or uuid4().hex
            job_id = f"legacy_{clip_id}"
            created_at = utc_now()
            job = {
                "id": job_id,
                "creator_name": legacy_clip.get("creator_name", "Legacy"),
                "source_type": "local",
                "source_value": legacy_clip.get("source_path", ""),
                "source_title": legacy_clip.get("source_title", ""),
                "source_path": legacy_clip.get("source_path", ""),
                "include_subtitles": 1 if legacy_clip.get("subtitle_path") else 0,
                "final_title": legacy_clip.get("title", ""),
                "final_video_path": legacy_clip.get("clip_path", ""),
                "final_thumbnail_path": legacy_clip.get("thumbnail_path", ""),
                "final_duration_seconds": legacy_clip.get("duration_seconds", 0),
                "subtitle_font": legacy_clip.get("subtitle_font", "Arial"),
                "subtitle_color": legacy_clip.get("subtitle_color", "yellow"),
                "cut_style": legacy_clip.get("cut_style", "viral"),
                "top_n": 1,
                "min_clip_seconds": int(legacy_clip.get("duration_seconds", 20) or 20),
                "max_clip_seconds": int(legacy_clip.get("duration_seconds", 20) or 20),
                "status": "completed",
                "stage": "done",
                "message": "Importado do estado antigo.",
                "error_message": None,
                "clips_count": 0,
                "created_at": created_at,
                "updated_at": created_at,
                "started_at": created_at,
                "finished_at": created_at,
            }
            self.create_job(job)

            clip = dict(legacy_clip)
            clip.setdefault("job_id", job_id)
            clip.setdefault("creator_name", job["creator_name"])
            clip.setdefault("source_type", "local")
            clip.setdefault("hashtags_text", "")
            clip.setdefault("notes", "")
            clip.setdefault("subtitle_font", "Arial")
            clip.setdefault("subtitle_color", "yellow")
            clip.setdefault("cut_style", "viral")
            clip.setdefault("board_column", "nao_postados")
            clip.setdefault("publish_status", "draft")
            self.add_clip(clip)

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        payload = {
            "id": job["id"],
            "creator_name": job["creator_name"],
            "source_type": job["source_type"],
            "source_value": job.get("source_value"),
            "source_title": job.get("source_title"),
            "source_path": job.get("source_path"),
            "include_subtitles": 1 if job.get("include_subtitles", True) else 0,
            "final_title": job.get("final_title"),
            "final_video_path": job.get("final_video_path"),
            "final_thumbnail_path": job.get("final_thumbnail_path"),
            "final_duration_seconds": job.get("final_duration_seconds"),
            "subtitle_font": job["subtitle_font"],
            "subtitle_color": job["subtitle_color"],
            "cut_style": job["cut_style"],
            "top_n": job["top_n"],
            "min_clip_seconds": job["min_clip_seconds"],
            "max_clip_seconds": job["max_clip_seconds"],
            "status": job.get("status", "queued"),
            "stage": job.get("stage", "waiting"),
            "message": job.get("message"),
            "error_message": job.get("error_message"),
            "clips_count": job.get("clips_count", 0),
            "created_at": job.get("created_at", now),
            "updated_at": job.get("updated_at", now),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, creator_name, source_type, source_value, source_title, source_path,
                    include_subtitles,
                    final_title, final_video_path, final_thumbnail_path, final_duration_seconds,
                    subtitle_font, subtitle_color, cut_style, top_n, min_clip_seconds,
                    max_clip_seconds, status, stage, message, error_message, clips_count,
                    created_at, updated_at, started_at, finished_at
                ) VALUES (
                    :id, :creator_name, :source_type, :source_value, :source_title, :source_path,
                    :include_subtitles,
                    :final_title, :final_video_path, :final_thumbnail_path, :final_duration_seconds,
                    :subtitle_font, :subtitle_color, :cut_style, :top_n, :min_clip_seconds,
                    :max_clip_seconds, :status, :stage, :message, :error_message, :clips_count,
                    :created_at, :updated_at, :started_at, :finished_at
                )
                """,
                payload,
            )
        return self.get_job(payload["id"]) or payload

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_job(job_id)

        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = :{key}" for key in fields)
        fields["id"] = job_id
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE id = :id", fields)
        return self.get_job(job_id)

    def increment_job_clips_count(self, job_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET clips_count = clips_count + 1, updated_at = ? WHERE id = ?",
                (utc_now(), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_dict(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def add_clip(self, item: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        payload = {
            "id": item["id"],
            "job_id": item["job_id"],
            "creator_name": item["creator_name"],
            "source_type": item.get("source_type", "local"),
            "source_title": item["source_title"],
            "source_path": item["source_path"],
            "clip_path": item["clip_path"],
            "subtitle_path": item.get("subtitle_path"),
            "thumbnail_path": item.get("thumbnail_path"),
            "start_seconds": item["start_seconds"],
            "end_seconds": item["end_seconds"],
            "duration_seconds": item["duration_seconds"],
            "score": item["score"],
            "title": item["title"],
            "caption": item["caption"],
            "hashtags_text": item.get("hashtags_text", ""),
            "notes": item.get("notes", ""),
            "include_subtitles": 1 if item.get("include_subtitles", True) else 0,
            "subtitle_font": item.get("subtitle_font", "Arial"),
            "subtitle_color": item.get("subtitle_color", "yellow"),
            "cut_style": item.get("cut_style", "viral"),
            "board_column": item.get("board_column", "nao_postados"),
            "publish_status": item.get("publish_status", "draft"),
            "created_at": item.get("created_at", now),
            "updated_at": item.get("updated_at", now),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO clips (
                    id, job_id, creator_name, source_type, source_title, source_path, clip_path,
                    subtitle_path, thumbnail_path, start_seconds, end_seconds, duration_seconds,
                    score, title, caption, hashtags_text, notes, include_subtitles, subtitle_font, subtitle_color,
                    cut_style, board_column, publish_status, created_at, updated_at
                ) VALUES (
                    :id, :job_id, :creator_name, :source_type, :source_title, :source_path, :clip_path,
                    :subtitle_path, :thumbnail_path, :start_seconds, :end_seconds, :duration_seconds,
                    :score, :title, :caption, :hashtags_text, :notes, :include_subtitles, :subtitle_font, :subtitle_color,
                    :cut_style, :board_column, :publish_status, :created_at, :updated_at
                )
                """,
                payload,
            )
        self.increment_job_clips_count(payload["job_id"])
        return self.get_clip(payload["id"]) or payload

    def list_clips(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM clips ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def list_clips_for_job(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM clips WHERE job_id = ? ORDER BY created_at DESC",
                (job_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows if row is not None]

    def get_clip(self, clip_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
        return self._row_to_dict(row)

    def update_publish_status(self, clip_id: str, status: str) -> bool:
        fields: dict[str, Any] = {"publish_status": status}
        if status == "published":
            fields["board_column"] = "postados"
        return self.update_clip(clip_id, **fields) is not None

    def update_board_column(self, clip_id: str, column: str) -> bool:
        if column not in DEFAULT_COLUMNS:
            return False
        return self.update_clip(clip_id, board_column=column) is not None

    def update_clip(self, clip_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_clip(clip_id)

        if "board_column" in fields and fields["board_column"] not in DEFAULT_COLUMNS:
            return None

        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = :{key}" for key in fields)
        fields["id"] = clip_id
        with self._connect() as conn:
            cursor = conn.execute(f"UPDATE clips SET {assignments} WHERE id = :id", fields)
        if cursor.rowcount == 0:
            return None
        return self.get_clip(clip_id)

    def delete_clip(self, clip_id: str) -> dict[str, Any] | None:
        clip = self.get_clip(clip_id)
        if clip is None:
            return None

        with self._connect() as conn:
            conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
            conn.execute(
                """
                UPDATE jobs
                SET clips_count = (
                    SELECT COUNT(*) FROM clips WHERE job_id = ?
                ),
                updated_at = ?
                WHERE id = ?
                """,
                (clip["job_id"], utc_now(), clip["job_id"]),
            )
        return clip

    def board(self) -> dict[str, list[dict[str, Any]]]:
        columns = {column: [] for column in DEFAULT_COLUMNS}
        for clip in self.list_clips():
            columns.setdefault(clip.get("board_column", "nao_postados"), []).append(clip)
        return columns


store = SqliteStore()
