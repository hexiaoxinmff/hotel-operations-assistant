"""Versioned local workflow checks. This is not platform-wide access control."""
import argparse
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import uuid

ACTIONS={'research','metrics','ocr','office'}
def require_text(data,key):
    if not isinstance(data.get(key),str) or not data[key].strip():raise ValueError('Missing '+key)

def initial(task,requirement):
    if not task.strip() or not requirement.strip():raise ValueError('Task and requirement required')
    return {'schema':1,'task_id':uuid.uuid4().hex,'task':task,'requirement':requirement,'requirement_version':1,'plan_version':0,'requirement_confirmation':None,'plans':[],'selected_plan':None,'plan_confirmation':None,'phase':'requirement_pending','events':[]}

def transition(state,event,data):
    s=copy.deepcopy(state)
    if s.get('schema')!=1:raise ValueError('Unsupported workflow')
    phase=s['phase']
    if phase=='cancelled':raise ValueError('Cancelled task cannot resume; create a new task')
    if event=='revise_requirement':
        require_text(data,'requirement');s.update(requirement=data['requirement'],requirement_version=s['requirement_version']+1,requirement_confirmation=None,plans=[],selected_plan=None,plan_confirmation=None,phase='requirement_pending')
    elif event=='confirm_requirement':
        if phase!='requirement_pending':raise ValueError('Requirement confirmation not expected')
        if data.get('requirement_version')!=s['requirement_version']:raise ValueError('Stale requirement version')
        for k in ('quote','message_ref'):require_text(data,k)
        s.update(requirement_confirmation=data,phase='solution_research')
    elif event=='propose_plans':
        if phase not in ('solution_research','plan_pending','ready','executing','delivered'):raise ValueError('Confirm requirement first')
        plans=data.get('plans')
        if not isinstance(plans,list) or not plans:raise ValueError('At least one concrete plan required')
        ids=[]
        for plan in plans:
            for k in ('id','description','deliverables','constraints'):require_text(plan,k)
            if not isinstance(plan.get('actions'),list) or not plan['actions'] or not set(plan['actions'])<=ACTIONS:raise ValueError('Invalid plan actions')
            ids.append(plan['id'])
        if len(set(ids))!=len(ids):raise ValueError('Duplicate plan IDs')
        s.update(plans=plans,plan_version=s['plan_version']+1,selected_plan=None,plan_confirmation=None,phase='plan_pending')
    elif event=='confirm_plan':
        if phase!='plan_pending':raise ValueError('Plan selection not expected')
        if data.get('requirement_version')!=s['requirement_version'] or data.get('plan_version')!=s['plan_version']:raise ValueError('Stale selection')
        if data.get('plan_id') not in [x['id'] for x in s['plans']]:raise ValueError('Unknown plan')
        for k in ('quote','message_ref'):require_text(data,k)
        s.update(selected_plan=data['plan_id'],plan_confirmation=data,phase='ready')
    elif event=='start':
        check(s,data.get('action'),data.get('requirement_version'),data.get('plan_version'));s['phase']='executing'
    elif event=='deliver':
        if phase not in ('ready','executing'):raise ValueError('No approved execution')
        for k in ('output','verification'):require_text(data,k)
        s['phase']='delivered'
    elif event=='confirm_success':
        if phase!='delivered':raise ValueError('Deliver first')
        for k in ('quote','message_ref'):require_text(data,k)
        s['phase']='success_confirmed'
    elif event=='cancel':s['phase']='cancelled'
    else:raise ValueError('Unsupported event')
    s['events'].append({'event':event,'data':data});return s

def check(s,action,requirement_version,plan_version):
    if s.get('schema')!=1 or s.get('phase') not in ('ready','executing'):raise ValueError('Execution blocked: requirement and plan confirmations required')
    if s['requirement_version']!=requirement_version or s['plan_version']!=plan_version:raise ValueError('Execution blocked: stale versions')
    req=s.get('requirement_confirmation') or {};plan=s.get('plan_confirmation') or {}
    if req.get('requirement_version')!=requirement_version or plan.get('requirement_version')!=requirement_version or plan.get('plan_version')!=plan_version:raise ValueError('Execution blocked: invalid confirmations')
    for item in (req,plan):
        for k in ('quote','message_ref'):require_text(item,k)
    selected=next((x for x in s['plans'] if x['id']==s.get('selected_plan')),None)
    if not selected or action not in selected['actions']:raise ValueError('Action outside selected plan')
    return True

def require_execution(path,req,plan,action):
    if not path:raise ValueError('Missing --workflow; formal execution requires two confirmations')
    return check(json.loads(Path(path).read_text(encoding='utf-8')),action,req,plan)

def add_arguments(parser):
    parser.add_argument('--workflow');parser.add_argument('--requirement-version',type=int);parser.add_argument('--plan-version',type=int)

@contextmanager
def locked(path):
    lock=path.with_name(path.name+'.lock')
    with lock.open('x',encoding='utf-8') as f:f.write('workflow update')
    try:yield
    finally:lock.unlink()

def save(path,data):
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',required=True);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('init');a.add_argument('--task',required=True);a.add_argument('--requirement',required=True)
    a=sub.add_parser('event');a.add_argument('--event',required=True);a.add_argument('--payload',required=True)
    sub.add_parser('status');a=sub.add_parser('check');a.add_argument('--action',choices=sorted(ACTIONS),required=True);a.add_argument('--requirement-version',type=int,required=True);a.add_argument('--plan-version',type=int,required=True)
    args=p.parse_args();path=Path(args.state)
    try:
        if args.command=='status':result=json.loads(path.read_text(encoding='utf-8'))
        elif args.command=='check':result={'allowed':require_execution(path,args.requirement_version,args.plan_version,args.action)}
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with locked(path):
                if args.command=='init':
                    if path.exists():raise ValueError('Workflow exists; do not overwrite')
                    result=initial(args.task,args.requirement)
                else:result=transition(json.loads(path.read_text(encoding='utf-8')),args.event,json.loads(Path(args.payload).read_text(encoding='utf-8-sig')))
                save(path,result)
        print(json.dumps(result,ensure_ascii=True,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:print(json.dumps({'error':str(exc)},ensure_ascii=True));return 2
if __name__=='__main__':raise SystemExit(main())
