"""Review boundaries without deleting text or changing the 60s ASR strategy."""
import json,hashlib
from pathlib import Path

def inspect(workdir):
    path=workdir/'qwen_segments.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()]
    findings=[]
    for left,right in zip(rows,rows[1:]):
        tail=left['text'][-80:];head=right['text'][:80]
        matches=[tail[-n:] for n in range(2,min(len(tail),len(head))+1) if tail[-n:]==head[:n]]
        findings.append({'left_index':left['index'],'right_index':right['index'],'boundary_seconds':left['end'],'listen_start_seconds':max(0,left['end']-3),'listen_end_seconds':right['start']+3,'tail':tail,'head':head,'exact_repeat_candidate':max(matches,key=len) if matches else None,'requires_review':True,'action':'Listen across boundary and retain legitimate repeated speech. Matching text alone never authorizes deletion.'})
    result={'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'overlap_enabled':False,'automatic_deletion':False,'boundaries':findings};(workdir/'boundary-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
