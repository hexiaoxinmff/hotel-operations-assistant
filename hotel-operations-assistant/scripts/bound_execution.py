"""Execute one approved local JSON job; approval evidence remains supplied by the host."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
from workflow_guard import check, locked, save
from professional_tools import OPERATIONS, import_csv

def digest(raw):return hashlib.sha256(raw).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()

def safe_path(value):
    if not isinstance(value,str) or not Path(value).is_absolute():raise ValueError("Absolute local path required")
    p=Path(value)
    for x in [p,*p.parents]:
        if x.exists() or x.is_symlink():
            attrs=getattr(x.lstat(),"st_file_attributes",0)
            if x.is_symlink() or attrs & getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",1024):raise ValueError("Reparse/symlink paths not supported")
    return p.resolve()

def inspect_job(raw):
    job=json.loads(raw)
    if job.get("schema")!=1 or job.get("operation") not in set(OPERATIONS)|{"import_csv"}:raise ValueError("Unknown job operation")
    files=job.get("input_files")
    expected={"data","csv"} if job["operation"]=="import_csv" else {"data"}
    if not isinstance(files,dict) or set(files)!=expected:raise ValueError("Unexpected input files")
    root=safe_path(job.get("output_root"));out=safe_path(job.get("output_file"))
    if out==root or not out.is_relative_to(root) or out.suffix.lower()!=".json":raise ValueError("Output outside approved root or not JSON")
    receipt=out.with_name(out.name+".receipt.json")
    paths=[]
    for spec in files.values():
        paths.append(safe_path(spec.get("path")))
        if not isinstance(spec.get("sha256"),str) or len(spec["sha256"])!=64:raise ValueError("Input SHA256 required")
    if out in paths or receipt in paths or out==receipt:raise ValueError("Input/output collision")
    return job,paths,out,receipt

def approved(state_path,req,plan,job_hash,action="metrics"):
    state=json.loads(Path(state_path).read_text(encoding="utf-8"))
    check(state,action,req,plan)
    selected=next(x for x in state["plans"] if x["id"]==state["selected_plan"])
    if job_hash not in selected.get("job_sha256",[]):raise ValueError("Job not bound to selected approved plan")
    return state["task_id"]

def execute(job_path,state_path,req,plan):
    raw=safe_path(str(Path(job_path).absolute())).read_bytes()
    job,paths,out,receipt=inspect_job(raw)
    action="research" if job["operation"] in ("facts","import_csv","handover") else "metrics"
    job_hash=digest(raw);task_id=approved(state_path,req,plan,job_hash,action)
    if out.exists() or receipt.exists():raise ValueError("Output/receipt exists; do not overwrite or silently retry")
    buffers={}
    for key,spec in job["input_files"].items():
        b=safe_path(spec["path"]).read_bytes()
        if digest(b)!=spec["sha256"]:raise ValueError("Input changed: "+key)
        buffers[key]=b
    # Keep an in-memory snapshot of input bytes; calculation never re-opens sources.
    data=json.loads(buffers["data"])
    out.parent.mkdir(parents=True,exist_ok=True)
    safe_path(str(out));safe_path(str(receipt))
    with locked(receipt):
        if out.exists() or receipt.exists():raise ValueError("Concurrent/already executed job")
        evidence={"schema":1,"task_id":task_id,"requirement_version":req,"plan_version":plan,"job_sha256":job_hash,"operation":job["operation"],"input_sha256":{k:digest(b) for k,b in buffers.items()},"started_at":now(),"status":"started","output":str(out)}
        with receipt.open("x",encoding="utf-8") as f:json.dump(evidence,f,ensure_ascii=False,indent=2)
        try:
            result=import_csv(data,buffers["csv"]) if job["operation"]=="import_csv" else OPERATIONS[job["operation"]](data)
            approved(state_path,req,plan,job_hash,action)
            if digest(safe_path(str(Path(job_path).absolute())).read_bytes())!=job_hash:raise ValueError("Job changed during execution")
            for key,spec in job["input_files"].items():
                if digest(safe_path(spec["path"]).read_bytes())!=spec["sha256"]:raise ValueError("Source changed during execution")
            safe_path(str(out))
            payload=json.dumps(result,ensure_ascii=False,indent=2).encode("utf-8")
            with out.open("xb") as f:f.write(payload);f.flush();os.fsync(f.fileno())
            evidence.update(status="completed",finished_at=now(),output_sha256=digest(out.read_bytes()),acceptance="pending_user_review")
            save(receipt,evidence)
            return evidence
        except Exception as exc:
            evidence.update(status="failed",finished_at=now(),error=str(exc),output_exists=out.exists())
            save(receipt,evidence)
            raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job",required=True);p.add_argument("--workflow",required=True)
    p.add_argument("--requirement-version",required=True,type=int);p.add_argument("--plan-version",required=True,type=int)
    a=p.parse_args()
    try:
        result=execute(a.job,a.workflow,a.requirement_version,a.plan_version)
        print(json.dumps(result,ensure_ascii=True,indent=2));return 0
    except (OSError,ValueError,TypeError,KeyError,StopIteration) as e:
        print(json.dumps({"error":str(e)},ensure_ascii=True));return 2
if __name__=="__main__":raise SystemExit(main())

