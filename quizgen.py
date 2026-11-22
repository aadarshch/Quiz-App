"""Extract text from uploaded documents and generate cloze multiple-choice questions."""

from __future__ import annotations

import io
import random
import re
from collections import Counter
from dataclasses import dataclass


class UnsupportedFileType(ValueError):
    pass


class NotEnoughContent(ValueError):
    pass


@dataclass
class Question:
    prompt: str
    options: list[str]
    answer_index: int


_STOPWORDS = set(
    "a an the and or but if then else while when where which who whom whose what why "
    "how of in on at to from by with without for about into over under between among "
    "during before after above below up down out off again further once here there all "
    "any both each few more most other some such no nor not only own same so than too "
    "very can will just should now also may might must shall could would this that these "
    "those it its itself they them their theirs he him his she her hers we us our ours "
    "you your yours i me my mine is are was were be been being have has had having do "
    "does did doing done get got make made say said one two three first second many much "
    "including include included use used using within upon per often however therefore "
    "thus although though because since across along around according example examples "
    "through against toward towards onto throughout whether without alongside "
    "etc well like even still yet ever never always sometimes usually mainly mostly "
    "part parts way ways number numbers case cases time times new different another "
    "every either neither enough less least high low large small long short able "
    "available possible important called known based various several likely".split()
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def extract_text(filename: str, data: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == "docx":
        import docx

        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    if ext == "txt":
        return data.decode("utf-8", errors="ignore")
    raise UnsupportedFileType(f"Unsupported file type: .{ext}")


def _clean(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _usable_sentence(sentence: str) -> bool:
    if not 60 <= len(sentence) <= 260:
        return False
    words = sentence.split()
    if not 8 <= len(words) <= 40:
        return False
    meaningful = sum(ch.isalpha() or ch in " .,'-" for ch in sentence)
    if meaningful / len(sentence) < 0.75:
        return False
    if sum(ch.isdigit() for ch in sentence) > len(sentence) * 0.08:
        return False
    return True


def _term_key(word: str) -> str:
    return word.lower().strip("'-")


def _content_words(sentence: str) -> list[str]:
    return [
        w for w in _WORD_RE.findall(sentence)
        if len(_term_key(w)) >= 4 and _term_key(w).isalpha() and _term_key(w) not in _STOPWORDS
    ]


def _term_pool(text: str) -> Counter:
    pool: Counter = Counter()
    for word in _WORD_RE.findall(text):
        key = _term_key(word)
        if len(key) >= 4 and key.isalpha() and key not in _STOPWORDS:
            pool[key] += 1
    return pool


def _format_like(term: str, template: str) -> str:
    if template[:1].isupper():
        return term[:1].upper() + term[1:]
    return term


def generate_questions(
    text: str,
    max_questions: int = 12,
    rng: random.Random | None = None,
) -> list[Question]:
    rng = rng or random.Random()
    text = _clean(text)
    if len(text) < 400:
        raise NotEnoughContent("The document has almost no extractable text.")

    sentences = [_clean(s) for s in _SENTENCE_SPLIT.split(text)]
    sentences = [s for s in sentences if _usable_sentence(s)]
    pool = _term_pool(text)
    if len(pool) < 8 or len(sentences) < 3:
        raise NotEnoughContent("Couldn't find enough factual sentences to build a quiz.")

    rng.shuffle(sentences)
    questions: list[Question] = []
    used_terms: set[str] = set()
    seen_prompts: set[str] = set()

    for sentence in sentences:
        if len(questions) >= max_questions:
            break

        candidates = {
            _term_key(w) for w in _content_words(sentence)
        } - used_terms
        preferred = {k for k in candidates if not (k.endswith("ing") or k.endswith("ed"))}
        if preferred:
            candidates = preferred
        if not candidates:
            continue
        key = max(candidates, key=lambda k: pool[k])

        target = None
        for match in _WORD_RE.finditer(sentence):
            if _term_key(match.group()) == key:
                target = match
                break
        if target is None:
            continue

        answer = target.group().strip("'-")
        prompt = sentence[: target.start()] + "_____" + sentence[target.end():]
        if prompt.lower() in seen_prompts:
            continue

        lower_sentence = sentence.lower()
        nearby = [
            k for k in pool
            if k != key
            and abs(len(k) - len(key)) <= 3
            and k not in lower_sentence
            and k not in used_terms
        ]
        distractor_keys = [k for k in nearby if not (k.endswith("ing") or k.endswith("ed"))]
        if len(distractor_keys) < 3:
            distractor_keys = nearby
        if len(distractor_keys) < 3:
            continue

        chosen = rng.sample(distractor_keys, 3)
        options = [answer] + [_format_like(d, answer) for d in chosen]
        rng.shuffle(options)
        answer_index = options.index(answer)

        questions.append(Question(prompt=prompt, options=options, answer_index=answer_index))
        used_terms.add(key)
        seen_prompts.add(prompt.lower())

    if len(questions) < 3:
        raise NotEnoughContent(
            "Couldn't find enough factual sentences in this document to build a quiz."
        )
    return questions
