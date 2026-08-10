"""
database.py — Persistence layer.
- SQLite: session/conversation metadata (lightweight, file-based).
- ChromaDB: optional semantic search over text columns (reviews, feedback, etc.)
  Only used when a dataset actually contains meaningful free text.
DuckDB (the analytical engine) lives in data_engine.py, not here.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager

from config import settings

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                entities TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS datasets_meta (
                dataset_id TEXT PRIMARY KEY,
                filename TEXT,
                uploaded_at TEXT,
                meta_json TEXT
            )
        """)


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

def add_message(session_id: str, role: str, content: str, entities: dict | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, entities) VALUES (?, ?, ?, ?)",
            (session_id, role, content, json.dumps(entities or {})),
        )


def get_recent_context(session_id: str, limit: int = 6) -> list[dict]:
    """Return a compact, recent slice of the conversation — not the full history."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT role, content, entities FROM conversations WHERE session_id=? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cur.fetchall()
    rows.reverse()
    return [{"role": r[0], "content": r[1], "entities": json.loads(r[2] or "{}")} for r in rows]


def save_dataset_meta(dataset_id: str, filename: str, uploaded_at: str, meta: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO datasets_meta (dataset_id, filename, uploaded_at, meta_json) "
            "VALUES (?, ?, ?, ?)",
            (dataset_id, filename, uploaded_at, json.dumps(meta)),
        )


# ---------------------------------------------------------------------------
# ChromaDB semantic search (optional, lazy-loaded)
# ---------------------------------------------------------------------------

_chroma_client = None


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    return _chroma_client


def index_text_column(dataset_id: str, column: str, ids: list[str], documents: list[str], metadatas: list[dict]):
    if not settings.SEMANTIC_SEARCH_ENABLED or not documents:
        return False
    try:
        client = _get_chroma_client()
        collection_name = f"ds_{dataset_id}_{column}"[:63]
        collection = client.get_or_create_collection(collection_name)
        # Chroma requires unique ids and non-empty docs
        filtered = [(i, d, m) for i, d, m in zip(ids, documents, metadatas) if isinstance(d, str) and d.strip()]
        if not filtered:
            return False
        ids_f = [f[0] for f in filtered]
        docs_f = [f[1] for f in filtered]
        meta_f = [f[2] for f in filtered]
        # Batch to avoid oversized single calls
        batch = 200
        for i in range(0, len(ids_f), batch):
            collection.upsert(
                ids=ids_f[i:i + batch],
                documents=docs_f[i:i + batch],
                metadatas=meta_f[i:i + batch],
            )
        return True
    except Exception:  # noqa: BLE001
        # Semantic search is an optional enhancement (e.g. embedding model download
        # can fail in offline/restricted environments) — never let it break upload.
        return False


def semantic_search(dataset_id: str, column: str, query: str, top_k: int = 8) -> list[dict]:
    try:
        client = _get_chroma_client()
        collection_name = f"ds_{dataset_id}_{column}"[:63]
        try:
            collection = client.get_collection(collection_name)
        except Exception:  # noqa: BLE001
            return []
        results = collection.query(query_texts=[query], n_results=top_k)
        out = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            out.append({"text": doc, "metadata": meta, "distance": dist})
        return out
    except Exception:  # noqa: BLE001
        # Degrade gracefully — the agent will report semantic search as unavailable
        # rather than crashing the whole chat response.
        return []


def has_index(dataset_id: str, column: str) -> bool:
    try:
        client = _get_chroma_client()
        client.get_collection(f"ds_{dataset_id}_{column}"[:63])
        return True
    except Exception:  # noqa: BLE001
        return False
