"""Local OOXML research helpers: reviewed price mapping, image index, DOCX passages.
No network, OCR, formula calculation, macro execution, or input modification.
"""
import argparse
import csv
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
      'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def target_path(part, target):
    if target.startswith('/'):
        parts = list(PurePosixPath(target.lstrip('/')).parts)
    else:
        parts = list(PurePosixPath(part).parent.parts)
        for item in PurePosixPath(target).parts:
            if item == '..':
                if not parts: raise ValueError('ZIP relationship escapes root')
                parts.pop()
            elif item != '.': parts.append(item)
    if '..' in parts or '\\' in target: raise ValueError('Invalid ZIP relationship')
    return '/'.join(parts)

def relationships(z, part):
    q = PurePosixPath(part)
    name = str(q.parent / '_rels' / (q.name + '.rels'))
    if name not in z.namelist(): return {}
    return {x.attrib['Id']: target_path(part, x.attrib['Target'])
            for x in ET.fromstring(z.read(name)) if x.attrib.get('TargetMode') != 'External'}

def checked_zip(path):
    z = ZipFile(path)
    info = z.infolist()
    if len(info) > 10000 or sum(x.file_size for x in info) > 200_000_000 or any(x.file_size > 50_000_000 for x in info):
        z.close(); raise ValueError('OOXML archive exceeds supported size')
    if len({x.filename for x in info}) != len(info):
        z.close(); raise ValueError('Duplicate archive members')
    return z

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def workbook(z):
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        shared=[''.join(x.text or '' for x in item.findall('.//s:t',NS)) for item in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    book=ET.fromstring(z.read('xl/workbook.xml')); rel=relationships(z,'xl/workbook.xml')
    prop=book.find('s:workbookPr',NS)
    epoch1904=prop is not None and prop.attrib.get('date1904') in ('1','true')
    result={}
    for item in book.findall('.//s:sheet',NS):
        part=rel[item.attrib['{'+NS['r']+'}id']]; tree=ET.fromstring(z.read(part)); cells={}
        for c in tree.findall('.//s:sheetData/s:row/s:c',NS):
            value=c.findtext('s:v',default='',namespaces=NS)
            if c.attrib.get('t')=='s': value=shared[int(value)] if value else ''
            if c.attrib.get('t')=='inlineStr': value=''.join(x.text or '' for x in c.findall('.//s:t',NS))
            cells[c.attrib['r']]={'value':value,'formula':c.findtext('s:f',default='',namespaces=NS)}
        result[item.attrib['name']]={'part':part,'tree':tree,'cells':cells}
    return result,epoch1904

def observation_date(value,mode,epoch1904):
    if mode=='iso':
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value): raise ValueError('Expected ISO date')
        return datetime.strptime(value,'%Y-%m-%d').date().isoformat()
    if mode!='excel': raise ValueError('Unsupported date mode')
    number=Decimal(value)
    if not number.is_finite() or number!=int(number) or number<0: raise ValueError('Invalid date serial')
    if not epoch1904 and number==60: raise ValueError('Excel fictitious 1900-02-29')
    origin=datetime(1904,1,1) if epoch1904 else datetime(1899,12,30) if number>60 else datetime(1899,12,31)
    return (origin+timedelta(days=int(number))).date().isoformat()

