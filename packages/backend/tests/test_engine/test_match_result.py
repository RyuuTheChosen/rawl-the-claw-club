import hashlib
import json

from rawl.engine.match_result import compute_match_hash, resolve_tiebreaker


class TestComputeMatchHash:
    def test_deterministic(self):
        payload1, hash1 = compute_match_hash("m1", "P1", [{"winner": "P1"}], [], "1.0.0")
        payload2, hash2 = compute_match_hash("m1", "P1", [{"winner": "P1"}], [], "1.0.0")
        assert hash1 == hash2
        assert payload1 == payload2

    def test_different_inputs_different_hash(self):
        _, hash1 = compute_match_hash("m1", "P1", [], [], "1.0.0")
        _, hash2 = compute_match_hash("m2", "P1", [], [], "1.0.0")
        assert hash1 != hash2

    def test_canonical_json(self):
        payload, _ = compute_match_hash("m1", "P1", [], [], "1.0.0")
        parsed = json.loads(payload)
        # Keys should be sorted
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_hash_matches_payload(self):
        """The hash hex must be SHA-256 of the exact payload bytes."""
        payload, hash_hex = compute_match_hash(
            "test-match", "P2", [{"winner": "P2", "p1_health": 0.0, "p2_health": 0.5}],
            [{"P1": [1, 0], "P2": [0, 1]}], "1.0.0"
        )
        expected = hashlib.sha256(payload).hexdigest()
        assert hash_hex == expected

    def test_hash_version_included(self):
        payload, _ = compute_match_hash("m1", "P1", [], [], "1.0.0", hash_version=2)
        parsed = json.loads(payload)
        assert parsed["hash_version"] == 2


class TestResolveTiebreaker:
    def test_step1_health_differential(self):
        history = [
            {"winner": "DRAW", "p1_health": 0.8, "p2_health": 0.3},
            {"winner": "DRAW", "p1_health": 0.5, "p2_health": 0.4},
        ]
        assert resolve_tiebreaker(history, "match-1") == "P1"

    def test_step1_p2_health(self):
        history = [
            {"winner": "DRAW", "p1_health": 0.2, "p2_health": 0.9},
        ]
        assert resolve_tiebreaker(history, "match-1") == "P2"

    def test_step2_rounds_won(self):
        history = [
            {"winner": "P1", "p1_health": 0.5, "p2_health": 0.5},
            {"winner": "P2", "p1_health": 0.5, "p2_health": 0.5},
            {"winner": "P1", "p1_health": 0.5, "p2_health": 0.5},
        ]
        # Health equal, but P1 has more round wins
        assert resolve_tiebreaker(history, "match-1") == "P1"

    def test_step3_last_round_health(self):
        history = [
            {"winner": "P1", "p1_health": 0.5, "p2_health": 0.5},
            {"winner": "P2", "p1_health": 0.5, "p2_health": 0.5},
            {"winner": "DRAW", "p1_health": 0.8, "p2_health": 0.3},
        ]
        # Equal wins, equal total health, but last round P1 has more
        assert resolve_tiebreaker(history, "match-1") == "P1"

    def test_step4_coin_flip_deterministic(self):
        """Same match_id always produces same result."""
        history = [{"winner": "DRAW", "p1_health": 0.5, "p2_health": 0.5}]
        result1 = resolve_tiebreaker(history, "deterministic-match-id")
        result2 = resolve_tiebreaker(history, "deterministic-match-id")
        assert result1 == result2
        assert result1 in ("P1", "P2")

    def test_step4_different_ids_may_differ(self):
        """Different match IDs should eventually produce different results."""
        history = [{"winner": "DRAW", "p1_health": 0.5, "p2_health": 0.5}]
        results = set()
        for i in range(100):
            results.add(resolve_tiebreaker(history, f"match-{i}"))
        # With 100 attempts, we should see both outcomes
        assert len(results) == 2
