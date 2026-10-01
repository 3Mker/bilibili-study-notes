"""Explicit segment review bound to source transcript and final note bytes."""
import hashlib,json,re
from pathlib import Path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def segments(workdir):
    text=(workdir/'transcript.md').read_text(encoding='utf-8')
    return re.findall(r'(?m)^\[([^\]]+)\]\s*(.*(?:\n(?!\[)[^\n]*)*)',text)
def create(workdir):
    rows=segments(workdir)
    if not rows: raise ValueError('No timestamped source segments')
    path=workdir/'coverage.json'
    if path.exists() or (workdir/"quality.json").exists(): raise FileExistsError('Coverage already exists; preserve review or explicitly remove it')
    path.write_text(json.dumps({'version':2,'transcript_sha256':sha(workdir/'transcript.md'),'note_sha256':None,'reviewer':None,'segments':[{'index':i,'timestamp':t,'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'decision':'pending','evidence':''} for i,(t,s) in enumerate(rows)]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    from quality import create as create_quality
    create_quality(workdir)
    return path

def validate(workdir):
    data=json.loads((workdir/'coverage.json').read_text())
    if data.get('transcript_sha256') != sha(workdir/'transcript.md') or data.get('note_sha256') != sha(workdir/'note.md'): raise ValueError('Coverage review must match current transcript and final note hashes')
    if not isinstance(data.get('reviewer'),str) or not data['reviewer'].strip(): raise ValueError('Coverage reviewer is required')
    expected=segments(workdir); rows=data.get('segments',[])
    if len(rows)!=len(expected): raise ValueError('Every source segment requires review')
    for i,((t,s),row) in enumerate(zip(expected,rows)):
        if row.get('index')!=i or row.get('timestamp')!=t or row.get('source_sha256')!=hashlib.sha256(s.encode()).hexdigest(): raise ValueError('Coverage source segment differs')
        if row.get('decision') not in ['included','omitted','mixed'] or not isinstance(row.get('evidence'),str) or not row['evidence'].strip(): raise ValueError('Record prose evidence and reasons for any omission for every segment')
    if data.get('version')==2:
        from quality import validate as validate_quality
        validate_quality(workdir)
    return len(rows)
