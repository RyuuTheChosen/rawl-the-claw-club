from rawl.engine.field_validator import FieldValidator, CONSECUTIVE_THRESHOLD, TOTAL_THRESHOLD


def _make_info(p1_fields=None, p2_fields=None):
    """Helper to create info dict with specified fields."""
    info = {
        "P1": p1_fields or {},
        "P2": p2_fields or {},
    }
    return info


class TestFieldValidator:
    def test_no_errors_when_all_present(self):
        fv = FieldValidator(
            match_id="test",
            required_fields=["health", "round"],
        )
        info = _make_info(
            {"health": 100, "round": 1},
            {"health": 100, "round": 1},
        )
        errors = fv.check_frame(info)
        assert errors == []

    def test_consecutive_threshold(self):
        fv = FieldValidator(
            match_id="test",
            required_fields=["health"],
        )
        info_missing = _make_info({}, {"health": 100})

        # Should not error until threshold
        for _ in range(CONSECUTIVE_THRESHOLD - 1):
            errors = fv.check_frame(info_missing)
            assert errors == []

        # Should error at threshold
        errors = fv.check_frame(info_missing)
        assert len(errors) > 0
        assert "consecutive" in errors[0]

    def test_consecutive_resets_on_reappear(self):
        fv = FieldValidator(
            match_id="test",
            required_fields=["health"],
        )
        info_missing = _make_info({}, {"health": 100})
        info_present = _make_info({"health": 50}, {"health": 100})

        # Miss 200 frames
        for _ in range(200):
            fv.check_frame(info_missing)

        # Field reappears — resets consecutive
        fv.check_frame(info_present)

        # Miss another 200 (total=401 but consecutive only 200)
        for _ in range(200):
            errors = fv.check_frame(info_missing)

        # Should not have consecutive error (200 < 300)
        # But should not have total error yet either (401 < 900)
        assert all("consecutive" not in e for e in errors)

    def test_total_threshold_never_resets(self):
        fv = FieldValidator(
            match_id="test",
            required_fields=["health"],
        )
        info_missing = _make_info({}, {"health": 100})
        info_present = _make_info({"health": 50}, {"health": 100})

        # Alternate: miss 200, present 1, miss 200, present 1, etc.
        total_missing = 0
        for batch in range(5):
            for _ in range(200):
                total_missing += 1
                errors = fv.check_frame(info_missing)
                if total_missing >= TOTAL_THRESHOLD:
                    assert any("total" in e for e in errors)
            fv.check_frame(info_present)

    def test_get_status(self):
        fv = FieldValidator(
            match_id="test",
            required_fields=["health", "round"],
        )
        info = _make_info({"health": 100}, {"health": 100, "round": 1})
        fv.check_frame(info)

        status = fv.get_status()
        assert "P1" in status
        assert "health" in status["P1"]
        assert status["P1"]["health"]["consecutive_missing"] == 0
        assert status["P1"]["round"]["consecutive_missing"] == 1

    def test_multiple_fields_tracked_independently(self):
        fv = FieldValidator(
            match_id="test",
            required_fields=["health", "round", "timer"],
        )
        # Only health present
        info = _make_info(
            {"health": 100},
            {"health": 100},
        )
        fv.check_frame(info)

        status = fv.get_status()
        assert status["P1"]["health"]["consecutive_missing"] == 0
        assert status["P1"]["round"]["consecutive_missing"] == 1
        assert status["P1"]["timer"]["consecutive_missing"] == 1
