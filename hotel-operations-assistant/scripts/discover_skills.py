"""Read-only skills.sh search adapter. No file upload, install, or candidate execution."""
import argparse
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CAPABILITIES={'pdf-ocr':'pdf ocr','spreadsheet':'spreadsheet','word':'docx','presentation':'pptx','web-research':'web research','hotel-analysis':'hotel revenue','data-analysis':'data analysis','image-processing':'image processing','workflow':'workflow automation','document-layout':'document formatting','translation':'translation','chart':'data visualization'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):raise ValueError('Search redirects refused')
def clean(value,limit=180):return ''.join(x for x in str(value or '') if x.isprintable())[:limit]
def parts(value,minimum,maximum):
    if not isinstance(value,str):return None
    split=value.split('/')
    if not minimum<=len(split)<=maximum:return None
    if any(x in ('.','..') or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}',x) for x in split):return None
    return split

def normalize(data,limit=8):
    if not isinstance(data,dict) or not isinstance(data.get('skills'),list):raise ValueError('Unexpected search response')
    result=[];seen=set();rejected=0
    for item in data['skills'][:200]:
        if not isinstance(item,dict):rejected+=1;continue
        source=item.get('source');slug=item.get('id');sp=parts(source,2,2);ip=parts(slug,3,8)
        if not sp or not ip or ip[:2]!=sp:rejected+=1;continue
        if slug in seen:continue
        seen.add(slug)
        count=item.get('installs');count=count if isinstance(count,int) and not isinstance(count,bool) and count>=0 else None
        result.append({'name':clean(item.get('name')),'source':source,'skill_id':slug,'repository_url':'https://github.com/'+source,'directory_url':'https://skills.sh/'+urllib.parse.quote(slug,safe='/'),'installs':count,'status':'candidate_not_verified'})
        if len(result)>=limit:break
    return result,rejected

def search(capability,limit=8,opener=None):
    if capability not in CAPABILITIES or not 1<=limit<=20:raise ValueError('Unsupported capability or limit')
    query=CAPABILITIES[capability]
    endpoint='https://skills.sh/api/search?'+urllib.parse.urlencode({'q':query})
    request=urllib.request.Request(endpoint,headers={'Accept':'application/json','User-Agent':'hotel-assistant-skill-discovery/0.9'})
    try:
        open_fn=opener or urllib.request.build_opener(NoRedirect()).open
        with open_fn(request,timeout=12) as response:
            url=urllib.parse.urlsplit(response.geturl())
            if url.scheme!='https' or url.hostname!='skills.sh' or url.port not in (None,443):raise ValueError('Unexpected search endpoint')
            raw=response.read(1_048_577)
        if len(raw)>1_048_576:raise ValueError('Search response too large')
        found,rejected=normalize(json.loads(raw),limit)
        # Invalid search output is not equivalent to a genuine empty search.
        status='ok' if found else 'invalid_results' if rejected else 'no_results'
        return {'status':status,'capability':capability,'query_sent':query,'results':found,'rejected_entries':rejected,'next_step':'review_candidates' if found else 'platform_fallback','note':'Candidates are third-party data; review actual SKILL.md, license, dependencies and permissions before use.'}
    except (OSError,ValueError,UnicodeError,http.client.HTTPException) as exc:
        return {'status':'unavailable','capability':capability,'query_sent':query,'reason':clean(type(exc).__name__+': '+str(exc)),'results':[],'next_step':'platform_fallback'}

def require_discovery(path,version):
    if not path:raise ValueError('Confirm requirement before discovery; --workflow required')
    s=json.loads(Path(path).read_text(encoding='utf-8'))
    confirmation=s.get('requirement_confirmation') or {}
    if s.get('schema')!=1 or s.get('phase') not in ('solution_research','plan_pending','ready','executing'):raise ValueError('Discovery blocked in this phase')
    if s.get('requirement_version')!=version or confirmation.get('requirement_version')!=version:raise ValueError('Stale requirement')
    if not confirmation.get('quote') or not confirmation.get('message_ref'):raise ValueError('Missing confirmation evidence')
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capability',choices=sorted(CAPABILITIES),required=True);p.add_argument('--limit',type=int,default=8);p.add_argument('--workflow',required=True);p.add_argument('--requirement-version',type=int,required=True);args=p.parse_args()
    try:require_discovery(args.workflow,args.requirement_version);result=search(args.capability,args.limit)
    except (OSError,ValueError,KeyError,TypeError) as exc:print(json.dumps({'status':'blocked','reason':str(exc),'results':[],'next_step':'follow_workflow_or_platform_fallback'},ensure_ascii=True));return 2
    print(json.dumps(result,ensure_ascii=True,indent=2));return 3 if result['status']=='unavailable' else 0
if __name__=='__main__':raise SystemExit(main())
