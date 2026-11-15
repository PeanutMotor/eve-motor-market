"""Parallel work per character (emm866) - pure, testable without network.

User 08.11.2026: "das laden vom Portfolio und der generelle erststart
von Moma dauert lange". The portfolio refresh walked all characters
STRICTLY one after another (transactions, journal, orders, assets per
character over ESI) - with 12 linked characters that is 12x waiting.
ESI handles a handful of concurrent requests fine, and the local
database runs WAL with a busy timeout (store._conn), so per-character
work may overlap safely.
"""
from concurrent.futures import ThreadPoolExecutor


def je_charakter(cids, fn, max_parallel=4):
    """Run fn(cid) for every cid, up to `max_parallel` at a time.

    Returns [(cid, result, error)] in INPUT order; `error` is None on
    success, otherwise str(exception) - one broken character must never
    abort the others (before this, a single 403 killed the whole
    portfolio refresh).
    """
    cids = list(cids)
    if not cids:
        return []

    def _lauf(cid):
        try:
            return (cid, fn(cid), None)
        except Exception as ex:
            return (cid, None, str(ex)[:200])

    with ThreadPoolExecutor(
            max_workers=max(1, min(int(max_parallel), len(cids)))) as tp:
        return list(tp.map(_lauf, cids))
