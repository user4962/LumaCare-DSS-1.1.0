from __future__ import annotations

import fcntl
from pathlib import Path
from typing import IO

from sqlalchemy.engine import make_url


class SingleWorkerLock:
    """Prevent multiple API workers from owning one SQLite simulator database."""

    def __init__(self, database_url: str) -> None:
        url = make_url(database_url)
        database = url.database
        self._path: Path | None = None
        self._handle: IO[str] | None = None
        if url.drivername.startswith("sqlite") and database and database != ":memory:":
            self._path = Path(database).expanduser().resolve().with_suffix(
                Path(database).suffix + ".simulator.lock"
            )

    def acquire(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise RuntimeError(
                "A worker already owns the simulator lock for this SQLite database; run one worker"
            ) from exc
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

