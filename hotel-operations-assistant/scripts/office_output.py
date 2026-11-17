"""Basic new-report fallback. Never edits an existing Office template."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
from toolkit import load_config, confined

def build(config,input_path,output_path,kind):
    source=confined(input_path,config['read_roots']);dest=confined(output_path,config['write_roots'],True)
    data=json.loads(source.read_text(encoding='utf-8-sig'))
    if not isinstance(data.get('title'),str):raise ValueError('Report title required')
    paragraphs=data.get('paragraphs',[]);table=data.get('table',[])
    if not all(isinstance(x,str) for x in paragraphs):raise ValueError('Paragraphs must be text')
    if table and (not all(isinstance(r,list) and len(r)==len(table[0]) for r in table) or len(table[0])>6):raise ValueError('Rectangular table of at most 6 columns required')
    if kind=='docx':
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        doc=Document();style=doc.styles['Normal'];style.font.name='宋体';style.font.size=Pt(10.5)
        style.element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')
        doc.add_heading(data['title'],0)
        for text in paragraphs:doc.add_paragraph(text)
        if table:
            t=doc.add_table(rows=0,cols=len(table[0]));t.style='Table Grid'
            for row in table:
                cells=t.add_row().cells
                for i,value in enumerate(row):cells[i].text=str(value)
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:doc.save(f)
    elif kind=='pdf':
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        font=Path(config.get('chinese_font','C:/Windows/Fonts/simsun.ttc'))
        if not font.is_file():raise ValueError('Configure a local Chinese TrueType font first')
        pdfmetrics.registerFont(TTFont('HotelChinese',str(font),subfontIndex=0))
        styles=getSampleStyleSheet()
        for name in ['Normal','Title']:styles[name].fontName='HotelChinese';styles[name].wordWrap='CJK';styles[name].leading=16 if name=='Normal' else 25
        story=[Paragraph(escape(data['title']),styles['Title']),Spacer(1,12)]
        for text in paragraphs:story.extend([Paragraph(escape(text),styles['Normal']),Spacer(1,8)])
        if table:
            cells=[[Paragraph(escape(str(x)),styles['Normal']) for x in row] for row in table]
            t=Table(cells,colWidths=[(A4[0]-80)/len(table[0])]*len(table[0]),repeatRows=1)
            t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E7EEF5')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(t)
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:SimpleDocTemplate(f,pagesize=A4,leftMargin=40,rightMargin=40,topMargin=40,bottomMargin=40).build(story)
    else:raise ValueError('Unsupported output type')
    return {'output':str(dest),'status':'GENERATED_REQUIRES_RENDER_REVIEW','format':kind}

def main():
    a=argparse.ArgumentParser();a.add_argument('--config');a.add_argument('--input',required=True);a.add_argument('--output',required=True);a.add_argument('--format',choices=['docx','pdf'],required=True);from workflow_guard import add_arguments, require_execution;add_arguments(a);args=a.parse_args()
    try:
        require_execution(args.workflow,args.requirement_version,args.plan_version,'office')
        r=build(load_config(args.config),args.input,args.output,args.format)
    except (OSError,ValueError,KeyError,ImportError) as e:print(json.dumps({'error':str(e)},ensure_ascii=True));return 2
    print(json.dumps(r,ensure_ascii=True));return 0
if __name__=='__main__':raise SystemExit(main())
