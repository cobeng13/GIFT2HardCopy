import pytest

from exam_formatter.gift.exceptions import GiftParseError
from exam_formatter.question_input import parse_questions


GIFT_HTML = '''// question: 1 name: Sample
$CATEGORY: $module$/top/Chemistry
::Sample::[html]<p>Which property is intensive &amp; measurable?</p>{
~<p>Mass</p>
=<p>Density</p>
~<p>Volume</p>
~<p>Amount</p>
####<p>Feedback is omitted from the printed exam.</p>
}'''

XML = '''<?xml version="1.0" encoding="UTF-8"?>
<quiz><question type="category"><category><text>Chemistry</text></category></question>
<question type="multichoice"><name><text>Sample</text></name>
<questiontext format="html"><text><![CDATA[<p>Which property is intensive &amp; measurable?</p>]]></text></questiontext>
<single>true</single>
<answer fraction="0" format="html"><text><![CDATA[<p>Mass</p>]]></text></answer>
<answer fraction="100" format="html"><text><![CDATA[<p>Density</p>]]></text></answer>
<answer fraction="0" format="html"><text><![CDATA[<p>Volume</p>]]></text></answer>
<answer fraction="0" format="html"><text><![CDATA[<p>Amount</p>]]></text></answer>
</question></quiz>'''


def test_lms_html_gift_and_xml_produce_identical_questions():
    gift = parse_questions(GIFT_HTML)
    assert gift == parse_questions(XML)
    assert gift[0].stem == "Which property is intensive & measurable?"
    assert [c.text for c in gift[0].choices] == ["Mass", "Density", "Volume", "Amount"]
    assert gift[0].choices[1].correct


def test_html_lines_entities_and_escaped_gift_controls():
    question = parse_questions(r'::HTML::[html]<p>First &amp; second<br>Next</p>{=<p>x\=1</p> ~<p>B</p> ~<p>C</p> ~<p>D</p>}')[0]
    assert question.stem == "First & second\nNext"
    assert question.choices[0].text == "x=1"


@pytest.mark.parametrize("markup", ['<img src="x">', '<table><tr><td>x</td></tr></table>', '<span class="equation">x</span>'])
def test_html_media_and_equations_are_rejected(markup):
    with pytest.raises(GiftParseError, match="unsupported"):
        parse_questions(GIFT_HTML.replace("<p>Mass</p>", markup.replace("=", "\\=")))


def test_empty_html_choice_rejected():
    with pytest.raises(GiftParseError, match="contain text"):
        parse_questions(GIFT_HTML.replace("<p>Mass</p>", "<p></p>"))


def test_xml_hint_rejects_nonquiz_root_and_entities():
    with pytest.raises(ValueError, match="root element"):
        parse_questions("<other/>", filename="questions.xml")
    with pytest.raises(ValueError, match="DTD and entity"):
        parse_questions('<!DOCTYPE quiz [<!ENTITY secret SYSTEM "file:///etc/passwd">]><quiz/>')


def test_plain_text_preserves_literal_angle_brackets():
    assert parse_questions("Is x < y? {=yes ~no ~maybe ~never}")[0].stem == "Is x < y?"


def test_web_xml_paste_and_mixed_upload_generation():
    from io import BytesIO
    from zipfile import ZipFile
    from fastapi.testclient import TestClient
    from exam_formatter.web.app import app

    with TestClient(app) as client:
        response = client.post("/validate", data={"gift_text": XML})
        assert "Valid questions: 1" in response.text
        response = client.post("/generate", data={"gift_text": GIFT_HTML}, files=[
            ("files", ("moodle.xml", XML.encode("utf-8-sig"), "application/xml")),
            ("files", ("aiken.txt", b"Question?\nA. A\nB. B\nC. C\nD. D\nANSWER: C", "text/plain")),
        ])
        assert response.headers["content-type"] == "application/zip"
        with ZipFile(BytesIO(response.content)) as archive:
            key = next(name for name in archive.namelist() if name.endswith("_ANSWERKEY.txt"))
            assert archive.read(key).decode().splitlines() == ["ANSWER KEY", "", "1. B", "2. B", "3. C"]


def test_web_xml_upload_error_does_not_expose_traceback():
    from fastapi.testclient import TestClient
    from exam_formatter.web.app import app

    with TestClient(app) as client:
        response = client.post("/validate", files={"files": ("invalid.xml", b"<quiz><question></quiz>", "application/xml")})
        assert "Malformed Moodle XML" in response.text
        assert "Traceback" not in response.text
