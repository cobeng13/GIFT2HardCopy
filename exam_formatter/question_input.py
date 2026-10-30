"""Detect supported text question formats and produce the shared question model."""
import re

from exam_formatter.gift.exceptions import GiftParseError
from exam_formatter.gift.models import Choice, Question
from exam_formatter.gift.parser import parse_gift


class AikenParseError(GiftParseError):
    """A readable error in an Aiken question bank."""


def parse_aiken(source: str) -> list[Question]:
    questions: list[Question] = []
    stem = ""
    options: list[str] = []
    for line_number, raw in enumerate(source.lstrip("\ufeff").splitlines(), 1):
        line = raw.strip()

        def fail(message: str) -> None:
            raise AikenParseError(f"Aiken question {len(questions) + 1}, line {line_number}: {message}")

        if not line:
            if stem:
                fail("expected choices and ANSWER before a blank line.")
            continue
        if re.match(r"ANSWER\s*:", line, re.IGNORECASE):
            match = re.fullmatch(r"ANSWER: ([A-Z])", line)
            if not match:
                fail("use uppercase ANSWER: followed by a space and one uppercase answer letter.")
            if not stem or len(options) != 4:
                fail(f"expected exactly 4 choices before ANSWER, found {len(options)}.")
            key = ord(match.group(1)) - ord("A")
            if not 0 <= key < len(options):
                fail("ANSWER must identify an existing choice (A–D).")
            questions.append(Question(stem, tuple(Choice(text, i == key) for i, text in enumerate(options))))
            stem, options = "", []
        elif re.match(r"[A-Za-z][.)]", line):
            match = re.fullmatch(r"([A-Z])[.)]\s+(.+)", line)
            if not stem:
                fail("a question stem must appear before its choices.")
            expected = chr(ord("A") + len(options))
            if not match or match.group(1) != expected:
                fail(f"expected choice {expected}. or {expected}) followed by a space and answer text.")
            if len(options) == 4:
                fail("this application supports exactly 4 choices (A–D).")
            options.append(match.group(2))
        elif stem:
            fail("question stems and choices must each occupy one line; missing ANSWER: A–D?")
        else:
            stem = line
    if stem:
        raise AikenParseError(f"Aiken question {len(questions) + 1}: missing ANSWER: A–D line.")
    if not questions:
        raise AikenParseError("No Aiken questions were provided.")
    return questions


def parse_questions(source: str) -> list[Question]:
    """Auto-detect each input independently; preserve the existing GIFT parser."""
    if re.search(r"^\s*ANSWER\s*:", source, re.MULTILINE | re.IGNORECASE) or re.search(
        r"^\s*A\)\s+", source, re.MULTILINE
    ):
        return parse_aiken(source)
    return parse_gift(source)
