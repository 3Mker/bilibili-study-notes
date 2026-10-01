#!/usr/bin/env python3
"""Bounded audio reads and atomic, source-bound Qwen checkpoints."""
from __future__ import annotations
import argparse, contextlib, fcntl, hashlib, json, math, os, subprocess, sys, time
from pathlib import Path

@contextlib.contextmanager
def job_lock(workdir, filename=".qwen.lock"):
    workdir.mkdir(parents=True, exist_ok=True)
    with (workdir / filename).open('a') as stream:
        try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another ASR job is using this workdir')
        yield stream.fileno()

def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def plan(wav, chunk_seconds):
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(wav) as stream:
        rate, count=stream.samplerate, len(stream)
        if rate != 16000 or stream.channels != 1: raise ValueError('Expected 16 kHz mono WAV')
        if count == 0: raise ValueError('Empty audio')
        cuts=[0]; target=chunk_seconds; duration=count/rate
        while target < duration:
            lo=max(cuts[-1]/rate+chunk_seconds*2/3, target-5)
            hi=min(duration-1,target+5)
            def energy(at):
                stream.seek(int(at*rate)); window=stream.read(int(.18*rate),dtype='float32')
                return float(np.mean(window*window)) if len(window) else math.inf
            candidates=np.arange(lo,hi,.25)
            cut=float(min(candidates,key=energy)) if len(candidates) else float(target)
            cuts.append(int(cut*rate)); target+=chunk_seconds
    return cuts+[count], rate

def transcribe(media: Path, workdir: Path, *, hotwords='', model_id=os.environ.get('BILIBILI_QWEN_MODEL', 'mlx-community/Qwen3-ASR-0.6B-bf16'), chunk_seconds=60):
    if not 10 <= chunk_seconds <= 90: raise ValueError('chunk_seconds must be between 10 and 90')
    media=media.resolve(); workdir=workdir.resolve()
    with job_lock(Path("/tmp") / f"bilibili-asr-{os.getuid()}") as host_fd, job_lock(workdir) as work_fd:
        wav=workdir/'audio.wav'; meta=workdir/'qwen_checkpoint.json'; checkpoint=workdir/'qwen_segments.jsonl'
        source_hash=digest(media)
        if meta.exists():
            old=json.loads(meta.read_text())
            if old.get('source_sha256') != source_hash: raise ValueError('Source differs; use a new workdir')
        elif checkpoint.exists():
            raise ValueError('Legacy checkpoint has no source identity; preserve it and use a new workdir')
        if media != wav:
            if not meta.exists() or not wav.exists():
                temp=workdir/'audio.partial.wav'
                subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(media),'-vn','-ar','16000','-ac','1','-c:a','pcm_s16le',str(temp)],check=True)
                os.replace(temp,wav)
        cuts,rate=plan(wav,chunk_seconds)
        identity={'version':2,'source_sha256':source_hash,'wav_sha256':digest(wav),'model':model_id,'hotwords':hotwords,'chunk_seconds':chunk_seconds,'cuts':cuts,'rate':rate}
        if meta.exists() and json.loads(meta.read_text()) != identity: raise ValueError('Audio or ASR configuration differs; use a new workdir')
        if not meta.exists(): atomic_json(meta,identity)
        rows=[]
        if checkpoint.exists():
            # Never silently discard a corrupt or incomplete checkpoint.
            rows=[json.loads(line) for line in checkpoint.read_text().splitlines()]
        saved={}
        for row in rows:
            index=row['index']
            if type(index) is not int or not 0 <= index < len(cuts)-1 or index in saved: raise ValueError('Invalid or duplicate checkpoint index')
            if row.get('start') != cuts[index]/rate or row.get('end') != cuts[index+1]/rate or row.get('model') != model_id or not row.get('text','').strip(): raise ValueError('Invalid checkpoint segment')
            saved[index]=row
        from progress import emit
        emit(workdir,"transcription",completed=len(saved),total=len(cuts)-1)
        for index,(start,end) in enumerate(zip(cuts[:-1],cuts[1:])):
            if index in saved: continue
            emit(workdir,"transcription",completed=len(saved),total=len(cuts)-1,next_segment=index)
            result_path=workdir/'qwen_worker_result.json'
            result_path.unlink(missing_ok=True)
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(wav),str(result_path),str(index),str(start),str(end),model_id,hotwords],check=True,pass_fds=(host_fd,work_fd))
            row=json.loads(result_path.read_text())
            if not row['text'].strip(): raise ValueError(f'Empty ASR segment {index}; checkpoint retained')
            saved[index]=row
            temp=checkpoint.with_suffix('.jsonl.tmp')
            with temp.open('w',encoding='utf-8') as stream:
                for key in sorted(saved): stream.write(json.dumps(saved[key],ensure_ascii=False)+'\n')
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temp,checkpoint); result_path.unlink()
            print(json.dumps({'completed':len(saved),'total':len(cuts)-1,'start':row['start'],'end':row['end'],'resources':row.get('resources')},ensure_ascii=False),flush=True)
        from progress import emit
        emit(workdir,"transcription","completed",completed=len(saved),total=len(cuts)-1)
        ordered=[saved[index] for index in range(len(cuts)-1)]
        text='\n'.join(f"[{int(r['start'])//3600:02d}:{int(r['start'])//60%60:02d}:{int(r['start'])%60:02d}] {r['text']}" for r in ordered)+'\n'
        (workdir/'transcript_qwen.md').write_text(text,encoding='utf-8')
        return ordered

def worker(wav,output,index,start,end,model_id,hotwords):
    import resource
    import soundfile as sf
    from qwen3_asr_mlx import Qwen3ASR
    import mlx.core as mx
    began=time.monotonic()
    with sf.SoundFile(wav) as stream:
        rate=stream.samplerate; stream.seek(start); audio=stream.read(end-start,dtype='float32')
    with Qwen3ASR.from_pretrained(model_id) as model:
        result=model.transcribe(audio,language='Chinese',context=f'Vocabulary: {hotwords}' if hotwords else None)
        peak=mx.get_peak_memory() if hasattr(mx,'get_peak_memory') else None
    row={'index':index,'start':start/rate,'end':end/rate,'text':result.text.strip(),'language':result.language,'model':model_id,'resources':{'wall_seconds':time.monotonic()-began,'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'mlx_peak_bytes':peak}}
    atomic_json(output,row)

def main():
    if len(sys.argv)==9 and sys.argv[1]=='--worker':
        worker(Path(sys.argv[2]),Path(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),int(sys.argv[6]),sys.argv[7],sys.argv[8]); return
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('media',type=Path); parser.add_argument('--workdir',type=Path,required=True); parser.add_argument('--hotwords',default=''); parser.add_argument('--model',default=os.environ.get('BILIBILI_QWEN_MODEL', 'mlx-community/Qwen3-ASR-0.6B-bf16')); parser.add_argument('--chunk-seconds',type=int,default=60)
    args=parser.parse_args(); transcribe(args.media.expanduser(),args.workdir.expanduser(),hotwords=args.hotwords,model_id=args.model,chunk_seconds=args.chunk_seconds)
if __name__=='__main__': main()
