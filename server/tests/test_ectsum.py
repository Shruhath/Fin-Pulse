import json

import numpy as np
import pytest

from finpulse.eval.ectsum import evaluate_ectsum, load_ectsum
from finpulse.llm.client import LlmError, Reply

CALL = [
    "Revenue rose 5 percent to 120 million dollars in the quarter driven by strong demand across regions.",
    "Operating margin expanded by 80 basis points as the company controlled costs throughout the period.",
    "We expect full year revenue between 480 and 500 million dollars given the current order backlog.",
    "The board approved a quarterly dividend of 12 cents per share payable next month to holders of record.",
    "Thank you all for joining us today and we look forward to speaking with you again next quarter.",
]


@pytest.fixture
def root(tmp_path):
    base = tmp_path / "ectsum" / "data" / "final" / "test"
    (base / "ects").mkdir(parents=True)
    (base / "gt_summaries").mkdir()
    for name in ("AAA_q1_2021", "BBB_q2_2021", "CCC_q3_2021"):
        (base / "ects" / f"{name}.txt").write_text("\n".join(CALL))
        (base / "gt_summaries" / f"{name}.txt").write_text(
            "q1 revenue rose 5 percent to 120 million.\nsees fy revenue 480 to 500 million."
        )
    (base / "ects" / "NOREF_q1_2021.txt").write_text("\n".join(CALL))  # no reference: ignored
    return tmp_path


class SummaryLlm:
    def __init__(self, text="Revenue rose 5 percent to 120 million dollars."):
        self.text, self.prompts = text, []

    def chat(self, model, system, user, *, schema=None, num_predict=1024):
        self.prompts.append(user)
        body = {"claims": [{"text": self.text, "sources": [0]}]}
        return Reply(json.dumps(body), model, 500, 40, 2.0)


class Judge:
    name = "fake"

    def predict(self, pairs):
        # entails when the premise carries the claim's numbers, otherwise contradicts when numbers differ
        out = []
        for premise, claim in pairs:
            nums = {w for w in claim.replace(",", "").split() if w.isdigit()}
            out.append((0.95, 0.03, 0.02) if nums and all(n in premise for n in nums) else (0.05, 0.1, 0.85))
        return np.array(out, dtype=np.float32)


def test_sampling_is_seeded_skips_transcripts_without_a_reference_and_keeps_bullets(root):
    a = load_ectsum(root, n=2, seed=7)
    assert [t.name for t in a] == [t.name for t in load_ectsum(root, n=2, seed=7)] and len(a) == 2
    assert all(t.name != "NOREF_q1_2021" for t in load_ectsum(root, n=10))
    t = a[0]
    assert t.sentences == CALL and t.reference.startswith("q1 revenue rose 5 percent")


def test_the_llm_and_both_baselines_are_scored_against_the_reference(root):
    transcripts = load_ectsum(root, n=3)
    llm = SummaryLlm()
    scores = evaluate_ectsum(llm, "llama", transcripts, Judge())
    assert set(scores) == {"llm", "lead3", "lexrank"}
    assert scores["llm"]["n"] == scores["lead3"]["n"] == scores["lexrank"]["n"] == 3.0
    assert scores["llm"]["rougeL"] > scores["lead3"]["rougeL"]  # the claim matches the reference bullet
    assert scores["llm"]["attribution"] == 1.0 and scores["llm"]["unsupported"] == 0.0
    assert "[S0] Revenue rose 5 percent" in llm.prompts[0]


def test_a_claim_with_a_wrong_number_is_counted_contradicted_not_attributed(root):
    scores = evaluate_ectsum(
        SummaryLlm("Revenue rose 7 percent to 999 million dollars."), "llama", load_ectsum(root, n=1), Judge()
    )
    assert (
        scores["llm"]["attribution"] == 0.0
        and scores["llm"]["contradicted"] + scores["llm"]["unsupported"] == 1.0
    )


def test_unusable_answers_are_skipped_and_counted_without_stopping_the_run(root):
    class Broken:
        def chat(self, *a, **k):
            return Reply("not json", "m", 1, 1, 0.1)

    scores = evaluate_ectsum(Broken(), "llama", load_ectsum(root, n=2), None)
    assert scores["llm"]["skipped"] == 2.0 and scores["llm"]["n"] == 0.0 and scores["lead3"]["n"] == 2.0
    assert "attribution" not in scores["llm"]
    assert LlmError  # the broken answers surface as LlmError inside, which the evaluation absorbs
