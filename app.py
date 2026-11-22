"""PDF/DOCX/TXT to multiple-choice quiz app."""

import json
import sqlite3
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

import quizgen

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "quiz.db"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_CONTENT_MB = 25

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_MB * 1024 * 1024


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                question_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                options TEXT NOT NULL,
                answer_index INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )


def _recent_quizzes():
    with get_db() as db:
        return db.execute(
            """
            SELECT q.id, q.filename, q.question_count, q.created_at, a.score, a.total
            FROM quizzes q
            LEFT JOIN attempts a ON a.id = (
                SELECT id FROM attempts WHERE quiz_id = q.id ORDER BY id DESC LIMIT 1
            )
            ORDER BY q.id DESC
            LIMIT 8
            """
        ).fetchall()


def _save_quiz(filename: str, questions: list[quizgen.Question]) -> int:
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO quizzes (filename, question_count) VALUES (?, ?)",
            (filename, len(questions)),
        )
        quiz_id = cursor.lastrowid
        db.executemany(
            "INSERT INTO questions (quiz_id, position, prompt, options, answer_index) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (quiz_id, position, q.prompt, json.dumps(q.options), q.answer_index)
                for position, q in enumerate(questions)
            ],
        )
    return quiz_id


def _load_quiz(quiz_id: int):
    with get_db() as db:
        quiz_row = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        if quiz_row is None:
            return None
        rows = db.execute(
            "SELECT prompt, options, answer_index FROM questions "
            "WHERE quiz_id = ? ORDER BY position",
            (quiz_id,),
        ).fetchall()
    questions = [
        {"prompt": r["prompt"], "options": json.loads(r["options"]), "answerIndex": r["answer_index"]}
        for r in rows
    ]
    return {"id": quiz_row["id"], "filename": quiz_row["filename"], "questions": questions}


def _index_page(error: str | None = None, status: int = 200):
    return (
        render_template("index.html", quizzes=_recent_quizzes(), error=error, max_mb=MAX_CONTENT_MB),
        status,
    )


@app.get("/")
def index():
    return _index_page()


@app.post("/upload")
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        return _index_page("Please choose a PDF, DOCX or TXT file to upload.", 400)

    filename = Path(file.filename).name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return _index_page("Only .pdf, .docx and .txt files are supported.", 400)

    try:
        text = quizgen.extract_text(filename, file.read())
        questions = quizgen.generate_questions(text)
    except quizgen.UnsupportedFileType:
        return _index_page("Only .pdf, .docx and .txt files are supported.", 400)
    except quizgen.NotEnoughContent as exc:
        return _index_page(str(exc), 400)
    except Exception:
        return _index_page(
            "Couldn't read that file. If it's an older .doc file, save it as .docx first.", 400
        )

    quiz_id = _save_quiz(filename, questions)
    return redirect(url_for("quiz_view", quiz_id=quiz_id))


@app.get("/quiz/<int:quiz_id>")
def quiz_view(quiz_id: int):
    quiz = _load_quiz(quiz_id)
    if quiz is None:
        abort(404)
    return render_template("quiz.html", quiz=quiz)


@app.post("/api/quiz/<int:quiz_id>/attempt")
def save_attempt(quiz_id: int):
    quiz = _load_quiz(quiz_id)
    if quiz is None:
        abort(404)
    payload = request.get_json(silent=True) or {}
    score = payload.get("score")
    total = payload.get("total")
    valid = (
        isinstance(score, int)
        and isinstance(total, int)
        and 1 <= total <= len(quiz["questions"])
        and 0 <= score <= total
    )
    if not valid:
        return jsonify({"ok": False, "error": "Invalid score."}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO attempts (quiz_id, score, total) VALUES (?, ?, ?)",
            (quiz_id, score, total),
        )
    return jsonify({"ok": True})


@app.errorhandler(413)
def file_too_large(_error):
    return _index_page(f"File is too large. The maximum size is {MAX_CONTENT_MB} MB.", 413)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
