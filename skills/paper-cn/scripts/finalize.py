"""把逐章翻译的中间稿合成单文件成稿,并校验 Obsidian vault 的格式硬规则。

用法:
    python3 finalize.py <章节目录> <输出.md> --title "中文标题" [--meta "元信息|多行用竖线分隔"]

约定:
  - 章节文件按文件名排序,建议 01-*.md、02-*.md……
  - 每个文件内 `#` = 章、`##` = 节、`###` = 小节,合成时整体降一级
  - 脚注定义 `[^n]: ...` 可写在任意章节文件里,会被集中搬到文末

做四件事:合并并统一层级 → 删参考文献编号 → 校验格式 → 报告统计。
"""
import argparse
import re
import sys
from pathlib import Path

# 参考文献编号:1~3 位数字(可含「; 」分隔多个),左邻是空格或右括号。
# 这样排除枚举序号「:(1)」「**(2) 标题**」、公式「`A_l`(4)」和年份「(2025)」。
CITATION = re.compile(r"(?: |(?<=\)))\((\d{1,3}(?:; ?\d{1,3})*)\) ?")
LATIN = re.compile(r"[A-Za-z0-9]")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]: .*$", re.M)
FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\](?!:)")


def _latin_side(text, pos, backward):
    """判断某侧是不是拉丁文本,决定删除后要不要补空格。

    左邻是「)」时看它闭合了什么:「(GRPO)」算拉丁,「(模型崩溃)」算中文。
    """
    ch = text[pos] if 0 <= pos < len(text) else ""
    if not ch:
        return False
    if ch == ")" and backward:
        open_at = text.rfind("(", max(0, pos - 60), pos)
        return bool(open_at != -1 and LATIN.search(text[open_at + 1:pos]))
    return bool(LATIN.match(ch))


def strip_citations(text):
    def sub(m):
        left = _latin_side(text, m.start() - 1, backward=True)
        right = _latin_side(text, m.end(), backward=False)
        return " " if (left or right) else ""

    return CITATION.subn(sub, text)


def demote_headings(text):
    return re.sub(r"^(#+) ", r"#\1 ", text, flags=re.M)


def collect_footnotes(text):
    """抽走正文里的脚注定义,返回(去掉定义的正文, 定义列表)。"""
    defs = FOOTNOTE_DEF.findall(text)
    bodies = [m.group(0) for m in FOOTNOTE_DEF.finditer(text)]
    return FOOTNOTE_DEF.sub("", text), bodies, defs


def build_header(title, meta):
    lines = [f"# {title}", ""]
    if meta:
        lines += [f"> {part.strip()}" for part in meta.split("|")] + [""]
    return "\n".join(lines + ["---", ""])


CODE_SPAN = re.compile(r"`[^`]*`")


def validate(text):
    """检查 Obsidian vault 硬规则,返回问题列表。

    反引号代码段内的 $ 是安全的(Obsidian 不会当作公式定界符),
    货币金额如 `$5.5M` 应写在反引号里,校验时先剥掉再查。
    """
    problems = []

    inline = [
        f"第 {i} 行: {ln.strip()[:70]}"
        for i, ln in enumerate(text.splitlines(), 1)
        if "$" in CODE_SPAN.sub("", ln) and ln.strip() != "$$"
    ]
    if inline:
        problems.append(
            "发现裸露的 $(vault 会当成公式定界符,不渲染)。\n"
            "    数学符号改用反引号 Unicode(`n_hc`),货币金额加反引号(`$5.5M`):\n    "
            + "\n    ".join(inline[:5]))

    fences = sum(1 for ln in text.splitlines() if ln.strip() == "$$")
    if fences % 2:
        problems.append(f"$$ 公式块未配对:共 {fences} 行,应为偶数")

    refs = set(FOOTNOTE_REF.findall(text))
    defs = set(FOOTNOTE_DEF.findall(text))
    if refs - defs:
        problems.append(f"脚注有引用无定义: {sorted(refs - defs)}")
    if defs - refs:
        problems.append(f"脚注有定义无引用: {sorted(defs - refs)}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapters_dir")
    ap.add_argument("output")
    ap.add_argument("--title", required=True)
    ap.add_argument("--meta", default="")
    args = ap.parse_args()

    files = sorted(Path(args.chapters_dir).glob("*.md"))
    if not files:
        sys.exit(f"{args.chapters_dir} 下没有 .md 章节文件")

    body = "\n\n".join(demote_headings(f.read_text(encoding="utf-8").strip())
                       for f in files)
    body, footnotes, _ = collect_footnotes(body)
    body, n_cites = strip_citations(body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    parts = [build_header(args.title, args.meta), body]
    if footnotes:
        parts.append("\n---\n\n## 脚注:歧义处的英文原文\n\n" + "\n".join(footnotes))
    text = "\n".join(parts).rstrip() + "\n"

    problems = validate(text)
    Path(args.output).write_text(text, encoding="utf-8")

    print(f"合并 {len(files)} 个章节文件 → {args.output}")
    print(f"行数 {len(text.splitlines())} · 删除引用编号 {n_cites} 处 · 脚注 {len(footnotes)} 条")
    if problems:
        print("\n⚠️ 格式问题(已写入,但需修复):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("✅ 格式校验通过")


if __name__ == "__main__":
    main()
