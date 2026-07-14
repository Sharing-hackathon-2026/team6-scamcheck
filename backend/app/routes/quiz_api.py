"""GET /api/quiz — 10 câu luyện tập tĩnh."""
from flask import Blueprint, jsonify

from ..services.quiz import load_quiz

bp = Blueprint("quiz", __name__)


@bp.get("/api/quiz")
def quiz():
    return jsonify({"questions": load_quiz()})
