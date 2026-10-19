import pytest
from sqlalchemy import func, select

from finpulse.db.models import Entity, EntityAlias
from finpulse.entities.gazetteer import seed_gazetteer, smart_title

pytestmark = pytest.mark.db


@pytest.mark.parametrize(
    ("raw", "nice"),
    [
        ("YES BANK LIMITED", "Yes Bank Limited"),
        ("HDFC BANK LIMITED", "HDFC Bank Limited"),
        ("LARSEN AND TOUBRO LIMITED", "Larsen and Toubro Limited"),
        ("20 MICRONS LTD", "20 Microns Ltd."),
        ("Tata Motors Limited", "Tata Motors Limited"),
    ],
)
def test_smart_title(raw, nice):
    assert smart_title(raw) == nice


def _benchmarks(root):
    nse = root / "nse-india-security-master" / "data"
    nse.mkdir(parents=True)
    (nse / "nse_security_master.csv").write_text(
        "nse_symbol,isin,company_name,listing_date,active_flag\n"
        "YESBANK,INE528G01035,YES BANK LIMITED,2005-07-12,True\n"
        "TCS,INE467B01029,TATA CONSULTANCY SERVICES LIMITED,2004-08-25,True\n"
    )
    (root / "sentfin").mkdir()
    (root / "sentfin" / "entity_list_comprehensive.csv").write_text(
        ",Symbol,Entity\n"
        '0,YESBANK,"Yes Bank Ltd, Yes Bank, YESBANK"\n'
        '1,SINTEX,"Sintex Industries Ltd., Sintex, SINTEX"\n'
    )


def test_seed_merges_nse_and_sentfin_and_is_repeatable(db, tmp_path):
    _benchmarks(tmp_path)
    first = seed_gazetteer(db, tmp_path)
    assert (first.from_nse, first.from_sentfin) == (2, 1)

    yes = db.scalar(select(Entity).where(Entity.nse_symbol == "YESBANK"))
    assert yes.canonical_name == "Yes Bank Limited" and yes.kind == "bank" and yes.isin == "INE528G01035"
    aliases = {
        a.alias_norm: a.origin for a in db.scalars(select(EntityAlias).where(EntityAlias.entity_id == yes.id))
    }
    assert aliases == {"yes bank": "nse", "yesbank": "sentfin"}  # duplicates collapse on the normalised form

    sintex = db.scalar(select(Entity).where(Entity.nse_symbol == "SINTEX"))
    assert sintex.canonical_name == "Sintex Industries Ltd."

    before = db.scalar(select(func.count()).select_from(EntityAlias))
    again = seed_gazetteer(db, tmp_path)
    assert again.entities == 0 and again.aliases == 0
    assert db.scalar(select(func.count()).select_from(EntityAlias)) == before


def test_missing_files_are_reported_not_fatal(db, tmp_path):
    stats = seed_gazetteer(db, tmp_path)
    assert stats.entities == 0
