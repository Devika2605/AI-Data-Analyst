"""
utils.py — Small shared helpers: in-memory caching, a restricted Pandas
operation executor (groupby/agg only — never arbitrary eval), and structured
logging setup.
"""
import hashlib
import json
import logging
import sys
import time

from config import settings

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)r}'
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


logger = logging.getLogger("ai_data_analyst")


def log_event(event: str, **fields):
    safe_fields = {k: v for k, v in fields.items() if k not in ("api_key", "secret")}
    logger.info(json.dumps({"event": event, **safe_fields}, default=str))


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_TTL_SECONDS = 300


def cache_key(*parts) -> str:
    raw = "||".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_get(key: str):
    if not settings.CACHE_ENABLED:
        return None
    item = _CACHE.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return value


def cache_set(key: str, value):
    if settings.CACHE_ENABLED:
        _CACHE[key] = (time.time(), value)


def cache_invalidate_prefix(prefix: str):
    for k in list(_CACHE.keys()):
        if k.startswith(prefix):
            _CACHE.pop(k, None)


# ---------------------------------------------------------------------------
# Restricted, controlled Pandas operation representation
# ---------------------------------------------------------------------------
# Rather than eval-ing arbitrary LLM-generated Python, we represent an
# analysis as a small structured "operation" and execute it with a fixed,
# whitelisted set of Pandas calls. This removes the injection surface
# entirely while still letting the agent express groupby/agg/sort/filter/topn.

ALLOWED_AGGS = {"sum", "mean", "count", "median", "min", "max", "std", "nunique"}


def run_pandas_operation(df, op: dict):
    """
    op = {
      "filter": {"column": "region", "op": "==", "value": "South"} | None,
      "groupby": ["region"] | None,
      "agg": {"revenue": "sum"} | None,
      "sort_by": "revenue" | None,
      "ascending": False,
      "top_n": 5 | None,
    }
    Returns a pandas DataFrame. Raises ValueError on invalid/unsafe operations.
    """
    import pandas as pd

    work = df

    flt = op.get("filter")
    if flt:
        col, cmp, val = flt.get("column"), flt.get("op"), flt.get("value")
        if col not in work.columns:
            raise ValueError(f"Unknown column in filter: {col}")
        if cmp not in ("==", "!=", ">", "<", ">=", "<="):
            raise ValueError(f"Unsupported filter operator: {cmp}")
        series = work[col]
        if cmp == "==":
            work = work[series == val]
        elif cmp == "!=":
            work = work[series != val]
        elif cmp == ">":
            work = work[pd.to_numeric(series, errors="coerce") > float(val)]
        elif cmp == "<":
            work = work[pd.to_numeric(series, errors="coerce") < float(val)]
        elif cmp == ">=":
            work = work[pd.to_numeric(series, errors="coerce") >= float(val)]
        elif cmp == "<=":
            work = work[pd.to_numeric(series, errors="coerce") <= float(val)]

    groupby = op.get("groupby")
    agg = op.get("agg")
    if groupby:
        for c in groupby:
            if c not in work.columns:
                raise ValueError(f"Unknown groupby column: {c}")
        if agg:
            for c, fn in agg.items():
                if c not in work.columns:
                    raise ValueError(f"Unknown agg column: {c}")
                if fn not in ALLOWED_AGGS:
                    raise ValueError(f"Unsupported aggregation function: {fn}")
            work = work.groupby(groupby, dropna=False).agg(agg).reset_index()
        else:
            work = work.groupby(groupby, dropna=False).size().reset_index(name="count")

    sort_by = op.get("sort_by")
    if sort_by:
        if sort_by not in work.columns:
            raise ValueError(f"Unknown sort_by column: {sort_by}")
        work = work.sort_values(sort_by, ascending=op.get("ascending", False))

    top_n = op.get("top_n")
    if top_n:
        work = work.head(int(top_n))

    return work.reset_index(drop=True)
