"""MOCKED: the research tools' relevance/conflict thresholds, with a stand-in store (no database)."""

from researchmind.tools import MIN_CONFLICT_SCORE, ResearchTools


class StubStore:
    """Answers the three queries compare_claims makes, with canned rows."""

    def __init__(self, relations):
        self.relations = relations

    def query(self, cypher, params=None, read_only=False):
        if "vector.queryNodes" in cypher:
            return [{"id": "s1", "sim": 0.8}, {"id": "s2", "sim": 0.7}]
        if "UNWIND $ids AS sid MATCH (p:Paper)" in cypher:
            return [{"id": "s1", "type": "Finding", "text": "A works", "polarity": 1, "paper_id": "p1", "paper_title": "P1",
                     "year": 2024, "chunk_id": "c1", "page": 1},
                    {"id": "s2", "type": "Finding", "text": "A fails", "polarity": -1, "paper_id": "p2", "paper_title": "P2",
                     "year": 2024, "chunk_id": "c2", "page": 1}]
        return self.relations


def test_weak_contradictions_are_reported_as_related_not_conflicts():
    rel = lambda score: {"relation": "CONTRADICTS", "score": score, "statement_a": "A works", "paper_a": "P1", "chunk_a": "c1",  # noqa: E731
                         "statement_b": "A fails", "paper_b": "P2", "chunk_b": "c2"}
    out = ResearchTools(StubStore([rel(0.83), rel(0.55)])).compare_claims("A")
    assert [c["score"] for c in out["contradictions"]] == [0.83]
    assert [c["score"] for c in out["related_statements"]] == [0.55]
    assert MIN_CONFLICT_SCORE == 0.7