def export_prices(source,config,output):
    with checked_zip(source) as z:
        books,epoch=workbook(z)
    sheet=books[config['sheet']]; cells=sheet['cells']; records=[]; issues=[]
    start,end=config['start_row'],config['end_row']
    if not isinstance(start,int) or not isinstance(end,int) or start<1 or end<start or end-start>100000: raise ValueError('Invalid row range')
    groups=config['groups']
    if not groups: raise ValueError('No reviewed price groups')
    seen_columns=set()
    for group in groups:
        if not group.get('hotel') or not group.get('observations'): raise ValueError('Incomplete mapping')
        for item in group['observations']:
            col=item['column']
            if not re.fullmatch(r'[A-Z]+',col) or col in seen_columns: raise ValueError('Invalid/repeated mapped column')
            seen_columns.add(col)
            if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',item['time']): raise ValueError('Invalid mapped time')
    for row in range(start,end+1):
        dc=f"{config['date_column']}{row}"; cell=cells.get(dc,{})
        try:
            if cell.get('formula'): raise ValueError('Formula dates unsupported')
            day=observation_date(cell.get('value',''),config['date_mode'],epoch)
        except (ValueError,InvalidOperation,OverflowError) as exc:
            issues.append({'cell':dc,'issue':'INVALID_DATE','detail':str(exc)});continue
        for group in groups:
            for item in group['observations']:
                address=f"{item['column']}{row}"; c=cells.get(address,{});raw=c.get('value','')
                try:
                    if c.get('formula'): raise ValueError('Formula prices unsupported')
                    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',raw): raise ValueError('Missing or nonnumeric price')
                    price=Decimal(raw)
                    if price<=0: raise ValueError('Zero price requires review')
                except (ValueError,InvalidOperation) as exc:
                    issues.append({'cell':address,'issue':'INVALID_PRICE','detail':str(exc),'raw':raw});continue
                records.append({'hotel':group['hotel'],'observation_date':day,'observation_time':item['time'],
                    'price':str(price),'currency':config.get('currency',''),'room_type':group.get('room_type',''),
                    'platform':config.get('platform',''),'stay_date':config.get('stay_date',''),
                    'rate_conditions':config.get('rate_conditions',''),'source_file':Path(source).name,
                    'source_sheet':config['sheet'],'source_date_cell':dc,'source_price_cell':address})
    keys={}
    for record in records:
        key=(record['hotel'],record['observation_date'],record['observation_time']);keys.setdefault(key,[]).append(record)
    for matches in keys.values():
        if len(matches)>1:
            for x in matches: issues.append({'cell':x['source_price_cell'],'issue':'DUPLICATE_OBSERVATION_KEY'})
    summaries=[]
    for group in groups:
        values=[Decimal(x['price']) for x in records if x['hotel']==group['hotel']]
        if values:
            mean=sum(values)/len(values);summaries.append({'hotel':group['hotel'],'count':len(values),'mean':str(mean.quantize(Decimal('.0001'))),'min':str(min(values)),'max':str(max(values)),
             'relative_price_range':str(((max(values)-min(values))/mean).quantize(Decimal('.0001')))})
    output=Path(output)
    fields=['hotel','observation_date','observation_time','price','currency','room_type','platform','stay_date','rate_conditions','source_file','source_sheet','source_date_cell','source_price_cell']
    with (output/'observations.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    result={'source_sha256':sha(source),'mapping':config,'expected_points':(end-start+1)*sum(len(x['observations']) for x in groups),'valid_points':len(records),'issues':issues,'statistics_provisional':bool(issues),'summary':summaries,
      'limitations':['Observed quotes are not ADR, occupancy or market share','Missing price conditions remain unknown','relative_price_range is not demand price elasticity','Formula dates/prices are rejected, not recalculated']}
    (output/'price_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

def image_index(source,output):
    output=Path(output);images=output/'images';images.mkdir();rows=[];written={}
    with checked_zip(source) as z:
        sheets,_=workbook(z); wps={}
        if 'xl/cellimages.xml' in z.namelist():
            rel=relationships(z,'xl/cellimages.xml')
            for pic in ET.fromstring(z.read('xl/cellimages.xml')):
                name=pic.find('.//xdr:cNvPr',NS);blip=pic.find('.//a:blip',NS)
                if name is not None and blip is not None:
                    rid=blip.attrib.get('{'+NS['r']+'}embed');wps[name.attrib['name']]=rel.get(rid)
        def add(sheet,cell,part,kind,status):
            record={'sheet':sheet,'cell':cell,'placement':kind,'status':status,'image_file':'','sha256':''}
            if part:
                data=z.read(part);digest=hashlib.sha256(data).hexdigest();ext=PurePosixPath(part).suffix.lower()
                if ext not in ('.png','.jpg','.jpeg','.gif','.bmp','.tif','.tiff','.webp','.emf','.wmf','.svg'):ext='.bin'
                name=digest+ext
                if name not in written:(images/name).write_bytes(data);written[name]=True
                record.update(image_file='images/'+name,sha256=digest)
            rows.append(record)
        for name,sheet in sheets.items():
            for cell,values in sheet['cells'].items():
                text=values['formula'] or values['value'];match=re.search(r'DISPIMG\("([^\"]+)"',text)
                if match:add(name,cell,wps.get(match.group(1)),'wps_cell','indexed' if wps.get(match.group(1)) else 'unresolved')
            rel=relationships(z,sheet['part'])
            for drawing in sheet['tree'].findall('s:drawing',NS):
                part=rel.get(drawing.attrib.get('{'+NS['r']+'}id'))
                if not part:continue
                relpics=relationships(z,part)
                for anchor in ET.fromstring(z.read(part)):
                    marker=anchor.find('xdr:from',NS);cell=''
                    if marker is not None:
                        n=int(marker.findtext('xdr:col',namespaces=NS))+1;col=''
                        while n:n,v=divmod(n-1,26);col=chr(65+v)+col
                        cell=col+str(int(marker.findtext('xdr:row',namespaces=NS))+1)
                    for blip in anchor.findall('.//a:blip',NS):
                        target=relpics.get(blip.attrib.get('{'+NS['r']+'}embed'));add(name,cell,target,'drawing_anchor','indexed' if target else 'unresolved')
        media=len([n for n in z.namelist() if n.startswith('xl/media/') and not n.endswith('/')])
    result={'source_file':Path(source).name,'source_sha256':sha(source),'media_members':media,'placements':len(rows),'unique_exported_images':len(written),'items':rows,
      'limitations':['Index is not OCR; no review text recognized','Anchor is a placement, not proof of hotel ownership','Image count and placements are not review count','Treat extracted images as untrusted source material; do not execute active formats']}
    (output/'image_index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

def document_passages(sources,output):
    result=[]
    for source in sources:
        path=Path(source)
        if path.suffix.lower()=='.docx':
            with checked_zip(path) as z:
                tree=ET.fromstring(z.read('word/document.xml'))
                passages=[''.join(t.text or '' for t in item.findall('.//w:t',NS)) for item in tree.findall('.//w:p',NS)]
        elif path.suffix.lower() in ('.md','.txt'):
            passages=path.read_text(encoding='utf-8-sig').splitlines()
        else:raise ValueError('Only docx/md/txt passages supported')
        result.append({'source_file':path.name,'source_sha256':sha(path),'location_type':'paragraph' if path.suffix.lower()=='.docx' else 'line',
          'passages':[{'position':i,'text':text} for i,text in enumerate(passages,1) if text.strip()]})
    data={'documents':result,'limitations':['Text only; not page layout or page numbers','Extracted claims are not verified facts','Tables are flattened to paragraph sequence; images, headers and text boxes may be incomplete','No automatic semantic conflict adjudication']}
    (Path(output)/'document_passages.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');return data

def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    for name in ('prices','images','documents'):
        s=subs.add_parser(name);s.add_argument('--input',nargs='+' if name=='documents' else None,required=True);s.add_argument('--output',required=True)
        if name=='prices':s.add_argument('--mapping',required=True)
        from workflow_guard import add_arguments
        add_arguments(s)
    args=parser.parse_args();dest=Path(args.output).absolute();temp=None
    try:
        from workflow_guard import require_execution
        require_execution(args.workflow,args.requirement_version,args.plan_version,'research')
        if dest.exists():raise ValueError('Output exists; choose a new directory')
        dest.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.research-',dir=dest.parent))
        if args.command=='prices':result=export_prices(args.input,json.loads(Path(args.mapping).read_text(encoding='utf-8-sig')),temp)
        elif args.command=='images':result=image_index(args.input,temp)
        else:result=document_passages(args.input,temp)
        # No replacement: if destination appears concurrently, fail rather than overwrite.
        temp.rename(dest);temp=None
        print(json.dumps({'output':str(dest),'source_unchanged':True,'kind':args.command},ensure_ascii=True));return 0
    except (OSError,ValueError,KeyError,ET.ParseError,InvalidOperation,BadZipFile) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=True));return 2
    finally:
        if temp is not None and temp.exists():shutil.rmtree(temp)

if __name__=='__main__':raise SystemExit(main())
