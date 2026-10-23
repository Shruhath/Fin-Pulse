"""Seed the entity gazetteer from the public NSE security master and the SEntFiN alias list.

Both come from the layer 1 download. SEntFiN aliases are stored with origin 'sentfin' and must
stay out of any published export (its licence asks for citation, not re-hosting).
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from finpulse.db.models import Entity, EntityAlias

from .names import normalise_name, slugify

log = logging.getLogger(__name__)

NSE_MASTER = Path("nse-india-security-master/data/nse_security_master.csv")
SENTFIN_ENTITIES = Path("sentfin/entity_list_comprehensive.csv")

_SMALL = {"of", "and", "the", "for", "in", "on", "at", "to", "&"}
_KEEP_UPPER = frozenset(
    (
        "ii iii iv llp icici idfc ifci itc ioc ntpc ongc sbi lic uco rbl dcb hcl hpcl bpcl jsw mrf nmdc pnb "
        "pfc rec sjvn nhpc tvs irb irctc irfc hal bel dlf gmr gsfc gnfc ifb iifl kec kpit ltimindtree "
        "bse nse gail sail bhel tcs hdfc"
    ).split()
)


def smart_title(name: str) -> str:
    """'YES BANK LIMITED' -> 'Yes Bank Limited'; short consonant-only tokens stay upper-case (HDFC, NTPC)."""
    out: list[str] = []
    for i, word in enumerate(name.split()):
        low = word.lower()
        letters = re.sub(r"[^a-z]", "", low)
        if any(c.islower() for c in word):
            out.append(word)  # already mixed case: trust it
        elif low in _SMALL and i > 0:
            out.append(low)
        elif low == "ltd":
            out.append("Ltd.")
        elif (letters and len(letters) <= 5 and not re.search(r"[aeiou]", letters)) or low in _KEEP_UPPER:
            out.append(word)
        else:
            out.append(word.capitalize())
    return " ".join(out)


# SEntFiN also labels groups of stocks and institutions ("hotel companies", "Supreme Court", "Stock
# exchanges"). Only names that read like a company are kept, or the matcher floods with false mentions.
_COMPANY_LIKE = re.compile(
    r"(?:\b(?:ltd|limited|co|company|corporation|corp|inc|industries|enterprises|holdings|finance)\b\.?"
    r"(?:\s*-\s*old)?\s*$)|\bbank\b",
    re.IGNORECASE,
)


def looks_like_company(name: str) -> bool:
    return bool(_COMPANY_LIKE.search(name.strip()))


def clean_sentfin_name(name: str) -> str:
    return re.sub(r"\s*-\s*old\s*$", "", name.strip(), flags=re.IGNORECASE)


@dataclass(slots=True)
class SeedStats:
    entities: int = 0
    aliases: int = 0
    from_nse: int = 0
    from_sentfin: int = 0
    skipped: int = 0  # SEntFiN rows that are not companies


def _unique_slug(session: Session, base: str, taken: set[str]) -> str:
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def seed_gazetteer(session: Session, benchmark_dir: Path) -> SeedStats:
    """Create entities and aliases that do not exist yet. Safe to run again."""
    stats = SeedStats()
    by_symbol: dict[str, Entity] = {e.nse_symbol: e for e in session.scalars(select(Entity)) if e.nse_symbol}
    taken = set(session.scalars(select(Entity.slug)))
    have_alias = {(a.entity_id, a.alias_norm) for a in session.scalars(select(EntityAlias))}

    def add_alias(entity: Entity, alias: str, origin: str) -> None:
        norm = normalise_name(alias)
        if not norm or (entity.id, norm) in have_alias:
            return
        have_alias.add((entity.id, norm))
        session.add(EntityAlias(entity_id=entity.id, alias=alias.strip(), alias_norm=norm, origin=origin))
        stats.aliases += 1

    nse_path = benchmark_dir / NSE_MASTER
    if nse_path.is_file():
        for row in _read_csv(nse_path):
            symbol = row["nse_symbol"].strip()
            if not symbol or symbol in by_symbol:
                continue
            name = smart_title(row["company_name"].strip())
            ent = Entity(
                slug=_unique_slug(session, slugify(name), taken),
                canonical_name=name,
                nse_symbol=symbol,
                isin=row.get("isin") or None,
                kind="bank" if "bank" in name.lower() else "company",
            )
            session.add(ent)
            session.flush()
            by_symbol[symbol] = ent
            add_alias(ent, name, "nse")
            add_alias(ent, row["company_name"], "nse")
            stats.entities += 1
            stats.from_nse += 1
    else:
        log.warning("NSE security master not found at %s", nse_path)

    sf_path = benchmark_dir / SENTFIN_ENTITIES
    if sf_path.is_file():
        for row in _read_csv(sf_path):
            symbol = (row.get("Symbol") or "").strip()
            aliases = [a.strip() for a in (row.get("Entity") or "").split(",") if a.strip()]
            if not symbol or not aliases:
                continue
            ent = by_symbol.get(symbol)
            if ent is None:
                if not looks_like_company(aliases[0]):
                    stats.skipped += 1
                    continue
                name = clean_sentfin_name(aliases[0])
                ent = Entity(
                    slug=_unique_slug(session, slugify(name), taken),
                    canonical_name=name,
                    nse_symbol=symbol,
                    kind="bank" if "bank" in name.lower() else "company",
                )
                session.add(ent)
                session.flush()
                by_symbol[symbol] = ent
                stats.entities += 1
                stats.from_sentfin += 1
            for alias in aliases:
                add_alias(ent, alias, "sentfin")
    else:
        log.warning("SEntFiN entity list not found at %s", sf_path)

    session.flush()
    return stats
