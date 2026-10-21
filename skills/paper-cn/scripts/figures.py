"""抽取论文插图。

两个来源互补:
  - arXiv HTML 的 <img>:LaTeXML 能渲染的图(通常是照片/外部图片),直接下载
  - PDF 页面渲染:TikZ 等矢量图 LaTeXML 渲染不出来,只能从 PDF 裁

PDF 裁剪思路:用 pdftotext -bbox 拿到每个词的坐标,找到 "Figure N" 图注的位置,
图就在图注正上方那片没有文字的空白带里;空白带上沿即图的顶边。

用法:
    python3 figures.py html <paper.html> <arxiv_id> <输出目录>
    python3 figures.py pdf  <paper.pdf> <输出目录> [--only 2,3,4]
"""
import re
import subprocess
import sys
import time
from pathlib import Path

from lxml import etree, html as LH

DPI = 150
PT_PER_INCH = 72.0
# 行宽超过版心该比例即判定为正文行(插图内部的标注都远窄于此)
WIDE_FRAC = 0.55
# 行首 x 与版心左边距的容差(pt),超出即认为是插图内容而非正文
LEFT_TOL_PT = 4.0
# 裁剪区域低于该高度(pt)就不是真图注,而是以 "Figure N" 开头的正文句
MIN_FIGURE_PT = 40.0
# 顶边紧邻正文时往下让开的距离(pt),避免把正文末行切进来
BODY_CLEAR_PT = 5.0
# 图一直顶到页首时,往上多留的边距(pt)
TOP_PAD_PT = 6.0


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


# ---------- 来源一:arXiv HTML ----------

IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")


def is_image(path):
    return path.exists() and path.read_bytes()[:4].startswith(IMAGE_MAGIC)


def download(url, dst, tries=3):
    """arXiv 会对连续请求限流,失败时退避重试。"""
    for attempt in range(tries):
        try:
            run(["curl", "-sL", "--retry", "2", "-A", "Mozilla/5.0", url, "-o", str(dst)])
        except subprocess.CalledProcessError:
            pass
        if is_image(dst):
            return True
        time.sleep(1.5 * (attempt + 1))
    dst.unlink(missing_ok=True)
    return False


def from_html(html_path, arxiv_id, outdir):
    root = LH.parse(str(html_path)).getroot()
    outdir.mkdir(parents=True, exist_ok=True)
    saved = []
    for img in root.xpath('//figure//img[@src]'):
        src = img.get("src")
        if src.startswith(("/", "http")):
            continue  # 站点自身的图标/logo
        name = Path(src).name
        dst = outdir / name
        if not download(f"https://arxiv.org/html/{arxiv_id}/{name}", dst):
            print(f"  ✗ {name} 下载失败(限流或路径不对)")
            continue
        cap = img.xpath("ancestor::figure[1]//figcaption")
        label = cap[0].text_content().strip()[:60].replace("\n", " ") if cap else ""
        saved.append((name, label))
        print(f"  ✓ {name}  {label}")
    return saved


# ---------- 来源二:PDF 页面裁剪 ----------

def page_words(pdf, page):
    """返回该页所有词的 bbox 列表 [(xmin, ymin, xmax, ymax, text)],单位 pt。"""
    xml = run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), str(pdf), "-"])
    parser = etree.XMLParser(recover=True)
    tree = etree.fromstring(xml.encode(), parser)
    ns = {"x": tree.nsmap.get(None, "http://www.w3.org/1999/xhtml")}
    words = []
    for w in tree.iterfind(".//x:word", ns):
        words.append((float(w.get("xMin")), float(w.get("yMin")),
                      float(w.get("xMax")), float(w.get("yMax")),
                      (w.text or "").strip()))
    pg = tree.find(".//x:page", ns)
    return words, float(pg.get("width")), float(pg.get("height"))


