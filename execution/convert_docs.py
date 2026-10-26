"""Convert Word (.docx) and PowerPoint (.pptx) files to Markdown so they can go into the store.

usage: python3 execution/convert_docs.py <file or folder> --out knowledge/<topic>

Standard library only. Text, headings and bullet lists come through; images, charts and layout do not.
--out is required: the .md files go into the AIOS, never next to the owner's originals. Existing .md files are never overwritten.
PDF: not handled here. Ask Claude to read the PDF (page by page) and write the Markdown.
Excel: export each sheet as CSV from Excel itself, then put the CSV in knowledge/.
"""
import re
import sys
import zipfile
from html import unescape
from pathlib import Path


def docx_to_md(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(unescape(t) for t in re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, re.S)).strip()
        if not text:
            continue
        style = re.search(r'<w:pStyle w:val="([^"]+)"', para)
        s = style.group(1).lower() if style else ""
        if s.startswith("heading") or s.startswith("titre") or s == "title":
            level = int(re.sub(r"\D", "", s) or 1)
            out.append("#" * min(level, 4) + " " + text)
        elif "<w:numPr>" in para or s.startswith("list"):
            out.append("- " + text)
        else:
            out.append(text)
    return "\n\n".join(out) + "\n"


def pptx_to_md(path: Path) -> str:
    z = zipfile.ZipFile(path)
    slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                    key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    out = []
    for name in slides:
        i = int(re.search(r"(\d+)", name.rsplit("/", 1)[1]).group(1))
        xml = z.read(name).decode("utf-8")
        paras = []
        for p in re.findall(r"<a:p>.*?</a:p>", xml, re.S):
            t = "".join(unescape(x) for x in re.findall(r"<a:t>(.*?)</a:t>", p, re.S)).strip()
            if t:
                paras.append(t)
        if paras:
            out.append(f"## Slide {i}: {paras[0]}\n\n" + "\n".join(f"- {p}" for p in paras[1:]))
    return "\n\n".join(out) + "\n"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_dir = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    if out_dir is not None and str(out_dir) in args:
        args.remove(str(out_dir))
    if not args or out_dir is None:
        sys.exit(__doc__)
    src = Path(args[0])
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.suffix.lower() in (".docx", ".pptx"))
    for f in files:
        if f.name.startswith("~$"):
            continue
        conv = {".docx": docx_to_md, ".pptx": pptx_to_md}.get(f.suffix.lower())
        if conv is None:
            print(f"skip (not .docx/.pptx): {f}")
            continue
        dest = out_dir / (f.stem + ".md")
        if dest.exists():
            print(f"exists, kept: {dest}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = conv(f)
        dest.write_text(f"# {f.stem}\n\n{body}" if not body.startswith("# ") else body, encoding="utf-8")
        print(f"wrote {dest} ({len(body.split())} words)")


if __name__ == "__main__":
    main()
