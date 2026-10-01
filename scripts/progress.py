"""Persisted stage state plus immediate stderr checkpoints for the active caller."""
import json,time,sys,datetime
from pathlib import Path
from qwen_mlx_asr import atomic_json
_started={}

def emit(workdir,phase,state='running',**details):
    workdir=Path(workdir);key=(str(workdir),phase);now=time.monotonic()
    if state=='running' and key not in _started:_started[key]=now
    path=workdir/'progress.json';data=json.loads(path.read_text()) if path.exists() else {'stages':{}}
    utc=datetime.datetime.now(datetime.timezone.utc)
    prior=data['stages'].get(phase,{})
    started=prior.get('started_utc') if prior.get('state')=='running' else None
    started=started or utc.isoformat()
    row={**prior,'phase':phase,'state':state,'utc':utc.isoformat(),'started_utc':started,'elapsed_seconds':round((utc-datetime.datetime.fromisoformat(started)).total_seconds(),3),**details}
    data['stages'][phase]=row;data['current']=row;atomic_json(path,data)
    with (workdir/'progress.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print('[bilibili checkpoint] '+json.dumps(row,ensure_ascii=False),file=sys.stderr,flush=True)
    return row
