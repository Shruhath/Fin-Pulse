"""Near-duplicate clustering with MinHash LSH (Jaccard over word 5-shingles)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from datasketch import MinHash, MinHashLSH

_WORD = re.compile(r"\w+")


def shingles(text: str, k: int = 5) -> set[str]:
    words = _WORD.findall(text.lower())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def signature(text: str, num_perm: int = 128) -> MinHash:
    sig = MinHash(num_perm=num_perm)
    for sh in shingles(text):
        sig.update(sh.encode("utf-8"))
    return sig


def cluster(items: Mapping[int, str] | Iterable[tuple[int, str]], threshold: float = 0.85) -> dict[int, int]:
    """Map each key to the smallest key in its near-duplicate group (itself when unique)."""
    pairs = list(items.items() if isinstance(items, Mapping) else items)
    sigs = {key: signature(text) for key, text in pairs}
    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    parent = {key: key for key in sigs}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for key, sig in sigs.items():
        for other in lsh.query(sig):
            a, b = find(key), find(other)
            if a != b:
                parent[max(a, b)] = min(a, b)
        lsh.insert(key, sig)
    return {key: find(key) for key in sigs}
