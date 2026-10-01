"""Grounded content inventory. Quotes prove locations, not semantic accuracy."""
import json,re
from pathlib import Path
from coverage import sha,segments
KINDS={'event','person','argument','example','qualification','transition','conclusion','filler','advertisement','asr_debris'}
SUBSTANTIVE=KINDS-{'filler','advertisement','asr_debris'}

def create(workdir):
    path=workdir/'quality.json'
    if path.exists(): raise FileExistsError('Quality inventory exists; preserve it')
    data={'version':1,'transcript_sha256':sha(workdir/'transcript.md'),'note_sha256':None,'reviewer':None,'segments':[{'index':i,'inventory_reviewed':False,'items':[],'uncertainties_reviewed':False,'uncertainties':[]} for i,_ in enumerate(segments(workdir))]}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return path

def validate(workdir):
    d=json.loads((workdir/'quality.json').read_text());source=segments(workdir);note=(workdir/'note.md').read_text();body=note.split('## 完整转写',1)[-1]
    if d.get('version')!=1 or d.get('transcript_sha256')!=sha(workdir/'transcript.md') or d.get('note_sha256')!=sha(workdir/'note.md'): raise ValueError('Quality inventory is stale or unsupported')
    if not d.get('reviewer') or len(d.get('segments',[]))!=len(source):raise ValueError('Quality inventory needs reviewer and every source segment')
    for i,(row,(_,text)) in enumerate(zip(d['segments'],source)):
        if row.get('index')!=i or row.get('inventory_reviewed') is not True or row.get('uncertainties_reviewed') is not True or not row.get('items'): raise ValueError(f'Inventory/uncertainty review incomplete at segment {i}')
        for item in row['items']:
            kind=item.get('kind');sq=item.get('source_quote','');nq=item.get('note_quote','')
            if kind not in KINDS or not sq.strip() or sq not in text:raise ValueError(f'Invalid source item at segment {i}')
            if item.get('decision')=='included':
                if not nq.strip() or nq not in body:raise ValueError(f'Item missing from full prose at segment {i}')
            elif item.get('decision')=='omitted':
                if kind in SUBSTANTIVE or not item.get('reason','').strip():raise ValueError(f'Substantive item cannot be omitted at segment {i}; restore or resolve source ambiguity')
            else:raise ValueError(f'Pending item at segment {i}')
        for issue in row.get('uncertainties',[]):
            if issue.get('kind') not in {'person','year','quotation','number','claim','boundary'} or not issue.get('source_quote','').strip() or issue['source_quote'] not in text:raise ValueError(f'Invalid uncertainty at segment {i}')
            if issue.get('status')=='verified':
                if not issue.get('evidence','').strip():raise ValueError('Verified uncertainty needs inspected source evidence')
            elif issue.get('status')=='marked':
                if not issue.get('note_quote','').strip() or issue['note_quote'] not in note or not issue.get('reason','').strip():raise ValueError('Unresolved uncertainty must be visibly marked in note')
            else:raise ValueError(f'Unresolved uncertainty at segment {i}')
    return sum(len(r['items']) for r in d['segments'])

def audit(workdir):
    """Flag source years/quotes and boundary fragments for review, never auto-correct."""
    findings=[];note=(workdir/'note.md').read_text() if (workdir/'note.md').exists() else ''
    for i,(stamp,text) in enumerate(segments(workdir)):
        for m in re.finditer(r'(?:公元\s*)?\d{3,4}年|[“「]([^”」]{2,120})[”」]',text):
            token=m.group(0);findings.append({'index':i,'timestamp':stamp,'source_quote':token,'kind':'year' if token.endswith('年') else 'quotation','exact_text_present':token in note,'action':'Review against audio/frame or visibly mark uncertainty; wording may legitimately differ'})
        if i and text and text[0] not in '。！？':findings.append({'index':i,'timestamp':stamp,'kind':'boundary','source_quote':text[:32],'action':'Inspect previous tail and this head together; no automatic deletion'})
    try:count=validate(workdir);gate={'valid':True,'items':count}
    except (OSError,ValueError,KeyError,TypeError) as exc:gate={'valid':False,'error':str(exc)}
    report={'semantic_accuracy_proven':False,'gate':gate,'findings':findings};(workdir/'quality-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
