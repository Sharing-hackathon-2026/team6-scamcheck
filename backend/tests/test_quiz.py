import json

import pytest

from app.services.quiz import load_quiz, validate_quiz


def test_quiz_has_exactly_ten_balanced_curated_questions():
    quiz = load_quiz()
    assert len(quiz) == 10
    assert sum(item["is_scam"] for item in quiz) == 5
    assert len({item["id"] for item in quiz}) == 10
    assert all(item["explanation"] and item["tip"] for item in quiz)


def test_quiz_route_is_static_and_typed(client, mock_gemini_text):
    response = client.get("/api/quiz")
    assert response.status_code == 200
    assert len(response.get_json()["questions"]) == 10
    assert mock_gemini_text["calls"] == 0


def test_quiz_validator_rejects_bad_length_duplicate_and_label():
    quiz = load_quiz()
    with pytest.raises(ValueError):
        validate_quiz(quiz[:9])
    duplicate = json.loads(json.dumps(quiz))
    duplicate[1]["id"] = duplicate[0]["id"]
    with pytest.raises(ValueError):
        validate_quiz(duplicate)
    bad = json.loads(json.dumps(quiz))
    bad[0]["is_scam"] = "yes"
    with pytest.raises(ValueError):
        validate_quiz(bad)
