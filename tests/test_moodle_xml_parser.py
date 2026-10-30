import pytest

from exam_formatter.moodle_xml.exceptions import MoodleXmlParseError
from exam_formatter.moodle_xml.parser import parse_moodle_xml


def xml_question(*, question_type="multichoice", single="true", answers=None, stem=None):
    if answers is None:
        answers = [("100", "Correct"), ("0", "Wrong 1"), ("-25", "Wrong 2"), ("0", "Wrong 3")]
    if stem is None:
        stem = "<questiontext format=\"html\"><text><![CDATA[<p>Stem</p>]]></text></questiontext>"
    answer_xml = "".join(
        f'<answer fraction="{fraction}" format="html"><text><![CDATA[{text}]]></text></answer>'
        for fraction, text in answers
    )
    single_xml = "" if single is None else f"<single>{single}</single>"
    return f"""
    <question type="{question_type}">
      <name><text>Question title</text></name>
      {stem}
      {single_xml}
      {answer_xml}
    </question>
    """


def quiz(question):
    return f'<?xml version="1.0" encoding="UTF-8"?><quiz>{question}</quiz>'


def test_parses_category_cdata_html_lists_entities_and_negative_fractions():
    stem = """<questiontext format="html"><text><![CDATA[
      <p>Which &amp; why?</p><ul><li>First</li><li>Second</li></ul>
    ]]></text></questiontext>"""
    answers = [("0", "<span>A &amp; B</span>"), ("100.0", "<strong>Correct</strong>"), ("-33.333", "Third"), ("0", "Fourth")]
    source = quiz(
        '<question type="category"><category><text>$course$/Science</text></category></question>'
        + xml_question(single="1", answers=answers, stem=stem)
    )

    question = parse_moodle_xml(b"\xef\xbb\xbf" + source.encode("utf-8"))[0]

    assert question.title == "Question title"
    assert question.stem == "Which & why?\n- First\n- Second"
    assert [choice.text for choice in question.choices] == ["A & B", "Correct", "Third", "Fourth"]
    assert [choice.correct for choice in question.choices] == [False, True, False, False]


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("<notquiz />", "root element"),
        (quiz(xml_question(question_type="essay")), "unsupported Moodle question type"),
        (quiz(xml_question(single=None)), "single-answer"),
        (quiz(xml_question(single="false")), "single-answer"),
        (quiz(xml_question(answers=[("100", "A"), ("0", "B"), ("0", "C")])), "exactly 4"),
        (quiz(xml_question(answers=[("100", "A"), ("100", "B"), ("0", "C"), ("0", "D")])), "one 100%"),
        (quiz(xml_question(answers=[("50", "A"), ("0", "B"), ("0", "C"), ("0", "D")])), "partial-credit"),
        (quiz(xml_question(answers=[("NaN", "A"), ("0", "B"), ("0", "C"), ("0", "D")])), "invalid fraction"),
        (quiz(xml_question(answers=[("100", ""), ("0", "B"), ("0", "C"), ("0", "D")])), "answer 1 is empty"),
        (quiz(xml_question(stem='<questiontext format="html"><text><![CDATA[<p>Stem</p><img src="x">]]></text></questiontext>')), "<img>"),
        (quiz(xml_question(stem='<questiontext format="html"><text><![CDATA[<span class="equation">x</span>]]></text></questiontext>')), "equation"),
        (quiz(xml_question(stem='<questiontext format="markdown"><text>**Stem**</text></questiontext>')), "format 'markdown'"),
    ],
)
def test_rejects_unsupported_question_shapes(source, error):
    with pytest.raises(MoodleXmlParseError, match=error):
        parse_moodle_xml(source)


def test_rejects_malformed_non_utf8_and_unsafe_declarations():
    with pytest.raises(MoodleXmlParseError, match="Malformed"):
        parse_moodle_xml("<quiz><question></quiz>")
    with pytest.raises(MoodleXmlParseError, match="UTF-8"):
        parse_moodle_xml('<?xml version="1.0" encoding="ISO-8859-1"?><quiz/>')
    with pytest.raises(MoodleXmlParseError, match="DTD and entity"):
        parse_moodle_xml('<!DOCTYPE quiz [<!ENTITY x SYSTEM "file:///etc/passwd">]><quiz>&x;</quiz>')


def test_rejects_embedded_file_payloads():
    source = quiz(xml_question(stem='<questiontext format="html"><text>Stem</text><file name="x.png">AA==</file></questiontext>'))
    with pytest.raises(MoodleXmlParseError, match="embedded files"):
        parse_moodle_xml(source)
