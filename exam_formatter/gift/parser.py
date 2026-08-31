from __future__ import annotations

import re

from .exceptions import GiftParseError
from .models import Choice, Question

_ESCAPES = {
    "{": "{", "}": "}", "=": "=", "~": "~", "#": "#",
    ":": ":", "\\": "\\", "n": "\n",
}
_CHOICE_LABEL = re.compile(r"^\s*([A-D])\.\s*(.*)$", re.IGNORECASE)
_QUESTION_LABEL = re.compile(r"^\s*\d+\.\s*(.*)$", re.DOTALL)
_CATEGORY_LINE = re.compile(r"^\s*\$CATEGORY\s*:", re.IGNORECASE)
_FORMAT_TAG = re.compile(r"^\[(html|markdown|moodle|plain)]\s*", re.IGNORECASE)


def _unescape(text: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] in _ESCAPES:
            result.append(_ESCAPES[text[index + 1]])
            index += 2
        else:
            result.append(char)
            index += 1
    return "".join(result)


def _find_unescaped(text: str, target: str, start: int = 0) -> int:
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == target:
            return index
    return -1


def _clean_source(source: str) -> str:
    """Remove GIFT metadata lines that do not belong to question content."""
    lines: list[str] = []
    for raw_line in source.lstrip("\ufeff").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            continue
        if stripped.startswith("//") or _CATEGORY_LINE.match(stripped):
            continue
        # Tolerate AI placing general feedback after the closing brace.
        if stripped.startswith("####"):
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def _split_blocks(source: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    position = 0
    while position < len(source):
        while position < len(source) and source[position].isspace():
            position += 1
        if position >= len(source):
            break
        opening = _find_unescaped(source, "{", position)
        if opening < 0:
            raise GiftParseError(f"Question {len(blocks) + 1}: missing opening '{{'.")
        closing = _find_unescaped(source, "}", opening + 1)
        if closing < 0:
            raise GiftParseError(f"Question {len(blocks) + 1}: missing closing '}}'.")
        if _find_unescaped(source, "{", opening + 1) >= 0 and _find_unescaped(source, "{", opening + 1) < closing:
            raise GiftParseError(f"Question {len(blocks) + 1}: nested '{{' is not supported.")
        blocks.append((source[position:opening], source[opening + 1:closing]))
        position = closing + 1
    return blocks


def _parse_question(number: int, raw_stem: str, raw_answers: str) -> Question:
    stem = raw_stem.strip()
    numbered = _QUESTION_LABEL.match(stem)
    if numbered:
        stem = numbered.group(1).strip()
    title: str | None = None
    if stem.startswith("::"):
        end = stem.find("::", 2)
        if end < 0:
            raise GiftParseError(f"Question {number}: unterminated GIFT title.")
        title = stem[2:end].strip() or None
        stem = stem[end + 2:].strip()
    format_tag = _FORMAT_TAG.match(stem)
    if format_tag:
        requested_format = format_tag.group(1).lower()
        if requested_format in {"html", "markdown"}:
            raise GiftParseError(
                f"Question {number}: [{requested_format}] content is not supported; use plain text."
            )
        stem = stem[format_tag.end():]
    stem = _unescape(stem)
    if not stem:
        raise GiftParseError(f"Question {number}: question stem is empty.")

    choices = _parse_answer_block(number, raw_answers)
    if len(choices) != 4:
        raise GiftParseError(f"Question {number}: expected exactly 4 choices, found {len(choices)}.")
    correct_count = sum(choice.correct for choice in choices)
    if correct_count != 1:
        raise GiftParseError(f"Question {number}: expected one correct answer, found {correct_count}.")
    return Question(stem=stem, choices=tuple(choices), title=title)


def _parse_answer_block(number: int, raw_answers: str) -> list[Choice]:
    """Tokenize V1 multiple-choice answers and discard GIFT feedback safely."""
    choices: list[Choice] = []
    current: list[str] | None = None
    current_correct = False
    state = "seeking"  # seeking | answer | feedback | general_feedback

    def finish_choice() -> None:
        nonlocal current
        if current is None:
            return
        text = _unescape("".join(current).strip())
        if not text:
            raise GiftParseError(f"Question {number}: a choice is empty.")
        choices.append(Choice(text, current_correct))
        current = None

    index = 0
    while index < len(raw_answers):
        character = raw_answers[index]
        if character == "\\" and index + 1 < len(raw_answers):
            if state == "answer" and current is not None:
                current.extend((character, raw_answers[index + 1]))
            index += 2
            continue
        if state == "general_feedback":
            index += 1
            continue
        if raw_answers.startswith("####", index):
            finish_choice()
            state = "general_feedback"
            index += 4
            continue
        if character == "#":
            finish_choice()
            state = "feedback"
            index += 1
            continue
        if character in ("=", "~"):
            finish_choice()
            state = "answer"
            current_correct = character == "="
            current = []
            index += 1
            if index < len(raw_answers) and raw_answers[index] == "%":
                raise GiftParseError(
                    f"Question {number}: weighted or multiple-response answers are not supported in V1."
                )
            continue
        if state == "answer" and current is not None:
            current.append(character)
        elif state == "seeking" and not character.isspace():
            raise GiftParseError(
                f"Question {number}: each choice must begin with '=' or '~'; found unexpected text."
            )
        index += 1
    finish_choice()
    return choices


def _split_rationale(text: str) -> tuple[str, bool]:
    """A trailing unescaped # marks the correct legacy choice and its rationale."""
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "#":
            return text[:index].rstrip(), True
    return text.rstrip(), False


def _parse_labeled_mcq(source: str) -> list[Question]:
    """Import a strict A.–D. draft format often used before GIFT conversion.

    This is deliberately narrow: `#rationale` must be attached to exactly one
    choice. Standalone rationales cannot safely identify a correct answer.
    """
    questions: list[Question] = []
    title: str | None = None
    stem_lines: list[str] = []
    choices: list[Choice] = []

    def finish() -> None:
        nonlocal title, stem_lines, choices
        if not stem_lines and not choices:
            return
        number = len(questions) + 1
        stem = "\n".join(stem_lines).strip()
        if not stem:
            raise GiftParseError(f"Question {number}: question stem is empty.")
        if len(choices) != 4:
            raise GiftParseError(f"Question {number}: expected exactly 4 choices, found {len(choices)}.")
        correct_count = sum(choice.correct for choice in choices)
        if correct_count != 1:
            raise GiftParseError(
                f"Question {number}: expected one correct answer, found {correct_count}. "
                "In labeled import format, attach #rationale to the correct choice."
            )
        questions.append(Question(stem=_unescape(stem), choices=tuple(choices), title=title))
        title, stem_lines, choices = None, [], []

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or _CATEGORY_LINE.match(line) or line.startswith("//"):
            continue
        if line.startswith("####"):
            # A standalone explanation is discarded; it cannot indicate a key.
            continue
        if line.startswith("::"):
            if choices:
                finish()
            end = line.find("::", 2)
            if end < 0:
                raise GiftParseError(f"Question {len(questions) + 1}: unterminated GIFT title.")
            title = line[2:end].strip() or None
            remainder = line[end + 2:].strip()
            if remainder:
                stem_lines.append(remainder)
            continue
        choice_match = _CHOICE_LABEL.match(line)
        if choice_match:
            if not stem_lines:
                raise GiftParseError(f"Question {len(questions) + 1}: choice appears before its stem.")
            label = choice_match.group(1).upper()
            expected = chr(ord("A") + len(choices))
            if label != expected:
                raise GiftParseError(f"Question {len(questions) + 1}: expected choice {expected}., found {label}.")
            text, correct = _split_rationale(choice_match.group(2))
            if not text:
                raise GiftParseError(f"Question {len(questions) + 1}: choice {label}. is empty.")
            choices.append(Choice(_unescape(text), correct))
            continue
        question_match = _QUESTION_LABEL.match(line)
        content = question_match.group(1) if question_match else line
        if len(choices) == 4:
            finish()
        elif choices:
            # A wrapped line after A.–D. belongs to that choice.
            previous = choices[-1]
            choices[-1] = Choice(f"{previous.text}\n{_unescape(content)}", previous.correct)
        else:
            stem_lines.append(content)
    finish()
    if not questions:
        raise GiftParseError("No supported GIFT or labeled MCQ questions were provided.")
    return questions


def parse_gift(source: str) -> list[Question]:
    """Parse the deliberately small, validated GIFT subset supported by V1."""
    source = _clean_source(source)
    if not source.strip():
        raise GiftParseError("No GIFT questions were provided.")
    if _find_unescaped(source, "{") < 0:
        return _parse_labeled_mcq(source)
    return [_parse_question(index, stem, answers) for index, (stem, answers) in enumerate(_split_blocks(source), 1)]
