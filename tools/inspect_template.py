import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docx import Document
from exam_formatter.docx_engine.placeholders import iter_all_paragraphs


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("template", type=Path); args = parser.parse_args()
    document = Document(args.template)
    for index, section in enumerate(document.sections, 1):
        print(f"Section {index}: {section.page_width}x{section.page_height}; margins L={section.left_margin} R={section.right_margin} T={section.top_margin} B={section.bottom_margin}")
    print("Paragraph styles:")
    for style in document.styles:
        if style.type == 1: print(f"  {style.name}")
    print("Table styles:")
    for style in document.styles:
        if style.type == 3: print(f"  {style.name}")
    print("Placeholder locations:")
    for paragraph in iter_all_paragraphs(document):
        if "{{" in paragraph.text: print(f"  [{paragraph.style.name}] {paragraph.text}")
    print("Numbering styles:")
    for style in document.styles:
        if style.type == 1 and style.element.pPr is not None and style.element.pPr.numPr is not None: print(f"  {style.name}")


if __name__ == "__main__": main()
