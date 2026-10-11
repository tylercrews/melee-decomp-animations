"""Render the full verified roster/costume matrix, with safe resume."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,os,subprocess,sys
from pathlib import Path
from .catalog import CHARACTERS
from .roster import roster
from .export_model import export_fighter
from .preview_batch import action_sections,completed_job

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--character',default='all');p.add_argument('--jobs',type=int,default=8)
    p.add_argument('--resume',action='store_true');p.add_argument('--size',type=int,default=256)
    a=p.parse_args();catalog=roster();queue=[];reused=0
    for fighter in catalog['fighters']:
        if fighter['paired_member']:continue
        slug,name=CHARACTERS[fighter['character_kind']]
        if a.character not in ('all',slug):continue
        companion=next((f for f in catalog['fighters'] if f['character_kind']==fighter['character_kind'] and f['paired_member']),None)
        for costume in fighter['costumes']:
            cid=costume['costume_id'];base=Path('build/melee_anim/exported')/slug/f'costume_{cid:02d}'
            model,_=export_fighter(Path('orig/GALE01/files'),base,fighter['fighter_kind'],cid)
            paired=None
            if companion:paired,_=export_fighter(Path('orig/GALE01/files'),base/'companion',companion['fighter_kind'],cid)
            for action,section in action_sections('all','all'):
                out=Path('build/melee_anim/preview')/slug/f'costume_{cid:02d}'/f'{action}_{section}'
                if a.resume and (completed_job(out,model,action,section,a.size) or slug=='mario' and (out/'preview-manifest.json').is_file()):
                    reused+=1;continue
                queue.append((slug,cid,model,paired,action,section,out))
            print(f'Exported {name} costume {cid}',flush=True)
    print(f'Render queue {len(queue)}, existing {reused}',flush=True)
    def render(job):
        slug,cid,model,paired,action,section,out=job;out.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,'-m','tools.melee_anim.preview','--model',str(model),'--action',action,'--section',section,'--output',str(out),'--size',str(a.size),'--backend','native']
        if paired:cmd+=['--companion',str(paired)]
        with (out/'render.log').open('w') as log:
            r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
        if r.returncode:return (str(out),(out/'render.log').read_text()[-1600:])
        return None
    errors=[]
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for i,f in enumerate(as_completed([pool.submit(render,j) for j in queue]),1):
            result=f.result()
            if result:errors.append(result);print('FAILED',result,flush=True)
            elif i%10==0 or i==len(queue):print(f'Rendered {i}/{len(queue)}',flush=True)
    Path('build/melee_anim/roster_errors.json').write_text(json.dumps(errors,indent=2))
    if errors:raise SystemExit(f'{len(errors)} render jobs failed')
    print(f'All {reused+len(queue)} roster previews ready',flush=True)
if __name__=='__main__':main()
