"""Host-local capabilities routed by explicit config; no raw shell execution."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import socket
import subprocess
import sys

def load_config(path=None):
    path=Path(path or os.environ.get('HOTEL_ASSISTANT_TOOLS_CONFIG') or Path.home()/'HotelOperationsMemory/hotel-operations-assistant/tools.json')
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('version')!=1:raise ValueError('Unsupported tool configuration')
    return data

def confined(path,roots,write=False):
    path=Path(path).absolute()
    for p in [path,*path.parents]:
        if p.is_symlink():raise ValueError('Symlink paths not supported')
        if p.exists() and getattr(p.lstat(),'st_file_attributes',0)&1024:raise ValueError('Reparse paths not supported')
    resolved=path.resolve()
    if not any(resolved.is_relative_to(Path(root).resolve()) for root in roots):raise ValueError('Outside configured roots')
    if write and resolved.exists():raise ValueError('Refusing to overwrite existing output')
    return resolved

def list_files(config,path):
    root=confined(path,config['read_roots'])
    # List one directory; do not follow reparse points or recursively scan the computer.
    return [{'name':p.name,'kind':'directory' if p.is_dir() else 'file','bytes':p.stat().st_size if p.is_file() else None} for p in root.iterdir() if not p.is_symlink()]

def ocr(config,path):
    path=confined(path,config['read_roots'])
    if path.suffix.lower() not in ('.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'):raise ValueError('Only local raster images supported')
    # The OCR engine must not download or transmit data while processing images.
    def offline(*args,**kwargs):raise OSError('Network disabled during local OCR; provision models separately')
    socket.socket.connect=offline
    socket.create_connection=offline
    from rapidocr import RapidOCR
    engine=RapidOCR()
    result=engine(str(path))
    texts=getattr(result,'txts',None)
    scores=getattr(result,'scores',None)
    boxes=getattr(result,'boxes',None)
    def native(value):
        if value is None:return []
        return value.tolist() if hasattr(value,'tolist') else list(value)
    return {'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'texts':native(texts),'scores':native(scores),'boxes':native(boxes),'status':'OCR_DRAFT_REQUIRES_REVIEW','network':'blocked_by_wrapper'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config');sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('status')
    for name in ('list','read','ocr'):
        s=sub.add_parser(name);s.add_argument('path')
        if name=='ocr':
            s.add_argument('--output',required=True)
            from workflow_guard import add_arguments
            add_arguments(s)
    args=parser.parse_args()
    try:
        c=load_config(args.config)
        if args.action=='status':result={'config_loaded':True,'python_exists':Path(c['python']).is_file(),'office_python_exists':Path(c['office_python']).is_file(),'node_exists':Path(c['node']).is_file(),'artifact_modules_exist':Path(c['artifact_modules']).is_dir(),'pdftoppm_exists':Path(c['pdftoppm']).is_file(),'read_roots':c['read_roots'],'write_roots':c['write_roots'],'web_search':c['web_search']}
        elif args.action=='list':result=list_files(c,args.path)
        elif args.action=='read':
            p=confined(args.path,c['read_roots'])
            if p.stat().st_size>2_000_000:raise ValueError('Text too large; use structured reader')
            result={'path':str(p),'text':p.read_text(encoding='utf-8-sig')}
        else:
            from workflow_guard import require_execution
            require_execution(args.workflow,args.requirement_version,args.plan_version,'ocr')
            dest=confined(args.output,c['write_roots'],True);result=ocr(c,args.path);dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
            result={'output':str(dest),'status':'OCR_DRAFT_REQUIRES_REVIEW','lines':len(result['texts'])}
    except (OSError,ValueError,KeyError,ImportError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=True));return 2
    print(json.dumps(result,ensure_ascii=True,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
