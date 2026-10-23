from finpulse.preprocess.dedup import cluster, shingles

BASE = " ".join(
    f"Paragraph {i} records that the noticee traded in scrip number {i * 7} on day {i} and the "
    f"Board examined the pattern of orders placed through account {i * 13}."
    for i in range(1, 40)
)


def test_exact_and_near_duplicates_share_a_cluster_distinct_texts_do_not():
    other = (
        "The Insolvency and Bankruptcy Code application was admitted by the Adjudicating Authority "
        "and an interim resolution professional has been appointed to run the corporate debtor. "
    ) * 4
    near = BASE.replace("noticee", "notice", 2)  # two words changed out of hundreds
    groups = cluster({1: BASE, 2: near, 3: BASE, 4: other})
    assert groups[1] == groups[2] == groups[3] == 1
    assert groups[4] == 4


def test_cluster_id_is_the_smallest_member():
    groups = cluster({9: BASE, 5: BASE, 7: BASE})
    assert set(groups.values()) == {5}


def test_short_text_still_has_a_shingle():
    assert shingles("only three words") == {"only three words"}
    assert shingles("") == set()
