from __future__ import annotations

import re
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from exam_formatter.docx_engine.generator import generate_exam
from exam_formatter.gift.exceptions import GiftParseError
from exam_formatter.gift.parser import parse_gift
from exam_formatter.programs import PROGRAM_CHAIRS, PROGRAM_LONG_NAMES

WEB_DIR = Path(__file__).resolve().parent
MASTER_TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "master_exam.docx"
MAX_INPUT_BYTES = 5 * 1024 * 1024
ALLOWED_SUFFIXES = {".gift", ".txt"}

app = FastAPI(title="GIFT2HardCopy")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_INPUT_BYTES + 256 * 1024:
                return JSONResponse({"detail": "Request is too large. The combined input limit is 5 MB."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid request size."}, status_code=400)
    return await call_next(request)


def _safe_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_-")
    return cleaned or fallback


async def _combined_gift(text: str, uploads: list[UploadFile]) -> str:
    parts = [text] if text.strip() else []
    total = len(text.encode("utf-8"))
    for upload in uploads:
        if not upload.filename:
            continue
        if Path(upload.filename).suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError("Only .gift and .txt files can be uploaded.")
        content = await upload.read(MAX_INPUT_BYTES + 1)
        total += len(content)
        if total > MAX_INPUT_BYTES:
            raise ValueError("GIFT input is too large. The combined limit is 5 MB.")
        try:
            parts.append(content.decode("utf-8-sig"))
        except UnicodeDecodeError as error:
            raise ValueError(f"{Path(upload.filename).name} must be UTF-8 encoded.") from error
    if total > MAX_INPUT_BYTES:
        raise ValueError("GIFT input is too large. The combined limit is 5 MB.")
    if not parts:
        raise ValueError("Paste GIFT questions or upload at least one .gift or .txt file.")
    return "\n\n".join(parts)


def _render(request: Request, *, message: str = "", error: bool = False,
            exam_name: str = "Preliminary Examination", course: str = "", semester: str = "1st Semester",
            academic_year: str = "", exam_date: str = "", faculty_member: str = "", program: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={
        "message": message, "is_error": error, "exam_name": exam_name, "course": course,
        "semester": semester, "academic_year": academic_year, "exam_date": exam_date or date.today().isoformat(),
        "faculty_member": faculty_member, "program": program, "program_chairs": PROGRAM_CHAIRS,
        "program_long_names": PROGRAM_LONG_NAMES,
    })


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request) -> HTMLResponse:
    return _render(request)


@app.post("/validate", response_class=HTMLResponse)
async def validate_gift(
    request: Request,
    gift_text: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    exam_name: str = Form("Preliminary Examination"),
    course: str = Form(""),
    semester: str = Form("1st Semester"),
    academic_year: str = Form(""),
    exam_date: str = Form(""),
    faculty_member: str = Form(""),
    program: str = Form(""),
) -> HTMLResponse:
    try:
        if program and program not in PROGRAM_CHAIRS:
            raise ValueError("Select a valid program.")
        source = await _combined_gift(gift_text, files)
        questions = parse_gift(source)
        return _render(request, message=f"Valid GIFT: {len(questions)} questions detected.", exam_name=exam_name,
                       course=course, semester=semester, academic_year=academic_year, exam_date=exam_date,
                       faculty_member=faculty_member, program=program)
    except Exception as error:
        message = str(error) if isinstance(error, (ValueError, GiftParseError)) else "GIFT validation failed. Check the input and try again."
        return _render(request, message=message, error=True, exam_name=exam_name, course=course,
                       semester=semester, academic_year=academic_year, exam_date=exam_date,
                       faculty_member=faculty_member, program=program)
    finally:
        for upload in files:
            await upload.close()


@app.post("/generate")
async def generate(
    request: Request,
    gift_text: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    exam_name: str = Form("Preliminary Examination"),
    course: str = Form(""),
    semester: str = Form("1st Semester"),
    academic_year: str = Form(""),
    exam_date: str = Form(""),
    faculty_member: str = Form(""),
    program: str = Form(""),
):
    temp_dir = None
    try:
        source = await _combined_gift(gift_text, files)
        questions = parse_gift(source)
        if program and program not in PROGRAM_CHAIRS:
            raise ValueError("Select a valid program.")
        if not MASTER_TEMPLATE.is_file():
            raise RuntimeError("The master exam template is unavailable on the server.")
        date_value = ""
        if exam_date:
            parsed_date = date.fromisoformat(exam_date)
            date_value = f"{parsed_date.strftime('%B')} {parsed_date.day}, {parsed_date.year}"
        metadata = {"EXAM_NAME": exam_name, "COURSE": course, "SEMESTER": semester,
                    "ACADEMIC_YEAR": academic_year, "DATE": date_value, "FACULTY_MEMBER": faculty_member,
                    "PROGRAM": program, "DEPARTMENT_CHAIR": PROGRAM_CHAIRS.get(program, ""),
                    "PROGRAM_LONG_NAME": PROGRAM_LONG_NAMES.get(program, "")}
        course_part = _safe_filename(course, "COURSE")
        exam_part = _safe_filename(exam_name, "EXAM")
        base_name = f"{course_part}_{exam_part}"
        temp_dir = tempfile.TemporaryDirectory(prefix="gift2hardcopy-")
        root = Path(temp_dir.name)
        docx_path = root / f"{base_name}.docx"
        key_path = generate_exam(MASTER_TEMPLATE, docx_path, metadata, questions)
        zip_path = root / f"{base_name}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(docx_path, arcname=docx_path.name)
            archive.write(key_path, arcname=f"{base_name}_ANSWERKEY.txt")
        return FileResponse(zip_path, media_type="application/zip", filename=f"{base_name}.zip",
                            background=BackgroundTask(temp_dir.cleanup))
    except Exception as error:
        message = str(error) if isinstance(error, (ValueError, GiftParseError)) else "Exam generation failed. Check the template and GIFT content, then try again."
        if temp_dir is not None:
            temp_dir.cleanup()
        return _render(request, message=message, error=True, exam_name=exam_name, course=course,
                       semester=semester, academic_year=academic_year, exam_date=exam_date,
                       faculty_member=faculty_member, program=program)
    finally:
        for upload in files:
            await upload.close()
