"""One local entrypoint; machine config is outside the installed skill."""
import argparse,json,os,sys,subprocess,shutil,importlib.metadata
from pathlib import Path

def configure(path):
    data=json.loads(Path(path).read_text());required={'vault','model','environment'}
    if not required<=data.keys():raise ValueError('Local config requires vault/model/environment')
    if data.get('chunk_seconds',60)!=60:raise ValueError('This deployment keeps target chunks at 60 seconds')
    mapping={'vault':'BILIBILI_NOTES_VAULT','model':'BILIBILI_QWEN_MODEL','cache':'HF_HOME'}
    for key,env in mapping.items():
        if key in data:os.environ.setdefault(env,str(Path(data[key]).expanduser()))
    os.environ['PATH']=str(Path(data['environment'])/'bin')+os.pathsep+os.environ.get('PATH','');os.environ.setdefault('HF_HUB_DISABLE_XET','1');return data

def doctor(data):
    packages={}
    for name in ['qwen3-asr-mlx','mlx','soundfile','numpy','yt-dlp','opencc-python-reimplemented']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]=None
    mismatches={}
    lock=Path(__file__).parent.parent/'requirements-macos.lock'
    for line in lock.read_text().splitlines():
        if '==' not in line:continue
        name,expected=line.split('==',1)
        try:actual=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:actual=None
        if actual!=expected:mismatches[name]={'expected':expected,'actual':actual}
    model=Path(os.environ['BILIBILI_QWEN_MODEL']); result={'python':sys.executable,'packages':packages,'ffmpeg':shutil.which('ffmpeg'),'yt_dlp':shutil.which('yt-dlp'),'model_config':(model/'config.json').is_file(),'model_weights':any(model.glob('*.safetensors')),'vault':os.environ['BILIBILI_NOTES_VAULT'],'vault_exists':Path(os.environ['BILIBILI_NOTES_VAULT']).is_dir(),'target_chunk_seconds':60,'missing':[],'version_mismatches':mismatches}
    result['missing']=[name for name,val in packages.items() if val is None]+[key for key in ['ffmpeg','yt_dlp','model_config','model_weights','vault_exists'] if not result[key]]
    print(json.dumps(result,ensure_ascii=False,indent=2));return not result['missing'] and not mismatches

def main():
    config=os.environ.get('BILIBILI_CONFIG')
    if not config:raise ValueError('Set BILIBILI_CONFIG to independent local JSON configuration')
    data=configure(config)
    if sys.argv[1:]==['doctor']:sys.exit(0 if doctor(data) else 1)
    args=sys.argv[1:]
    if args and args[0]=='prepare':
        if '--chunk-seconds' not in args:args+=['--chunk-seconds','60']
        if '--max-minutes' not in args:args+=['--max-minutes',str(data.get('max_minutes',90))]
    os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name('video_pipeline.py')),*args])
if __name__=='__main__':main()
