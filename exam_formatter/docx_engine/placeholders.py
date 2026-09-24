from __future__ import annotations

from collections.abc import Mapping
from docx.document import Document
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph


def _paragraphs_in_table(table: Table):
    for row in table.rows:
        for cell in row.cells:
            yield from cell.paragraphs
            for nested in cell.tables:
                yield from _paragraphs_in_table(nested)


def iter_all_paragraphs(document: Document):
    for paragraph in document.paragraphs:
        yield paragraph
    for table in document.tables:
        yield from _paragraphs_in_table(table)
    for section in document.sections:
        for container in (section.header, section.footer):
            for paragraph in container.paragraphs:
                yield paragraph
            for table in container.tables:
                yield from _paragraphs_in_table(table)


def replace_in_paragraph(paragraph: Paragraph, replacements: Mapping[str, str]) -> bool:
    changed = False
    for token, value in replacements.items():
        while True:
            run_texts = [run.text for run in paragraph.runs]
            full_text = "".join(run_texts)
            start = full_text.find(token)
            if start < 0:
                break
            end = start + len(token)

            run_starts: list[int] = []
            position = 0
            for text in run_texts:
                run_starts.append(position)
                position += len(text)
            start_index = next(
                (i for i, text in enumerate(run_texts) if text and run_starts[i] <= start < run_starts[i] + len(text)),
                None,
            )
            end_index = next(
                (i for i, text in enumerate(run_texts) if text and run_starts[i] < end <= run_starts[i] + len(text)),
                None,
            )
            if start_index is None or end_index is None:
                # This can only occur for unusual empty/run-boundary cases; retain
                # the old safe fallback rather than leave a visible placeholder.
                paragraph.runs[0].text = full_text.replace(token, value, 1)
                for run in paragraph.runs[1:]:
                    run.text = ""
                changed = True
                continue

            start_offset = start - run_starts[start_index]
            end_offset = end - run_starts[end_index]
            if start_index == end_index:
                run = paragraph.runs[start_index]
                run.text = run.text[:start_offset] + value + run.text[end_offset:]
            else:
                start_run = paragraph.runs[start_index]
                end_run = paragraph.runs[end_index]
                start_run.text = start_run.text[:start_offset] + value
                for index in range(start_index + 1, end_index):
                    paragraph.runs[index].text = ""
                end_run.text = end_run.text[end_offset:]
            changed = True
    return changed


def replace_placeholders(document: Document, replacements: Mapping[str, str]) -> None:
    for paragraph in iter_all_paragraphs(document):
        replace_in_paragraph(paragraph, replacements)


def find_questions_placeholder(document: Document) -> Paragraph | None:
    return next((paragraph for paragraph in document.paragraphs if "{{QUESTIONS}}" in "".join(run.text for run in paragraph.runs)), None)
