from copy import deepcopy
from docx.oxml.ns import qn
from .exceptions import TemplateContractError


def apply_question_numbering(paragraph) -> None:
    style_ppr = paragraph.style.element.pPr
    num_pr = style_ppr.find(qn("w:numPr")) if style_ppr is not None else None
    if num_pr is None:
        raise TemplateContractError("Required style 'Exam Question' does not contain a Word numbering definition.")
    paragraph._p.get_or_add_pPr().append(deepcopy(num_pr))
