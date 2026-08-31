import argparse
from pathlib import Path
from exam_formatter.docx_engine.generator import generate_exam
from exam_formatter.gift.parser import parse_gift


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a DOCX exam from GIFT.")
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--gift", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exam-name", default="")
    parser.add_argument("--course", default="")
    parser.add_argument("--semester", default="")
    parser.add_argument("--academic-year", default="")
    parser.add_argument("--date", default="")
    args = parser.parse_args()
    key_path = generate_exam(args.template, args.output, {"EXAM_NAME": args.exam_name, "COURSE": args.course, "SEMESTER": args.semester, "ACADEMIC_YEAR": args.academic_year, "DATE": args.date}, parse_gift(args.gift.read_text(encoding="utf-8-sig")))
    print(f"Created: {args.output}")
    print(f"Answer key: {key_path}")


if __name__ == "__main__": main()