def find_captions(pdf, n_pages):
    """扫全文,返回 {图号: (页码, 图注 yMin)}。

    只认「Figure N」出现在行首的情况。正文里的交叉引用(如 "as shown in
    Figure 5")是行中出现,必须排除,否则会定位到错误的页面。
    """
    candidates = {}
    for page in range(1, n_pages + 1):
        words, pw, _ = page_words(pdf, page)
        # 每行最左侧那个词的下标,用来判断行首
        row_first = {}
        for i, (x0, _, _, y1, _) in enumerate(words):
            key = round(y1)
            if key not in row_first or x0 < words[row_first[key]][0]:
                row_first[key] = i
        starts = set(row_first.values())
        for i, (_, ymin, _, _, text) in enumerate(words):
            if text != "Figure" or i not in starts:
                continue
            nxt = words[i + 1][4] if i + 1 < len(words) else ""
            m = re.match(r"(\d+)[:.]?$", nxt)
            if not m:
                continue
            # 正文里也可能有句子以「Figure 10 presents ...」开头,靠上方留白区分:
            # 真图注上面是插图(大片空白),正文句上面是紧挨着的正文行。
            height = ymin - figure_top(words, ymin, pw)
            candidates.setdefault(int(m.group(1)), []).append((height, page, ymin))
    return {num: (p, y) for num, lst in candidates.items()
            for h, p, y in [max(lst)] if h >= MIN_FIGURE_PT}


def group_rows(words):
    """把词按基线聚成行,返回 [(ytop, ybottom, x0, 行宽), ...],自上而下。"""
    rows = {}
    for x0, y0, x1, y1, _ in words:
        key = round(y1)
        r = rows.setdefault(key, [y0, y1, x0, x1])
        r[0], r[2], r[3] = min(r[0], y0), min(r[2], x0), max(r[3], x1)
    return [(v[0], v[1], v[2], v[3] - v[2]) for _, v in sorted(rows.items())]


def figure_top(words, cap_ymin, page_width):
    """定位插图顶边。

    判定正文行需要同时满足两条:横跨大半个版心,且从版心左边距起排。
    只看宽度会误伤——插图内部也可能有横跨整幅的元素(如时间轴条),
    但那些通常是居中或缩进的,不会贴着左边距。
    """
    rows = group_rows(words)
    if not rows:
        return 0.0
    margin = min(r[2] for r in rows)
    above = [r for r in rows if r[1] < cap_ymin - 1]
    top = cap_ymin
    for ytop, ybottom, x0, width in reversed(above):  # 自下而上
        is_body = width >= WIDE_FRAC * page_width and x0 <= margin + LEFT_TOL_PT
        if is_body:
            return ybottom + BODY_CLEAR_PT  # 撞到正文,顶边落在它下面
        top = ytop
    return max(0.0, top - TOP_PAD_PT)  # 一路到页首都没有正文,留点边距


def crop_figure(pdf, page, cap_ymin, out_png):
    words, pw, ph = page_words(pdf, page)
    top = figure_top(words, cap_ymin, pw)
    scale = DPI / PT_PER_INCH
    run(["pdftoppm", "-png", "-r", str(DPI),
         "-f", str(page), "-l", str(page),
         "-x", "0", "-y", str(int(top * scale)),
         "-W", str(int(pw * scale)), "-H", str(int((cap_ymin - top) * scale)),
         "-singlefile", str(pdf), str(out_png.with_suffix(""))])
    return out_png


def from_pdf(pdf_path, outdir, only=None):
    outdir.mkdir(parents=True, exist_ok=True)
    info = run(["pdfinfo", str(pdf_path)])
    n_pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    caps = find_captions(pdf_path, n_pages)
    print(f"PDF {n_pages} 页,定位到 {len(caps)} 个图注")
    saved = []
    for num in sorted(caps):
        if only and num not in only:
            continue
        page, ymin = caps[num]
        out = outdir / f"figure{num}.png"
        try:
            crop_figure(pdf_path, page, ymin, out)
            kb = out.stat().st_size // 1024
            print(f"  ✓ Figure {num} (p.{page}) → {out.name} {kb}KB")
            saved.append((out.name, f"Figure {num}"))
        except Exception as exc:
            print(f"  ✗ Figure {num} (p.{page}) 裁剪失败: {exc}")
    return saved


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    mode = sys.argv[1]
    if mode == "html":
        from_html(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
    elif mode == "pdf":
        only = None
        if "--only" in sys.argv:
            only = {int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")}
        from_pdf(Path(sys.argv[2]), Path(sys.argv[3]), only)
    else:
        sys.exit(__doc__)
