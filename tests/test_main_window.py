import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from exam_formatter.gui.main_window import GiftFileDialog, MainWindow


def test_metadata_controls_have_requested_values():
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.exam_name.currentText() == "Preliminary Examination"
    assert [window.semester.itemText(index) for index in range(window.semester.count())] == ["1st Semester", "2nd Semester", "Term Break"]
    assert window.date.calendarPopup()
    assert window.metadata()["DATE"]
    application.quit()


def test_gift_file_dialog_preserves_selected_order(tmp_path):
    application = QApplication.instance() or QApplication([])
    first, second = tmp_path / "first.gift", tmp_path / "second.gift"
    first.write_text("First", encoding="utf-8")
    second.write_text("Second", encoding="utf-8")
    dialog = GiftFileDialog()
    dialog.path_inputs[0].setText(str(first))
    dialog.add_file_row()
    dialog.path_inputs[1].setText(str(second))
    assert dialog.combined_text() == "First\n\nSecond"
    application.quit()
