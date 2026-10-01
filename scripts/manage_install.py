"""Backed-up local installation/rollback; leave private overlay and external config intact."""
import argparse,shutil,tempfile,zipfile,json,os
from pathlib import Path
from datetime import datetime,timezone

def install(source,target,backups):
    source=source.resolve();target=target.resolve();backups.mkdir(parents=True,exist_ok=True)
    if source==target or source in target.parents or target in source.parents:raise ValueError('Source and target must be separate directories')
    if not (source/'SKILL.md').is_file():raise ValueError('Source has no SKILL.md')
    backup=backups/('install-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.zip')
    if target.exists():
        with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
            for p in target.rglob('*'):
                if p.is_file():z.write(p,p.relative_to(target))
    candidate=Path(tempfile.mkdtemp(prefix=target.name+'-update-',dir=target.parent));old=target.with_name(target.name+'-previous')
    try:
        shutil.copytree(source,candidate,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc','.DS_Store','local-runtime.md'))
        overlay=target/'references/local-runtime.md'
        if overlay.is_file():(candidate/'references').mkdir(exist_ok=True);shutil.copy2(overlay,candidate/'references/local-runtime.md')
        if old.exists():raise FileExistsError('Previous update directory exists; inspect it before update')
        if target.exists():target.rename(old)
        try:candidate.rename(target)
        except BaseException:
            if old.exists():old.rename(target)
            raise
        if old.exists():shutil.rmtree(old)
    finally:
        if candidate.exists():shutil.rmtree(candidate)
    return str(backup) if backup.exists() else None

def rollback(backup,target):
    with tempfile.TemporaryDirectory(dir=target.parent) as folder:
        source=Path(folder)
        with zipfile.ZipFile(backup) as z:
            for name in z.namelist():
                if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe archive path')
            z.extractall(source)
        return install(source,target,target.parent/'bilibili-install-backups')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['install','rollback']);p.add_argument('source',type=Path);p.add_argument('target',type=Path);p.add_argument('--backups',type=Path);a=p.parse_args()
    print(json.dumps({'backup':install(a.source,a.target,a.backups or a.target.parent/'bilibili-install-backups') if a.action=='install' else rollback(a.source,a.target)}))
