import pytest

from exam_formatter.question_input import AikenParseError, parse_questions

AIKEN = "Which city is in Japan?\nA. Manila\nB. Tokyo\nC. Paris\nD. Rome\nANSWER: B"


@pytest.mark.parametrize("separator", [".", ")"])
def test_aiken_detection_and_key(separator):
    source = AIKEN.replace(". ", separator + " ")
    questions = parse_questions("\ufeff" + source + "\n\n" + source)
    assert len(questions) == 2
    assert questions[0].stem == "Which city is in Japan?"
    assert [c.text for c in questions[0].choices] == ["Manila", "Tokyo", "Paris", "Rome"]
    assert [c.correct for c in questions[0].choices] == [False, True, False, False]


@pytest.mark.parametrize("source, message", [
    (AIKEN.replace("ANSWER: B", "ANSWER: Z"), "existing choice"),
    (AIKEN.replace("ANSWER: B", "answer: b"), "uppercase"),
    (AIKEN.replace("B. Tokyo", "C. Tokyo"), "expected choice B"),
    (AIKEN.replace("D. Rome\n", ""), "exactly 4"),
    (AIKEN.replace("ANSWER: B", "E. Lima\nANSWER: B"), "exactly 4"),
    (AIKEN.replace("\nA.", "\nwrapped stem\nA."), "one line"),
    (AIKEN.replace("ANSWER: B", "").replace(". ", ") "), "missing ANSWER"),
])
def test_invalid_aiken_is_not_silently_imported(source, message):
    with pytest.raises(AikenParseError, match=message):
        parse_questions(source)


def test_gift_still_uses_existing_parser():
    questions = parse_questions("Question? {=A ~B ~C ~D}")
    assert questions[0].choices[0].correct
