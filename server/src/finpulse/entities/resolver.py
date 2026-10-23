"""Entity linking: surface string -> gazetteer entity, or honestly unresolved.

Order: normalised alias match (lower-case, '&'='and', legal suffixes dropped), then a fuzzy
match with `rapidfuzz`. The plan names token-set ratio >= 92, but that scorer treats a subset
as a perfect match ("Yes Bank" vs "Yes Bank of America" scores 100), so token-sort ratio is
used instead, which penalises the extra words. Ambiguous aliases are left unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import EntityAlias

from .names import normalise_name

FUZZY_CUTOFF = 92.0


@dataclass(frozen=True, slots=True)
class Resolution:
    entity_id: int | None
    method: str  # normalised | fuzzy | ambiguous | unresolved
    score: float


class Resolver:
    def __init__(self, aliases: dict[str, set[int]]):
        self._aliases = aliases
        self._keys = list(aliases)

    @classmethod
    def from_session(cls, session: Session) -> Resolver:
        aliases: dict[str, set[int]] = {}
        for norm, entity_id in session.execute(select(EntityAlias.alias_norm, EntityAlias.entity_id)):
            aliases.setdefault(norm, set()).add(entity_id)
        return cls(aliases)

    def resolve(self, surface: str, *, fuzzy: bool = True) -> Resolution:
        norm = normalise_name(surface)
        if not norm:
            return Resolution(None, "unresolved", 0.0)
        ids = self._aliases.get(norm)
        if ids:
            if len(ids) == 1:
                return Resolution(next(iter(ids)), "normalised", 100.0)
            return Resolution(None, "ambiguous", 100.0)
        if fuzzy and len(norm) >= 5:
            hit = process.extractOne(
                norm, self._keys, scorer=fuzz.token_sort_ratio, score_cutoff=FUZZY_CUTOFF
            )
            if hit is not None:
                key, score, _ = hit
                ids = self._aliases[key]
                if len(ids) == 1:
                    return Resolution(next(iter(ids)), "fuzzy", float(score))
                return Resolution(None, "ambiguous", float(score))
        return Resolution(None, "unresolved", 0.0)
