import json

from llm_validation import extract_json_from_text, validate_and_normalize, ValidationError


def test_validate_and_normalize_valid():
    payload = {
        "Strategic": ["Risk A", "Risk B"],
        "Financial": ["Fin Risk"],
        "Legal": [],
        "Operational": ["Op Risk 1", "Op Risk 2", "Op Risk 3", "Op Risk 4"],
        "Technology": ["Tech Risk"]
    }
    out = validate_and_normalize(payload, top_n=3)
    assert len(out["Operational"]) == 3
    assert out["Strategic"][0] == "Risk A"


def test_extract_json_from_messy_text():
    text = "Model says: 1. See below. {\"Strategic\": [\"S1\"], \"Financial\": [], \"Legal\": [], \"Operational\": [], \"Technology\": []} end"
    data = extract_json_from_text(text)
    assert data["Strategic"] == ["S1"]


def test_invalid_schema_raises():
    bad = {"Strategic": ["a"], "Financial": []}  # missing keys
    try:
        validate_and_normalize(bad)
        assert False, "Expected ValidationError"
    except Exception as e:
        assert isinstance(e, Exception)
