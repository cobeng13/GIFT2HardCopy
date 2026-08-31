import pytest
from exam_formatter.gift.exceptions import GiftParseError
from exam_formatter.gift.parser import parse_gift

VALID = "::Title::\nA multiline\nstem {\n=correct\n~wrong 1\n~wrong 2\n~wrong 3\n}"

def test_parse_valid_question_and_title():
    question = parse_gift(VALID)[0]
    assert question.title == "Title" and question.stem == "A multiline\nstem"
    assert [choice.text for choice in question.choices] == ["correct", "wrong 1", "wrong 2", "wrong 3"]
    assert sum(choice.correct for choice in question.choices) == 1

def test_multiple_questions_preserve_order():
    questions = parse_gift(VALID + "\n\nSecond? {\n~a\n=b\n~c\n~d\n}")
    assert [question.stem for question in questions] == ["A multiline\nstem", "Second?"]

def test_escaped_controls():
    question = parse_gift("What is \\{x\\}? {\n=\\= equals\n~\\~ tilde\n~\\} brace\n~\\\\ slash\n}")[0]
    assert question.stem == "What is {x}?" and question.choices[0].text == "= equals"


def test_canonical_feedback_and_general_feedback_are_discarded():
    source = """$CATEGORY: Science
// generated item
1. ::Feedback::Which answer is correct? {
~Wrong A#Specific feedback with words
=Correct C#Correct-answer feedback
~Wrong B#Another response
~Wrong D
####General feedback for the whole question
}
"""
    question = parse_gift(source)[0]
    assert question.title == "Feedback"
    assert question.stem == "Which answer is correct?"
    assert [choice.text for choice in question.choices] == ["Wrong A", "Correct C", "Wrong B", "Wrong D"]
    assert [choice.correct for choice in question.choices] == [False, True, False, False]


def test_inline_answers_feedback_and_escaped_hash():
    question = parse_gift(r"Pick one {~A\#1#No =B#Yes ~C#No ~D#No ####Overall}")[0]
    assert [choice.text for choice in question.choices] == ["A#1", "B", "C", "D"]
    assert question.choices[1].correct


def test_literal_newline_and_colon_escape():
    question = parse_gift(r"First\nSecond {=ratio\: 1 ~b ~c ~d}")[0]
    assert question.stem == "First\nSecond"
    assert question.choices[0].text == "ratio: 1"


def test_weighted_answers_are_rejected_clearly():
    with pytest.raises(GiftParseError, match="weighted or multiple-response"):
        parse_gift("Stem {~%50%a ~%50%b ~c ~d}")


def test_ai_markdown_fence_and_missing_blank_separator_are_tolerated():
    source = """```gift
First {=a ~b ~c ~d}::Second::Second stem {~a =b ~c ~d}
```
"""
    questions = parse_gift(source)
    assert [question.stem for question in questions] == ["First", "Second stem"]


def test_labeled_mcq_import_ignores_category_comments_titles_and_rationales():
    source = """$CATEGORY: Research Hypotheses
// Bloom's level: Remember
::RH01 Remember::What is a research hypothesis?
A. An explanation
B. A summary
C. A testable prediction#This marks the correct answer.
D. A procedure
####Standalone rationale is ignored.
"""
    question = parse_gift(source)[0]
    assert question.title == "RH01 Remember"
    assert question.stem == "What is a research hypothesis?"
    assert [choice.text for choice in question.choices] == ["An explanation", "A summary", "A testable prediction", "A procedure"]
    assert question.choices[2].correct


def test_labeled_mcq_requires_an_explicit_correct_marker():
    source = """What is the next step?
A. First option
B. Second option
C. Third option
D. Fourth option
####A standalone rationale is not a key.
"""
    with pytest.raises(GiftParseError, match="attach #rationale"):
        parse_gift(source)

@pytest.mark.parametrize("answers,error", [("=a\n~b\n~c", "4 choices"), ("=a\n~b\n~c\n~d\n~e", "4 choices"), ("=a\n=b\n~c\n~d", "one correct"), ("~a\n~b\n~c\n~d", "one correct")])
def test_invalid_choice_counts_and_keys(answers, error):
    with pytest.raises(GiftParseError, match=error): parse_gift(f"Stem {{\n{answers}\n}}")
