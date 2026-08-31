# Exam Formatter

Offline Windows application that converts the supported four-choice GIFT subset into a master-template-derived DOCX exam.

## Setup

The requested environment is defined in `environment.yml` and is named `exam-formatter`.

```powershell
conda run -n exam-formatter python -m pip install -r requirements.txt
conda run -n exam-formatter python -m exam_formatter.app
```

## Template contract

The master remains unchanged. It must contain `{{QUESTIONS}}` as a standalone body paragraph and the styles `Exam Question`, `Exam Choice`, and `Exam Choice Compact`. `Exam Question` must carry the template's real Word automatic-numbering definition. Metadata placeholders supported anywhere in paragraphs, table cells, headers, and footers are `{{EXAM_NAME}}`, `{{COURSE}}`, `{{SEMESTER}}`, `{{ACADEMIC_YEAR}}`, and `{{DATE}}`.

## Supported GIFT

Only four-choice, single-correct multiple-choice questions are supported. Optional `::titles::` are ignored in output. Escaped `\{`, `\}`, `\=`, `\~`, and `\\` are recognized. Question and choice order are never shuffled.

## Test and debug

```powershell
conda run -n exam-formatter pytest
conda run -n exam-formatter python tools/inspect_template.py 'Prelims DDS.docx'
conda run -n exam-formatter python generate_test.py --template 'Prelims DDS.docx' --gift samples/sample.gift --output output/test_exam.docx
```

## Packaging later

```powershell
conda run -n exam-formatter python -m pip install pyinstaller
conda run -n exam-formatter pyinstaller --windowed --name ExamFormatter exam_formatter/app.py
```
