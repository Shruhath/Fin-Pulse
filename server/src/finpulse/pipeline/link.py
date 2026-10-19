"""Entity stage: find who each document mentions and link them to the gazetteer.

Two rule sources run on every parsed document:
  1. the parties named in the title (`title-subject`), created as new entities when the
     gazetteer does not know them (unlisted companies and individuals in enforcement orders);
  2. every gazetteer alias found in the body text (`gazetteer-rules`).
Mentions are exact character spans into `clean_text`. Re-running replaces a document's mentions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finpulse.core.offsets import Span, locate_sentence
from finpulse.db.models import Document, Entity, EntityAlias, Mention, Sentence
from finpulse.entities.matcher import AliasMatcher
from finpulse.entities.names import normalise_name, slugify
from finpulse.entities.resolver import Resolver
from finpulse.entities.titles import TitleSubject, title_subjects

from .runs import recorded_run

log = logging.getLogger(__name__)

NER_TITLE = "title-subject"
NER_GAZETTEER = "gazetteer-rules"


@dataclass(slots=True)
class LinkStats:
    documents: int = 0
    mentions: int = 0
    unresolved: int = 0
    created_entities: int = 0


class Linker:
    """Holds the matcher and resolver built from the gazetteer, and extends both as entities appear."""

    def __init__(self, session: Session):
        self.session = session
        self.matcher = AliasMatcher()
        rows = session.execute(select(EntityAlias.alias, EntityAlias.entity_id)).all()
        self.matcher.extend(rows)
        self.resolver = Resolver.from_session(session)
        self.slugs = set(session.scalars(select(Entity.slug)))
        self.created = 0

    def _new_entity(self, subject: TitleSubject) -> Entity:
        base = slugify(subject.name)[:90]
        slug, n = base, 2
        while slug in self.slugs:
            slug, n = f"{base}-{n}", n + 1
        self.slugs.add(slug)
        ent = Entity(slug=slug, canonical_name=subject.name, kind=subject.kind)
        self.session.add(ent)
        self.session.flush()
        norm = normalise_name(subject.name)
        self.session.add(EntityAlias(entity_id=ent.id, alias=subject.name, alias_norm=norm, origin="corpus"))
        self.matcher.add(subject.name, ent.id)
        self.resolver._aliases.setdefault(norm, set()).add(ent.id)
        self.resolver._keys.append(norm)
        self.created += 1
        return ent

    def link(self, doc: Document, sentences: list[Sentence]) -> list[Mention]:
        text = doc.clean_text
        spans = [Span(s.char_start, s.char_end) for s in sentences]

        def sentence_id(start: int) -> int | None:
            idx = locate_sentence(spans, start)
            return sentences[idx].id if idx is not None else None

        taken: list[Span] = []
        mentions: list[Mention] = []

        def add(span: Span, entity_id: int | None, ner: str, method: str, score: float) -> None:
            if any(span.overlaps(t) for t in taken):
                return
            taken.append(span)
            mentions.append(
                Mention(
                    doc_id=doc.id,
                    sentence_id=sentence_id(span.start),
                    entity_id=entity_id,
                    char_start=span.start,
                    char_end=span.end,
                    surface=text[span.start : span.end],
                    ner_model=ner,
                    ner_score=None,
                    link_method=method,
                    link_score=score,
                )
            )

        for subject in title_subjects(doc.title, doc.source_kind):
            res = self.resolver.resolve(subject.name)
            if res.entity_id is None and res.method != "ambiguous":
                entity_id, method, score = self._new_entity(subject).id, "created", 100.0
            else:
                entity_id, method, score = res.entity_id, res.method, res.score
            pattern = r"\s+".join(re.escape(w) for w in subject.name.split())
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                add(Span(m.start(), m.end()), entity_id, NER_TITLE, method, score)

        for match in self.matcher.find(text):
            if len(match.entity_ids) == 1:
                add(match.span, match.entity_ids[0], NER_GAZETTEER, "exact", 100.0)
            else:
                add(match.span, None, NER_GAZETTEER, "ambiguous", 100.0)
        return sorted(mentions, key=lambda m: m.char_start)


def link_document(session: Session, linker: Linker, doc: Document) -> list[Mention]:
    """Replace one document's mentions with freshly linked ones."""
    sentences = list(
        session.scalars(select(Sentence).where(Sentence.doc_id == doc.id).order_by(Sentence.idx))
    )
    session.execute(delete(Mention).where(Mention.doc_id == doc.id))
    mentions = linker.link(doc, sentences)
    session.add_all(mentions)
    session.flush()
    return mentions


def link_pending(session: Session, *, limit: int | None = None, relink: bool = False) -> LinkStats:
    """Link every parsed document that has no mentions yet (or all of them with `relink`)."""
    stmt = select(Document).where(Document.status.in_(("parsed", "analysed"))).order_by(Document.id)
    if not relink:
        stmt = stmt.where(~select(Mention.id).where(Mention.doc_id == Document.id).exists())
    if limit:
        stmt = stmt.limit(limit)
    docs = list(session.scalars(stmt))
    stats = LinkStats()
    if not docs:
        return stats
    with recorded_run(
        session, "entities", model="gazetteer-rules+title-subject", params={"documents": len(docs)}
    ):
        linker = Linker(session)
        for doc in docs:
            mentions = link_document(session, linker, doc)
            stats.documents += 1
            stats.mentions += len(mentions)
            stats.unresolved += sum(m.entity_id is None for m in mentions)
            session.commit()
        stats.created_entities = linker.created
    return stats
