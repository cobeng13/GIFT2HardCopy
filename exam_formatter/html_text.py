"""Convert supported LMS HTML fragments to plain text without rendering media."""
from lxml import etree, html


class HtmlContentError(ValueError):
    """HTML content cannot be represented safely by the exam text model."""


_BLOCK_TAGS = frozenset({"div", "p"})
_LIST_TAGS = frozenset({"ul", "ol"})
_INLINE_TAGS = frozenset({"span", "b", "strong", "i", "em", "u", "sub", "sup", "a", "code", "s", "del"})
_RICH_TAGS = frozenset({"img", "table", "math", "svg", "audio", "video", "iframe", "object", "embed", "canvas"})



def _append_html(node, output: list[str]) -> None:
    tag = node.tag.lower() if isinstance(node.tag, str) else ""
    if tag in _RICH_TAGS or tag not in _BLOCK_TAGS | _LIST_TAGS | _INLINE_TAGS | {"div", "br", "li"}:
        raise HtmlContentError(f"unsupported rich HTML element <{tag}>.")
    semantic_markup = " ".join((node.get("class", ""), node.get("id", ""))).lower()
    if "mathjax" in semantic_markup or "equation" in semantic_markup:
        raise HtmlContentError("unsupported equation content in Moodle HTML.")
    if tag in _BLOCK_TAGS | _LIST_TAGS and output and not output[-1].endswith("\n"):
        output.append("\n")
    if tag == "li":
        if output and not output[-1].endswith("\n"):
            output.append("\n")
        output.append("- ")
    if tag == "br":
        output.append("\n")
    if node.text:
        output.append(node.text)
    for child in node:
        _append_html(child, output)
        if child.tail:
            output.append(child.tail)
    if tag in _BLOCK_TAGS | _LIST_TAGS | {"li"} and (not output or not output[-1].endswith("\n")):
        output.append("\n")


def html_to_text(raw: str) -> str:
    try:
        root = html.fragment_fromstring(raw, create_parent="div")
    except (etree.ParserError, ValueError) as error:
        raise HtmlContentError(f"invalid HTML content: {error}") from error
    output: list[str] = []
    if root.text:
        output.append(root.text)
    for child in root:
        _append_html(child, output)
        if child.tail:
            output.append(child.tail)
    lines = [" ".join(line.split()) for line in "".join(output).splitlines()]
    return "\n".join(line for line in lines if line).strip()
