"""Shared storage configuration. Author: Dev Anh Khôi. Version: 1.3.0."""
import os
import sqlite3
import tempfile
import threading
import time
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.environ.get("APP_DATA_DIR") or BASE_DIR)
DATABASE_PATH = os.path.abspath(os.environ.get("DATABASE_PATH") or os.path.join(DATA_DIR, "database.db"))
UPLOAD_PATH = os.path.join(DATA_DIR, "uploads")
FILE_WRITE_LOCK = threading.RLock()


def storage_identity(connection):
    """An opaque identifier shared by receipts and the Mini App, never a path."""
    existing = connection.execute("SELECT value FROM app_settings WHERE key='storage_id'").fetchone()
    if existing:
        return existing[0]
    connection.execute("INSERT OR IGNORE INTO app_settings(key, value) VALUES('storage_id', ?)", (uuid.uuid4().hex,))
    connection.commit()
    row = connection.execute("SELECT value FROM app_settings WHERE key='storage_id'").fetchone()
    return row[0]


def account_receipt(connection, account_id):
    row = connection.execute("SELECT id, chat_cmd_enabled FROM accounts WHERE id=?", (account_id,)).fetchone()
    if row is None:
        raise ValueError("Tài khoản chưa có trong dữ liệu")
    return {"account_id": row[0], "commands_enabled": bool(row[1] if row[1] is not None else 1),
            "storage_id": storage_identity(connection),
            "account_count": connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]}


def normalize_file_index(connection, folder):
    """Repair legacy timestamp aliases/old deploy paths without moving any file."""
    names = {}
    for record_id, old_name, old_path in connection.execute("SELECT id, filename, filepath FROM files ORDER BY id"):
        basename = os.path.basename(str(old_path or old_name or "").replace("\\", "/"))
        candidate = os.path.join(folder, basename)
        if not basename.lower().endswith(".txt") or not os.path.isfile(candidate) or os.path.islink(candidate):
            continue
        names[str(old_name or "").lower()] = basename
        if old_name != basename or old_path != candidate:
            connection.execute("UPDATE files SET filename=?, filepath=? WHERE id=?", (basename, candidate, record_id))
    for key, value in connection.execute("SELECT key, value FROM app_settings WHERE key IN ('selected_nhay_file', 'selected_ngon_file')"):
        normalized = names.get(str(value or "").lower())
        if normalized and normalized != value:
            connection.execute("UPDATE app_settings SET value=? WHERE key=?", (normalized, key))


def connect_database(path=None, *, rows=False):
    """A database error must never silently select a different database."""
    connection = sqlite3.connect(path or DATABASE_PATH, timeout=15, check_same_thread=False)
    try:
        if rows:
            connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA cache_size=-2048")
        return connection
    except Exception:
        connection.close()
        raise


def save_text_file(connection_factory, folder, filename, content, file_type):
    """Register the exact on-disk name and restore the previous file on failure."""
    os.makedirs(folder, exist_ok=True)
    destination = os.path.join(folder, filename)
    if os.path.islink(destination):
        raise ValueError("Không ghi đè liên kết tệp")
    line_count = len(content.splitlines())
    with FILE_WRITE_LOCK:
        previous = None
        previous_ready = False
        temporary = None
        replaced = False
        committed = False
        connection = connection_factory()
        try:
            with tempfile.NamedTemporaryFile(dir=folder, prefix=".text-", delete=False) as output:
                temporary = output.name
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            existing = connection.execute("SELECT id FROM files WHERE lower(filename)=? ORDER BY id DESC LIMIT 1", (filename.lower(),)).fetchone()
            if existing:
                connection.execute("UPDATE files SET filepath=?, lines_count=?, created_at=?, file_type=? WHERE id=?",
                                   (destination, line_count, time.time(), file_type, existing[0]))
            else:
                connection.execute(
                    "INSERT INTO files (filename, filepath, lines_count, created_at, file_type) VALUES (?, ?, ?, ?, ?)",
                    (filename, destination, line_count, time.time(), file_type),
                )
            if os.path.isfile(destination):
                with tempfile.NamedTemporaryFile(dir=folder, prefix=".previous-", delete=False) as backup:
                    previous = backup.name
                os.replace(destination, previous)
                previous_ready = True
            os.replace(temporary, destination)
            temporary = None
            replaced = True
            connection.commit()
            committed = True
        except Exception:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
            if previous_ready:
                os.replace(previous, destination)
                previous = None
            elif replaced:
                os.unlink(destination)
            raise
        finally:
            connection.close()
            # Keep a recovery backup if restoring it failed; never discard it
            # merely because rollback/rename encountered an I/O error.
            for leftover in (temporary, previous if committed or not previous_ready else None):
                if leftover and os.path.exists(leftover):
                    os.unlink(leftover)
    return {"filename": filename, "lines": line_count, "size_kb": round(len(content) / 1024, 1)}
