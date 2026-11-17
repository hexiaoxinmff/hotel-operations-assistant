"""Provide the generic skill guide. No hotel data or business execution."""
import argparse
from pathlib import Path
import shutil
import tempfile

ASSETS=Path(__file__).resolve().parents[1]/"assets"
def provide(output,rebuild=False):
    out=Path(output)
    if out.exists():raise ValueError("Output exists; choose a new file")
    if out.suffix.lower()!=".docx":raise ValueError("Output must be .docx")
    out.parent.mkdir(parents=True,exist_ok=True)
    if not rebuild:
        with (ASSETS/"hotel-assistant-user-guide.docx").open("rb") as src,out.open("xb") as dst:shutil.copyfileobj(src,dst)
        return out
    from docx import Document
    from docx.shared import Cm,Pt,RGBColor
    from docx.oxml.ns import qn
    doc=Document()
    section=doc.sections[0]
    section.page_width=Cm(21);section.page_height=Cm(29.7)
    section.top_margin=section.bottom_margin=Cm(2)
    section.left_margin=section.right_margin=Cm(2.2)
    for name,size in [("Normal",11),("Title",22),("Heading 1",16),("Heading 2",12)]:
        s=doc.styles[name];s.font.name="Microsoft YaHei";s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0)
        s.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"),"Microsoft YaHei")
        s.paragraph_format.space_after=Pt(7)
    doc.styles["Normal"].paragraph_format.line_spacing=1.2
    for line in (ASSETS/"user-guide.md").read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        if line.startswith("# "):doc.add_paragraph(line[2:],"Title")
        elif line.startswith("## "):doc.add_heading(line[3:],1)
        elif line.startswith("### "):doc.add_heading(line[4:],2)
        elif line.startswith("- "):doc.add_paragraph(line[2:],"List Bullet")
        else:doc.add_paragraph(line)
    doc.core_properties.author="";doc.core_properties.last_modified_by=""
    doc.core_properties.title="酒店运营助手使用教程"
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        p=Path(temp)/"guide.docx";doc.save(p)
        with p.open("rb") as src,out.open("xb") as dst:shutil.copyfileobj(src,dst)
    return out
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);p.add_argument("--rebuild",action="store_true");a=p.parse_args()
    try:print(provide(a.output,a.rebuild));return 0
    except (OSError,ValueError,ImportError) as e:print(str(e));return 2
if __name__=="__main__":raise SystemExit(main())

