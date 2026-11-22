# Quiz App

Upload a PDF, DOCX or TXT file and get an auto-generated multiple-choice quiz from its content — no AI or API keys, everything runs locally.

## Features

- **Document upload** — PDF (`pypdf`), DOCX (`python-docx`), and plain TXT up to 25 MB
- **Automatic MCQs** — cloze-style questions built from key terms in the document, 4 options each
- **Instant feedback** — correct answers light up green (silent), wrong ones flash red with a sound; a second sound plays at the end if more than 5 answers were wrong
- **Results & review** — final score, review of missed questions, and a "retry missed questions" mode
- **Quiz history** — recent quizzes and last scores are stored in SQLite
- **UI** — minimal dark glassmorphism interface with golden accents, sounds bundled in `static/sounds/`

## Run it (Windows)

```powershell
cd D:\Quiz
.\.venv\Scripts\python.exe app.py
```

Then open **http://127.0.0.1:5000** in your browser.

First-time setup on a fresh machine:

```powershell
cd D:\Quiz
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## How questions are generated

Text is extracted, split into sentences, and factual-looking sentences are turned into fill-in-the-blank questions. The blanked term becomes the answer, and three same-length terms from elsewhere in the document become the distractors. About 12 questions are generated per document (minimum 3).

**Limits:** scanned/image-only PDFs (no selectable text) aren't supported yet, and question quality is mechanical — it works best on notes and textbook-style documents.

## Project layout

```
app.py                 Flask routes, SQLite storage
quizgen.py             Text extraction + MCQ generation
templates/             index.html, quiz.html
static/css/style.css   Dark glassmorphism theme
static/js/quiz.js      Quiz flow, scoring, sound playback
static/sounds/         wrong.mp3, 2wrong.mp3
```
