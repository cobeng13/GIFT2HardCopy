from pathlib import Path
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget)
from exam_formatter.docx_engine.generator import generate_exam
from exam_formatter.gift.exceptions import GiftParseError
from exam_formatter.gift.parser import parse_gift


class GiftFileDialog(QDialog):
    """Collect GIFT files in the order they should be appended."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load GIFT Files")
        self.resize(680, 220)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose one or more GIFT files in question order."))
        self.file_rows = QVBoxLayout()
        layout.addLayout(self.file_rows)
        self.path_inputs: list[QLineEdit] = []
        self.add_file_row()
        add_file = QPushButton("Add Another GIFT File")
        add_file.clicked.connect(self.add_file_row)
        layout.addWidget(add_file)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Load Files")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_file_row(self) -> None:
        number = len(self.path_inputs) + 1
        row = QHBoxLayout()
        row.addWidget(QLabel(f"Load GIFT File {number}:"))
        path_input = QLineEdit()
        path_input.setReadOnly(True)
        browse = QPushButton("Browse")
        browse.clicked.connect(lambda: self.choose_file(path_input))
        row.addWidget(path_input, 1)
        row.addWidget(browse)
        self.path_inputs.append(path_input)
        self.file_rows.addLayout(row)

    def choose_file(self, path_input: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select GIFT file", filter="GIFT files (*.gift *.txt)")
        if path:
            path_input.setText(path)

    def accept(self) -> None:
        if not self.paths:
            QMessageBox.warning(self, "Load GIFT Files", "Select at least one GIFT file.")
            return
        super().accept()

    @property
    def paths(self) -> list[Path]:
        return [Path(path_input.text()) for path_input in self.path_inputs if path_input.text()]

    def combined_text(self) -> str:
        return "\n\n".join(path.read_text(encoding="utf-8-sig") for path in self.paths)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Exam Formatter")
        self.resize(820, 680)
        root = QWidget()
        layout = QVBoxLayout(root)
        form = QFormLayout()
        self.template = QLineEdit()
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_template)
        template_row = QHBoxLayout(); template_row.addWidget(self.template); template_row.addWidget(browse)
        form.addRow("Master Template:", template_row)
        self.exam_name = QComboBox()
        self.exam_name.addItems(("Preliminary Examination", "Midterm Examination", "Final Examination"))
        self.course = QLineEdit()
        self.semester = QComboBox()
        self.semester.addItems(("1st Semester", "2nd Semester", "Term Break"))
        self.academic_year = QLineEdit()
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("MMMM d, yyyy")
        form.addRow("Exam Name:", self.exam_name)
        form.addRow("Course:", self.course)
        form.addRow("Semester:", self.semester)
        form.addRow("Academic Year:", self.academic_year)
        form.addRow("Date:", self.date)
        layout.addLayout(form)
        layout.addWidget(QLabel("GIFT Questions:"))
        self.gift_text = QTextEdit(); layout.addWidget(self.gift_text, 1)
        buttons = QHBoxLayout()
        load = QPushButton("Load GIFT File(s)"); load.clicked.connect(self.load_gift)
        validate = QPushButton("Validate GIFT"); validate.clicked.connect(self.validate_gift)
        generate = QPushButton("Generate Exam"); generate.clicked.connect(self.generate)
        for button in (load, validate, generate): buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QLabel("Ready."); layout.addWidget(self.status)
        self.setCentralWidget(root)

    def choose_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select master template", filter="Word documents (*.docx)")
        if path: self.template.setText(path)

    def load_gift(self) -> None:
        dialog = GiftFileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.gift_text.setPlainText(dialog.combined_text())
                self.status.setText(f"Loaded {len(dialog.paths)} GIFT file(s) in sequence.")
            except (OSError, UnicodeDecodeError) as error:
                self.show_error(f"Could not read selected GIFT file: {error}")

    def parsed_questions(self):
        questions = parse_gift(self.gift_text.toPlainText())
        self.status.setText(f"Valid GIFT: {len(questions)} question(s).")
        return questions

    def validate_gift(self) -> None:
        try: self.parsed_questions()
        except GiftParseError as error: self.show_error(str(error))

    def generate(self) -> None:
        try:
            questions = self.parsed_questions()
            template = Path(self.template.text())
            if not template.is_file(): raise ValueError("Select a valid master template.")
            path, _ = QFileDialog.getSaveFileName(self, "Save exam", filter="Word documents (*.docx)")
            if not path: return
            if not path.lower().endswith(".docx"): path += ".docx"
            key_path = generate_exam(template, Path(path), self.metadata(), questions)
            self.status.setText(f"Created exam and answer key: {path}")
            QMessageBox.information(
                self,
                "Exam Formatter",
                f"Exam created successfully.\n\nDOCX: {path}\nAnswer key: {key_path}",
            )
        except Exception as error:
            self.show_error(str(error))

    def metadata(self) -> dict[str, str]:
        return {
            "EXAM_NAME": self.exam_name.currentText(),
            "COURSE": self.course.text(),
            "SEMESTER": self.semester.currentText(),
            "ACADEMIC_YEAR": self.academic_year.text(),
            "DATE": self.date.date().toString("MMMM d, yyyy"),
        }

    def show_error(self, message: str) -> None:
        self.status.setText(f"Error: {message}")
        QMessageBox.critical(self, "Exam Formatter", message)
