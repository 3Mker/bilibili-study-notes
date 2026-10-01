import unittest,tempfile,sys,json,os,hashlib
from pathlib import Path
from unittest.mock import patch
from argparse import Namespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import qwen_mlx_asr as asr, coverage, video_pipeline as pipeline

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); self.work=self.root/'work'; self.work.mkdir(); self.uid_patch=patch.object(asr.os,'getuid',return_value=987123); self.uid_patch.start()
 def tearDown(self): self.uid_patch.stop(); self.temp.cleanup()
 def audio(self):
  import soundfile as sf, numpy as np
  media=self.work/'audio.wav'; sf.write(media,np.zeros(16000*21),16000); return media
 def fake_worker(self,args,check,**kwargs):
  output=Path(args[4]); index,start,end=int(args[5]),int(args[6]),int(args[7]); asr.atomic_json(output,{'index':index,'start':start/16000,'end':end/16000,'text':'短样本内容','model':args[8]})
 def test_resume_and_configuration_binding(self):
  media=self.audio()
  with patch.object(asr.subprocess,'run',side_effect=self.fake_worker) as run:
   asr.transcribe(media,self.work,chunk_seconds=10); self.assertGreater(run.call_count,0)
   run.reset_mock(); asr.transcribe(media,self.work,chunk_seconds=10); self.assertEqual(run.call_count,0)
   with self.assertRaises(ValueError): asr.transcribe(media,self.work,chunk_seconds=10,hotwords='新词')
   media.write_bytes(b'changed')
   with self.assertRaises(ValueError): asr.transcribe(media,self.work,chunk_seconds=10)
 def test_worker_failure_resumes(self):
  media=self.audio(); completed=0
  def fail(args,check,**kwargs):
   nonlocal completed
   if completed: raise RuntimeError('interrupted')
   completed+=1; self.fake_worker(args,check)
  with patch.object(asr.subprocess,'run',side_effect=fail):
   with self.assertRaises(RuntimeError): asr.transcribe(media,self.work,chunk_seconds=10)
  with patch.object(asr.subprocess,'run',side_effect=self.fake_worker) as run:
   rows=asr.transcribe(media,self.work,chunk_seconds=10); self.assertEqual(run.call_count,len(rows)-1)
 def test_lock(self):
  with asr.job_lock(self.work):
   with self.assertRaises(RuntimeError):
    with asr.job_lock(self.work): pass
 def test_child_retains_lock_after_parent_context_closes(self):
  import subprocess
  with asr.job_lock(self.work) as fd:
   child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(.3)'],pass_fds=(fd,))
  try:
   with self.assertRaises(RuntimeError):
    with asr.job_lock(self.work): pass
  finally: child.wait()
  with asr.job_lock(self.work): pass
 def test_corrupt_checkpoint_refused(self):
  media=self.audio()
  with patch.object(asr.subprocess,'run',side_effect=self.fake_worker): asr.transcribe(media,self.work,chunk_seconds=10)
  (self.work/'qwen_segments.jsonl').write_text('{bad')
  with self.assertRaises(json.JSONDecodeError): asr.transcribe(media,self.work,chunk_seconds=10)
 def test_short_vtt_timestamps(self):
  subtitle=self.work/'subtitle.zh.vtt'; subtitle.write_text('WEBVTT\n\n00:01.000 --> 00:03.000\n中文字幕\n')
  rows=pipeline.parse_subtitle(subtitle); self.assertEqual(rows,[{'start':1.0,'end':3.0,'text':'中文字幕'}])
 def test_prepare_request_binding(self):
  args=Namespace(workdir=self.work,url='https://www.bilibili.com/video/BV0000000000/',hotwords='',chunk_seconds=60,series_part=None,browser=None)
  with patch.object(pipeline,'_prepare') as prepare:
   pipeline.prepare(args); pipeline.prepare(args); self.assertEqual(prepare.call_count,2)
   args.hotwords='changed'
   with self.assertRaises(ValueError): pipeline.prepare(args)
 def fixture(self):
  slug='BV0000000000-P02'; manifest={'id':slug,'title':'测试','creator':'测试作者','part':1,'series_part':2,'source_tags':['历史'],'transcript_source':'subtitle','selected':[{'file':f'../assets/{slug}-frame-000001.png'}]}
  (self.work/'manifest.json').write_text(json.dumps(manifest)); (self.work/'assets').mkdir(); (self.work/'assets'/f'{slug}-frame-000001.png').write_bytes(b'fixture-image')
  (self.work/'transcript.md').write_text('[00:00:00] 测试论据\n[00:00:10] 测试例子\n')
  (self.work/'audio.wav').write_bytes(b'media'); (self.work/'note.md').write_text('---\ntitle: "测试"\ncreator: "测试作者"\npart: 1\nseries_part: 2\nseries: "测试系列"\nvideo_keywords: ["历史"]\ncontent_keywords: ["论据"]\ntranscript_source: "subtitle"\ndynasties: ["唐"]\ntags: ["UP主/测试作者", "系列/测试系列", "朝代/唐"]\n---\n## 自测问题\n问题\n## 完整转写\n'+'测试论据与例子。'*30+f'\n![](../assets/{slug}-frame-000001.png)\n')
  path=coverage.create(self.work); data=json.loads(path.read_text()); data['reviewer']='synthetic-test'; data['note_sha256']=coverage.sha(self.work/'note.md')
  for row in data['segments']: row.update(decision='included',evidence='Synthetic test prose includes both points')
  path.write_text(json.dumps(data))
  import quality
  q=json.loads((self.work/'quality.json').read_text());q.update(reviewer='synthetic-test',note_sha256=coverage.sha(self.work/'note.md'))
  for i,row in enumerate(q['segments']):row.update(inventory_reviewed=True,uncertainties_reviewed=True,items=[{'kind':'argument' if i==0 else 'example','source_quote':'测试论据' if i==0 else '测试例子','note_quote':'测试论据与例子。','decision':'included'}])
  (self.work/'quality.json').write_text(json.dumps(q));return slug
 def test_publish_no_overwrite_and_verified_cleanup(self):
  slug=self.fixture(); vault=self.root/'vault'
  with patch.dict(os.environ,{'BILIBILI_NOTES_VAULT':str(vault)}):
   pipeline.publish(Namespace(workdir=self.work,validate_only=False,category='History'))
   self.assertFalse((self.work/'audio.wav').exists()); self.assertTrue((self.work/'transcript.md').exists()); self.assertTrue((self.work/'coverage.json').exists())
   with self.assertRaises(FileExistsError): pipeline.publish(Namespace(workdir=self.work,validate_only=False,category='History'))
   (self.work/'audio.wav').write_bytes(b'retain'); (vault/'Video Notes/History'/f'{slug}.md').write_text('mismatch')
   with self.assertRaises(ValueError): pipeline.cleanup_staging(self.work,pipeline.load_manifest(self.work),'History')
   self.assertTrue((self.work/'audio.wav').exists())
 def test_publish_keep_media(self):
  self.fixture(); vault=self.root/'vault'
  with patch.dict(os.environ,{'BILIBILI_NOTES_VAULT':str(vault)}):
   pipeline.publish(Namespace(workdir=self.work,validate_only=False,category='History',keep_media=True))
  self.assertTrue((self.work/'audio.wav').exists())
  self.assertTrue((vault/'Video Notes/History/BV0000000000-P02.md').exists())
 def test_coverage_stale_and_pending(self):
  self.fixture(); coverage.validate(self.work)
  (self.work/'note.md').write_text('changed')
  with self.assertRaises(ValueError): coverage.validate(self.work)
if __name__=='__main__': unittest.main()
