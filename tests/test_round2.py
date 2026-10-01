import unittest,tempfile,json,sys,os,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import quality,coverage,progress,boundaries,runtime,manage_install,video_pipeline

class Round2Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.w=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def reviewed(self):
  (self.w/'transcript.md').write_text('[00:00:00] 人物张三在315年出发，例如剪发换酒。\n');(self.w/'note.md').write_text('## 完整转写\n张三出发。例如剪发换酒。年份315年未核查。')
  quality.create(self.w);d=json.loads((self.w/'quality.json').read_text());d.update(reviewer='fixture reviewer',note_sha256=coverage.sha(self.w/'note.md'));d['segments'][0].update(inventory_reviewed=True,uncertainties_reviewed=True,items=[{'kind':'event','source_quote':'出发','note_quote':'张三出发。','decision':'included'},{'kind':'example','source_quote':'剪发换酒','note_quote':'例如剪发换酒。','decision':'included'}],uncertainties=[{'kind':'year','source_quote':'315年','status':'marked','note_quote':'年份315年未核查。','reason':'No inspected evidence'}]);(self.w/'quality.json').write_text(json.dumps(d));return d
 def save(self,d):(self.w/'quality.json').write_text(json.dumps(d))
 def test_missing_example_and_substantive_omission_block(self):
  d=self.reviewed();quality.validate(self.w);d['segments'][0]['items'][1]['note_quote']='正文不存在例子';self.save(d)
  with self.assertRaises(ValueError):quality.validate(self.w)
  d['segments'][0]['items'][1].update(decision='omitted',reason='Want a shorter summary');self.save(d)
  with self.assertRaises(ValueError):quality.validate(self.w)
 def test_pending_and_unmarked_doubt_block(self):
  d=self.reviewed();d['segments'][0]['uncertainties'][0]['status']='pending';self.save(d)
  with self.assertRaises(ValueError):quality.validate(self.w)
  d['segments'][0]['uncertainties'][0].update(status='marked',note_quote='not in note');self.save(d)
  with self.assertRaises(ValueError):quality.validate(self.w)
 def test_source_anchor_and_stale_note_block(self):
  d=self.reviewed();d['segments'][0]['items'][0]['source_quote']='Invented event';self.save(d)
  with self.assertRaises(ValueError):quality.validate(self.w)
  self.reviewed_reset()
 def reviewed_reset(self):
  (self.w/'quality.json').unlink();self.reviewed();(self.w/'note.md').write_text('new note')
  with self.assertRaises(ValueError):quality.validate(self.w)
 def test_year_quote_audit_is_warning_not_fact_correction(self):
  self.reviewed();report=quality.audit(self.w);self.assertFalse(report['semantic_accuracy_proven']);self.assertTrue(report['gate']['valid']);self.assertEqual(report['findings'][0]['kind'],'year')
 def test_progress_survives_error_with_live_output(self):
  with patch('sys.stderr') as output:
   progress.emit(self.w,'download');progress.emit(self.w,'download','failed',failure='network',recovery='Repeat identical command')
   self.assertTrue(output.write.called)
  data=json.loads((self.w/'progress.json').read_text());self.assertEqual(data['current']['state'],'failed');self.assertEqual(len((self.w/'progress.jsonl').read_text().splitlines()),2)
 def test_prepare_failure_identifies_stage(self):
  with patch.object(video_pipeline.sys,'argv',['pipeline','prepare','https://b23.tv/test','--workdir',str(self.w)]),patch.object(video_pipeline,'_prepare',side_effect=RuntimeError('network')):
   with self.assertRaises(SystemExit):video_pipeline.main()
  self.assertEqual(json.loads((self.w/'progress.json').read_text())['current']['state'],'failed');self.assertTrue((self.w/'prepare_request.json').exists())
 def test_tool_heartbeat_preserves_output(self):
  import subprocess
  progress.emit(self.w,'download')
  with patch.object(video_pipeline,'CURRENT_WORKDIR',self.w),patch.object(video_pipeline.subprocess,'Popen') as create:
   proc=create.return_value;proc.communicate.side_effect=[subprocess.TimeoutExpired('tool',15),('complete payload','')];proc.returncode=0
   result=video_pipeline.call(['test-tool'])
  self.assertEqual(result.stdout,'complete payload');self.assertEqual(json.loads((self.w/'progress.json').read_text())['current']['phase'],'download')
 def test_failure_reports_nested_stage(self):
  def fail(args):progress.emit(self.w,'frames');raise RuntimeError('decode failed')
  with patch.object(video_pipeline.sys,'argv',['pipeline','prepare','https://b23.tv/test','--workdir',str(self.w)]),patch.object(video_pipeline,'_prepare',side_effect=fail):
   with self.assertRaises(SystemExit):video_pipeline.main()
  self.assertEqual(json.loads((self.w/'progress.json').read_text())['current']['failure_point'],'frames')
 def test_repetition_is_never_removed_without_alignment(self):
  rows=[{'index':0,'start':0,'end':60,'text':'不要放弃。不要放弃。'},{'index':1,'start':60,'end':120,'text':'不要放弃。接下来举例。'}];p=self.w/'qwen_segments.jsonl';original='\n'.join(json.dumps(r,ensure_ascii=False) for r in rows);p.write_text(original)
  result=boundaries.inspect(self.w);self.assertFalse(result['automatic_deletion']);self.assertFalse(result['overlap_enabled']);self.assertEqual(result['boundaries'][0]['exact_repeat_candidate'],'不要放弃。');self.assertEqual(p.read_text(),original)
 def test_config_env_override_preserved(self):
  p=self.w/'config.json';p.write_text(json.dumps({'vault':'/private/user-vault','model':'/local/model','environment':'/isolated','chunk_seconds':60}))
  with patch.dict(os.environ,{'BILIBILI_NOTES_VAULT':'/temporary-vault'},clear=True):runtime.configure(p);self.assertEqual(os.environ['BILIBILI_NOTES_VAULT'],'/temporary-vault')
 def test_install_backup_rollback_preserves_private_overlay(self):
  source=self.w/'source';target=self.w/'installed';source.mkdir();target.mkdir();(source/'SKILL.md').write_text('new skill');(target/'SKILL.md').write_text('old skill');(target/'references').mkdir();(target/'references/local-runtime.md').write_text('user config');(source/'references').mkdir();(source/'references/local-runtime.md').write_text('upstream config')
  config=self.w/'config.json';config.write_text('user settings');backup=manage_install.install(source,target,self.w/'backups');self.assertEqual((target/'SKILL.md').read_text(),'new skill');self.assertEqual((target/'references/local-runtime.md').read_text(),'user config');manage_install.rollback(Path(backup),target);self.assertEqual((target/'SKILL.md').read_text(),'old skill');self.assertEqual(config.read_text(),'user settings')
if __name__=='__main__':unittest.main()
