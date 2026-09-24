# GIFT2HardCopy

Convert supported Moodle GIFT questions into a master-template-derived CAMP Major Exam DOCX and answer key. The desktop and web interfaces share the same parser and DOCX generation engine.

## Desktop version

The Windows desktop interface also supports importing Moodle XML question files.

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

The master template must contain `{{QUESTIONS}}` as a standalone body paragraph and the styles `Exam Question`, `Exam Choice`, and `Exam Choice Compact`. `Exam Question` must carry the template's real Word automatic-numbering definition. Metadata placeholders supported anywhere in paragraphs, table cells, headers, and footers are `{{EXAM_NAME}}`, `{{COURSE}}`, `{{SEMESTER}}`, `{{ACADEMIC_YEAR}}`, and `{{DATE}}`.

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
