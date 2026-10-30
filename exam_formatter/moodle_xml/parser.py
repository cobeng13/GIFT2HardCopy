from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from lxml import etree
from exam_formatter.html_text import html_to_text, HtmlContentError

from exam_formatter.gift.models import Choice, Question

from .exceptions import MoodleXmlParseError

_XML_ENCODING = re.compile(r"<\?xml[^>]*encoding\s*=\s*['\"]([^'\"]+)", re.IGNORECASE)
_UNSAFE_DECLARATION = re.compile(r"<!\s*(DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _normalized_xml_bytes(source: str | bytes) -> bytes:
    if isinstance(source, bytes):
        try:
            decoded = source.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise MoodleXmlParseError("Moodle XML must be encoded as UTF-8.") from error
    else:
        decoded = source.lstrip("\ufeff")
    encoding = _XML_ENCODING.search(decoded[:300])
    if encoding and encoding.group(1).lower().replace("_", "-") not in {"utf-8", "utf8"}:
        raise MoodleXmlParseError("Moodle XML must declare UTF-8 encoding.")
    if _UNSAFE_DECLARATION.search(decoded):
        raise MoodleXmlParseError("DTD and entity declarations are not supported.")
    return decoded.encode("utf-8")




def _inner_text(text_node) -> str:
    pieces = [text_node.text or ""]
    pieces.extend(etree.tostring(child, encoding="unicode") for child in text_node)
    return "".join(pieces)


def _content(container, question_number: int, field: str, default_format: str = "html") -> str:
    text_node = container.find("text") if container is not None else None
    if text_node is None:
        raise MoodleXmlParseError(f"Question {question_number}: {field} is missing its <text> value.")
    content_format = (container.get("format") or default_format).strip().lower()
    raw = _inner_text(text_node)
    if content_format == "html":
        try:
            value = html_to_text(raw)
        except HtmlContentError as error:
            raise MoodleXmlParseError(f"Question {question_number}: {field}: {error}") from error
    elif content_format in {"plain_text", "moodle_auto_format"}:
        value = raw.strip()
    else:
        raise MoodleXmlParseError(
            f"Question {question_number}: {field} format '{content_format}' is not supported."
        )
    if not value:
        raise MoodleXmlParseError(f"Question {question_number}: {field} is empty.")
    return value


def _title(question_element) -> str | None:
    text_node = question_element.find("./name/text")
    if text_node is None:
        return None
    value = " ".join("".join(text_node.itertext()).split())
    return value or None


def _parse_multichoice(question_element, number: int) -> Question:
    if question_element.find(".//file") is not None:
        raise MoodleXmlParseError(f"Question {number}: embedded files or media are not supported.")
    single = question_element.findtext("single")
    if single is None or single.strip().lower() not in {"true", "1"}:
        raise MoodleXmlParseError(f"Question {number}: only single-answer multichoice questions are supported.")
    stem = _content(question_element.find("questiontext"), number, "question text")
    answer_elements = question_element.findall("answer")
    if len(answer_elements) != 4:
        raise MoodleXmlParseError(f"Question {number}: expected exactly 4 answers, found {len(answer_elements)}.")
    choices: list[Choice] = []
    for answer_number, answer in enumerate(answer_elements, 1):
        raw_fraction = answer.get("fraction")
        try:
            fraction = Decimal(raw_fraction) if raw_fraction is not None else None
        except InvalidOperation as error:
            raise MoodleXmlParseError(
                f"Question {number}: answer {answer_number} has invalid fraction '{raw_fraction}'."
            ) from error
        if fraction is None:
            raise MoodleXmlParseError(f"Question {number}: answer {answer_number} is missing its fraction.")
        if not fraction.is_finite():
            raise MoodleXmlParseError(
                f"Question {number}: answer {answer_number} has invalid fraction '{raw_fraction}'."
            )
        if fraction > 0 and fraction != 100:
            raise MoodleXmlParseError(
                f"Question {number}: partial-credit fraction {fraction} is not supported."
            )
        choices.append(Choice(_content(answer, number, f"answer {answer_number}"), fraction == 100))
    correct_count = sum(choice.correct for choice in choices)
    if correct_count != 1:
        raise MoodleXmlParseError(f"Question {number}: expected one 100% answer, found {correct_count}.")
    return Question(stem=stem, choices=tuple(choices), title=_title(question_element))


def parse_moodle_xml(source: str | bytes) -> list[Question]:
    """Parse the supported text-only Moodle XML multichoice subset."""
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        recover=False,
    )
    try:
        root = etree.fromstring(_normalized_xml_bytes(source), parser=parser)
    except MoodleXmlParseError:
        raise
    except etree.XMLSyntaxError as error:
        raise MoodleXmlParseError(f"Malformed Moodle XML: {error.msg}.") from error
    if root.tag != "quiz":
        raise MoodleXmlParseError("Moodle XML root element must be <quiz>.")
    questions: list[Question] = []
    for element in root.findall("question"):
        question_type = (element.get("type") or "").strip().lower()
        if question_type == "category":
            continue
        number = len(questions) + 1
        if question_type != "multichoice":
            raise MoodleXmlParseError(
                f"Question {number}: unsupported Moodle question type '{question_type or '(missing)'}'."
            )
        questions.append(_parse_multichoice(element, number))
    if not questions:
        raise MoodleXmlParseError("No supported Moodle multichoice questions were found.")
    return questions
