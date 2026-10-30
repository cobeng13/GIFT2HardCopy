# GIFT2HardCopy

Convert supported Moodle GIFT questions into a master-template-derived CAMP Major Exam DOCX and answer key. The desktop and web interfaces share the same parser and DOCX generation engine.

## Desktop version

The Windows desktop interface also supports importing Moodle XML question files.

```bash
conda env create -n exam-formatter-clean -f environment.yml
conda activate exam-formatter-clean
python -m exam_formatter.app
```

The Conda environment uses the project-pinned Python 3.12 and keeps Qt out of the shared `base` environment. If you use another isolated Python environment, install and launch with that same interpreter:

```bash
python -m pip install -r requirements-desktop.txt
python -m exam_formatter.app
```

The existing Conda environment is also defined in `environment.yml`. Install `requirements.txt` for the full desktop, web, and test development setup.

## Web version

The web form accepts pasted GIFT and multiple `.gift`/`.txt` files. When both are supplied, pasted text is followed by uploaded files in their selected order, separated by blank lines. Uploads must be UTF-8 or UTF-8-SIG; the combined input limit is 5 MB. The web interface uses the fixed server template `templates/master_exam.docx`.

Development:

```bash
python -m pip install -r requirements-web.txt
uvicorn exam_formatter.web.app:app --reload
```

Production/server:

```bash
uvicorn exam_formatter.web.app:app --host 0.0.0.0 --port 8000
```

The generated ZIP contains the DOCX exam and its `_ANSWERKEY.txt` file.

## Docker

The web image installs only web and core dependencies; it does not install PySide6.

```bash
docker build -t gift2hardcopy .
docker run -d --name gift2hardcopy -p 8000:8000 gift2hardcopy
```

Open `http://localhost:8000` after starting the container.

## Template contract

The master template must contain `{{QUESTIONS}}` as a standalone body paragraph and the styles `Exam Question`, `Exam Choice`, and `Exam Choice Compact`. `Exam Question` must carry the template's real Word automatic-numbering definition. Metadata placeholders supported anywhere in paragraphs, table cells, headers, and footers are `{{EXAM_NAME}}`, `{{COURSE}}`, `{{SEMESTER}}`, `{{ACADEMIC_YEAR}}`, `{{DATE}}`, `{{FACULTY_MEMBER}}`, `{{DEPARTMENT_CHAIR}}`, `{{PROGRAM}}`, and `{{PROGRAM_LONG_NAME}}`. The program selector fills the matching department chair and full program title from the fixed program list in the web and desktop forms.

The `generate_test.py` command-line utility accepts `--faculty-member` and `--program` to populate the new placeholders. It does not launch a graphical interface.

## Supported GIFT

Only four-choice, single-correct multiple-choice questions are supported. Optional `::titles::` are ignored in output. Escaped `\{`, `\}`, `\=`, `\~`, and `\\` are recognized. Question and choice order are never shuffled.

## Supported Moodle XML

The desktop file loader accepts `.gift`, `.txt`, and `.xml` files in any sequence. Moodle XML support is limited to UTF-8, text-only `multichoice` questions with `<single>true</single>`, exactly four answers, and exactly one `fraction="100"` answer. Basic HTML is converted to plain text; unsupported content stops import with an error.

## Tests and utilities

```bash
python -m pip install -r requirements.txt
pytest
python tools/inspect_template.py 'Prelims DDS.docx'
python generate_test.py --template 'Prelims DDS.docx' --gift samples/sample.gift --output output/test_exam.docx
```

## Aiken import and automatic detection

Pasted text and each uploaded `.txt` or `.gift` file are detected independently as GIFT or Aiken. You can combine GIFT and Aiken files in one request; pasted questions come first, then uploaded files in upload order. Each input must contain one format. UTF-8 and UTF-8-SIG are supported. Desktop text import and `generate_test.py --gift input.txt` use the same detection.

Aiken follows [Moodle’s format](https://docs.moodle.org/502/en/Aiken_format): one question line, uppercase sequential answer labels with a period or closing parenthesis followed by a space, and an uppercase `ANSWER: X` line immediately after the last option. Separate questions with blank lines. This application supports exactly four options (A–D), even though Moodle Aiken allows more. No manual format selector is needed.

```text
Which city is in Japan?
A. Manila
B. Tokyo
C. Paris
D. Rome
ANSWER: B
```

Invalid keys, missing answers, out-of-order options, and unsupported choice counts stop the import with a readable error. Existing GIFT and labeled MCQ support still uses the original GIFT parser. The DOCX generator and template contract are unchanged.
