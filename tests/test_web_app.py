from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from docx import Document

from exam_formatter.web.app import app

client = TestClient(app)
GIFT = "Question one? {\n=a\n~b\n~c\n~d\n}"
AIKEN = "Aiken question?\nA) One\nB) Two\nC) Three\nD) Four\nANSWER: C"


def test_aiken_paste_validates_and_generates_zip():
    response = client.post("/validate", data={"gift_text": AIKEN})
    assert "Valid questions: 1" in response.text
    response = client.post("/generate", data={"gift_text": AIKEN})
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        key = next(name for name in archive.namelist() if name.endswith("_ANSWERKEY.txt"))
        assert archive.read(key).decode().splitlines() == ["ANSWER KEY", "", "1. C"]


def test_mixed_format_uploads_keep_order_and_bom():
    response = client.post("/generate", data={"gift_text": GIFT}, files=[
        ("files", ("aiken.txt", AIKEN.encode("utf-8-sig"), "text/plain")),
        ("files", ("gift.gift", GIFT.encode(), "text/plain")),
    ])
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        key = next(name for name in archive.namelist() if name.endswith("_ANSWERKEY.txt"))
        assert archive.read(key).decode().splitlines() == ["ANSWER KEY", "", "1. A", "2. C", "3. A"]


def test_invalid_aiken_returns_readable_error():
    response = client.post("/validate", data={"gift_text": AIKEN.replace("ANSWER: C", "ANSWER: Z")})
    assert "existing choice" in response.text
    assert "Traceback" not in response.text


def test_homepage_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "LMStoHardCopy" in response.text


def test_valid_gift_can_be_validated():
    response = client.post("/validate", data={"gift_text": GIFT})
    assert response.status_code == 200
    assert "Valid questions: 1 questions detected." in response.text


def test_invalid_gift_shows_readable_error_without_traceback():
    response = client.post("/validate", data={"gift_text": "not a question"})
    assert response.status_code == 200
    assert "expected exactly 4 choices" in response.text
    assert "Traceback" not in response.text


def test_uploaded_files_are_concatenated_in_order():
    files = [("files", ("first.gift", BytesIO(GIFT.encode()), "text/plain")),
             ("files", ("second.txt", BytesIO(GIFT.replace("one", "two").encode()), "text/plain"))]
    response = client.post("/validate", files=files)
    assert response.status_code == 200
    assert "2 questions detected" in response.text


def test_valid_gift_generates_zip_with_docx_and_answer_key():
    response = client.post("/generate", data={"gift_text": GIFT, "course": "PHARMACOLOGY",
                                               "exam_name": "Preliminary Examination", "exam_date": "2026-09-24",
                                               "faculty_member": "Dr. Faculty Example", "program": "Pharmacy"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"].endswith('filename="PHARMACOLOGY_Preliminary_Examination.zip"')
    with ZipFile(BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "PHARMACOLOGY_Preliminary_Examination.docx",
            "PHARMACOLOGY_Preliminary_Examination_ANSWERKEY.txt",
        }
        document = Document(BytesIO(archive.read("PHARMACOLOGY_Preliminary_Examination.docx")))
        rendered_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        assert "Dr. Faculty Example" in rendered_text
        assert "Mr. Aaron Dell A. Cobeng, RPh, MA ELM" in rendered_text
        assert "Pharmacy" in rendered_text
        assert "Diploma in Pharmacy Assisting Leading to\nBachelor of Science in Pharmacy" in rendered_text
