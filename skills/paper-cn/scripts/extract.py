"""把 arXiv 的 LaTeXML HTML 转成分块 JSON,公式无损还原为 LaTeX。

用法:
    python3 extract.py paper.html blocks.json

输出每块形如 {"kind": "para|heading|table|title", "section": "...", "text": "..."},
便于按章节分批翻译。会打印章节清单和正文词数,用来决定怎么切批次。
"""
import json
import re
import sys

from lxml import html as LH

DISPLAY_MATH_CLASSES = ("ltx_equation", "ltx_equationgroup")
HEADING_LEVELS = {"h2": 2, "h3": 3, "h4": 4, "h5": 5}


def math_to_latex(el):
    """LaTeXML 把原始 LaTeX 存在 alttext 属性里,优先取它。"""
    alt = el.get("alttext")
    return f"${alt}$" if alt else (el.text_content() or "")


def node_text(el):
    """递归取文本,遇到 math 节点还原 LaTeX,丢弃公式编号。"""
    if el.tag == "math":
        return math_to_latex(el)
    parts = [el.text or ""]
    for child in el:
        cls = child.get("class") or ""
        if child.tag == "math":
            parts.append(math_to_latex(child))
        elif "ltx_tag_equation" not in cls:
            parts.append(node_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def clean(text):
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def table_to_markdown(tbl):
    rows = []
    for tr in tbl.iter("tr"):
        cells = [clean(node_text(td)) for td in tr if td.tag in ("td", "th")]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    head = "| " + " | ".join(padded[0]) + " |"
    sep = "| " + " | ".join(["---"] * width) + " |"
    body = ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join([head, sep, *body])


def extract(path):
    tree = LH.parse(path).getroot()
    blocks = []
    section = "Front Matter"

    title = tree.find(".//head/title")
    if title is not None:
        blocks.append({"kind": "title", "section": section,
                       "text": clean(title.text_content())})

    for p in tree.xpath('//div[contains(@class,"ltx_abstract")]//p'):
        blocks.append({"kind": "para", "section": "Abstract",
                       "text": clean(node_text(p))})

    page = tree.xpath('//div[contains(@class,"ltx_page_content")]')
    scope = page[0] if page else tree

    for el in scope.iter():
        cls = el.get("class") or ""
        if el.tag in HEADING_LEVELS and "ltx_title" in cls:
            heading = clean(node_text(el))
            if not heading:
                continue
            level = HEADING_LEVELS[el.tag]
            if level == 2:
                section = heading
            blocks.append({"kind": "heading", "level": level,
                           "section": section, "text": heading})
        elif el.tag == "p" and "ltx_p" in cls:
            if el.xpath('ancestor::div[contains(@class,"ltx_abstract")]'):
                continue
            if el.xpath("ancestor::td | ancestor::th"):
                continue
            text = clean(node_text(el))
            if text:
                blocks.append({"kind": "para", "section": section, "text": text})
        elif el.tag == "table" and "ltx_tabular" in cls:
            if el.xpath('ancestor::table[contains(@class,"ltx_tabular")]'):
                continue
            md = table_to_markdown(el)
            if md:
                blocks.append({"kind": "table", "section": section, "text": md})
        elif el.tag == "table" and any(c in cls for c in DISPLAY_MATH_CLASSES):
            text = clean(node_text(el))
            if text:
                blocks.append({"kind": "equation", "section": section, "text": text})
    return blocks


def report(blocks):
    sections = []
    for b in blocks:
        if b["section"] not in sections:
            sections.append(b["section"])
    words = sum(len(b["text"].split()) for b in blocks if b["kind"] == "para")
    print(f"块数 {len(blocks)} · 章节 {len(sections)} · 正文词数≈{words}")
    print("\n章节清单(按此切批,每批 ≤5000 词):")
    for name in sections:
        chunk = [b for b in blocks if b["section"] == name]
        w = sum(len(b["text"].split()) for b in chunk if b["kind"] == "para")
        tables = sum(1 for b in chunk if b["kind"] == "table")
        extra = f" · {tables} 表" if tables else ""
        print(f"  [{len(chunk):3d} 块 · {w:5d} 词{extra}] {name}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("用法: extract.py <paper.html> <blocks.json>")
    result = extract(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    report(result)
