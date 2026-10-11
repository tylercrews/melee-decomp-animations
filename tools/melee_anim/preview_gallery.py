"""Build offline animation/costume controls and downloadable GIF bundles.

python -m tools.melee_anim.preview_gallery --require-all
Open build/melee_anim/preview/player.html. Generated GIFs and ZIP bundles
stay under ignored build/; no server or external resources are required.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_STORED
from .catalog import CHARACTERS

COSTUMES = {0: "Red (default)", 1: "Yellow", 2: "Black", 3: "Blue", 4: "Green"}
ACTIONS = [("results-clap", "source", "Clapping"),
           ("victory1", "source", "Victory 1"), ("victory1", "wait", "Victory 1 loop"),
           ("victory2", "source", "Victory 2"), ("victory2", "wait", "Victory 2 loop"),
           ("victory3", "source", "Victory 3"), ("victory3", "wait", "Victory 3 loop"),
           ("taunt", "source", "Taunt")]

TEMPLATE = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Melee animation preview</title>
<style>
body{font:16px system-ui;background:#161b22;color:#edf2f7;padding:32px;max-width:1040px;margin:auto}
h1{margin:0 0 8px;font-size:28px}p{color:#b5c0ce;line-height:1.5}select,button,input{font:inherit}
select,button,.download{padding:10px;border:1px solid #445368;border-radius:6px;background:#263243;color:inherit}
.controls,.downloads{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}
.controls label{display:flex;align-items:center;gap:8px}.download{display:inline-block;text-decoration:none}
.download.primary{background:#235da8;border-color:#3878cb}.download:hover{filter:brightness(1.15)}
.stage{background:#22262e;border:1px solid #354151;border-radius:12px;display:flex;justify-content:center;min-height:400px;align-items:center}
#frame{width:min(100%,512px);height:auto}.timeline{display:flex;gap:12px;align-items:center;margin:20px 0}
#scrub{flex:1}a{color:#81baff}.meta{background:#202a36;padding:16px;border-radius:8px}
[hidden]{display:none!important}small{color:#b5c0ce}
</style><h1>Melee animation preview</h1>
<p>Choose a character, animation, and costume color, then save its GIF or download a bundle of colors.</p>
<div class="controls">
<label>Character <select id="character" aria-label="Character"></select></label>
<label>Animation <select id="action" aria-label="Animation"></select></label>
<label>Costume <select id="costume" aria-label="Costume color"></select></label>
<button id="play">Pause</button><button id="restart">Restart</button>
<label><input id="loop" type="checkbox"> Repeat preview</label></div>
<div class="stage"><img id="frame" alt="Animated character costume preview"></div>
<div class="timeline"><input id="scrub" type="range" min="0" value="0" step="1" aria-label="Animation frame"><span id="time"></span></div>
<div class="downloads"><a class="download primary" id="gif" download>Download GIF</a>
<a class="download" id="animationzip" download>Download this animation in all colors</a>
<a class="download" id="allzip" download="melee-all-characters-all-animations.zip" href="downloads/melee-all-characters-all-animations.zip">Download all GIFs</a>
<a class="download" id="still" hidden download>Download paused frame PNG</a>
<a class="download" id="framezip" hidden download>Download paused frame in all colors</a>
<a id="open" target="_blank" rel="noopener">Open GIF</a></div>
<small>Repeat preview does not alter the saved GIF. Victory loops are the separate authored wait animations. If a browser opens a local file instead of downloading it, use Save link as.</small>
<div class="meta" id="meta"></div>
<p>This prototype uses original models and motion curves with approximate shading. Timed game scripts, effects, props, dynamics, and audio are not played; native seams are preserved.</p>
<script>
const clips=__CLIPS__, animations=__ANIMATIONS__, characters=__CHARACTERS__;
const character=document.getElementById("character"), still=document.getElementById("still"), framezip=document.getElementById("framezip");
const action=document.getElementById('action'), costume=document.getElementById('costume'), frame=document.getElementById('frame'),
play=document.getElementById('play'), restart=document.getElementById('restart'), loop=document.getElementById('loop'),
scrub=document.getElementById('scrub'), clock=document.getElementById('time'), gif=document.getElementById('gif'),
archive=document.getElementById('animationzip'), open=document.getElementById('open');
let current=0,index=0,playing=true,last=performance.now(),carry=0,lastImage=null;
characters.forEach(c=>{let o=document.createElement('option');o.value=c.slug;o.textContent=c.label;character.append(o)});
character.value=characters.some(c=>c.slug==='mario')?'mario':characters[0].slug;
function colors(){let list=characters.find(c=>c.slug===character.value).costumes;let old=costume.value;costume.options.length=0;
list.forEach(c=>{let o=document.createElement('option');o.value=String(c.id);o.textContent=c.label;costume.append(o)});
costume.value=list.some(c=>String(c.id)===old)?old:String(list[0].id)}
function actions(){let old=action.value;let list=animations.filter(a=>a.character===character.value);action.options.length=0;
list.forEach(a=>{let o=document.createElement('option');o.value=a.key;o.textContent=a.label;action.append(o)});
action.value=list.some(a=>a.key===old)?old:list[0].key}
colors();actions();
document.getElementById('allzip').textContent=`Download all ${clips.length} GIFs`;
function show(){if(current<0)return;let c=clips[current];let src=c.frames[index];if(lastImage!==src){frame.src=src;lastImage=src}scrub.value=index;
let a=animations.find(a=>a.key===action.value&&a.character===character.value);
still.href=c.frames[index];still.download=c.download_name.replace('.gif',`-frame-${String(index+1).padStart(4,'0')}.png`);
framezip.href=`${a.stills}/frame-${String(index+1).padStart(4,'0')}.zip`;framezip.download=`${c.character}-${c.action_key}-frame-${index+1}-all-colors.zip`;
still.hidden=playing;framezip.hidden=playing;
clock.textContent=`${index+1}/${c.frames.length} / source ${c.source_times[index].toFixed(2)}`}
function select(){current=clips.findIndex(c=>c.character===character.value&&c.action_key===action.value&&String(c.costume_id)===costume.value);
index=0;carry=0;last=performance.now();
let a=animations.find(a=>a.key===action.value&&a.character===character.value);archive.href=a.zip;archive.download=a.download_name;
archive.textContent=`Download this animation — ${a.color_count} colors`;
if(current<0){playing=false;play.textContent='Play';frame.hidden=true;gif.hidden=true;open.hidden=true;
still.hidden=true;framezip.hidden=true;
document.getElementById('meta').textContent='This animation/color has not been rendered yet.';return}
let c=clips[current];frame.hidden=false;gif.hidden=false;open.hidden=false;scrub.max=c.frames.length-1;
loop.checked=c.authored_loop;playing=true;play.textContent='Pause';
gif.href=c.gif;gif.download=c.download_name;gif.textContent=`Download GIF / ${c.costume_label}`;open.href=c.gif;
document.getElementById('meta').textContent=`${c.symbol} / ${c.period} source frames / ${c.fps} fps preview / ${c.authored_loop?'authored loop':'one-shot action'}`;
c.frames.forEach(src=>{let image=new Image();image.src=src});show()}
character.onchange=()=>{colors();actions();select()};action.onchange=select;costume.onchange=select;
play.onclick=()=>{if(current<0)return;playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now();carry=0;show()};
restart.onclick=()=>{if(current<0)return;index=0;last=performance.now();carry=0;playing=true;play.textContent='Pause';show()};
scrub.oninput=()=>{if(current<0)return;index=Number(scrub.value);playing=false;play.textContent='Play';show()};
function tick(now){if(current>=0&&playing){let c=clips[current];carry+=Math.min(now-last,250);let step=1000/c.fps;
while(carry>=step){carry-=step;if(index+1<c.frames.length)index++;else if(loop.checked)index=0;else{playing=false;play.textContent='Play';break}}show()}
last=now;requestAnimationFrame(tick)}
select();requestAnimationFrame(tick);
</script></html>'''


def collect_clips(root):
    clips = []
    seen = set()
    for path in sorted(root.glob("*/costume_*/*/preview-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not manifest["complete_interval"]:
            continue
        match = re.fullmatch(r"costume_(\d+)", path.parent.parent.name)
        if match is None:
            raise ValueError(f"Invalid costume directory: {path}")
        costume_id = int(match[1]); slug=path.parent.parent.parent.name
        name=dict(CHARACTERS).get(slug)
        if name is None:continue
        if manifest.get("costume_id", costume_id) != costume_id:
            raise ValueError(f"Costume identity mismatch: {path}")
        key = f"{manifest['action']}_{manifest['section']}"
        if key not in {f"{a}_{s}" for a,s,_ in ACTIONS}:
            continue
        if (slug,key, costume_id) in seen:
            raise ValueError(f"Duplicate action/costume: {key}/{costume_id}")
        seen.add((slug,key, costume_id))
        relative = path.parent.relative_to(root).as_posix()
        times = manifest["sample_source_times"]
        expected = {f"frame_{i:04d}.png" for i in range(len(times))}
        if not times or expected != {p.name for p in path.parent.glob("frame_*.png")} or not (path.parent/"preview.gif").is_file():
            raise ValueError(f"Incomplete or stale preview files: {path}")
        suffix=Path(manifest.get("source_model_archive","PlMrNr.dat")).stem[4:]
        color=COSTUMES[costume_id] if slug=='mario' else {'Nr':'Default','Re':'Red','Bu':'Blue','Gr':'Green','Bk':'Black','Wh':'White','Ye':'Yellow','Or':'Orange','Aq':'Aqua','Pi':'Pink'}.get(suffix,f'Costume {costume_id+1}')
        if slug=='game-and-watch':color=('Black','Red','Blue','Green')[costume_id]
        filename = f"{slug}-{key.replace('_','-')}-costume-{costume_id:02d}-{color.split()[0].lower()}.gif"
        clips.append({"character":slug,"character_label":name,"action_key": key, "costume_id": costume_id, "costume_label": color,
                      "fps": manifest["fps"], "period": manifest["source_period_frames"],
                      "authored_loop": manifest["authored_loop"], "symbol": manifest["source_symbol"],
                      "download_name": filename, "source_times": times, "gif": f"{relative}/preview.gif",
                      "frames": [f"{relative}/frame_{i:04d}.png" for i in range(len(times))]})
    return clips


def write_bundle(root, path, clips):
    inventory = []
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        for clip in clips:
            source = root/clip["gif"]
            archive.write(source, clip["download_name"])
            inventory.append({"file": clip["download_name"], "costume_id": clip["costume_id"],
                              "costume_label": clip["costume_label"], "animation": clip["action_key"],
                              "source_symbol": clip["symbol"], "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        archive.writestr("manifest.json", json.dumps({"files": inventory}, indent=2)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("build/melee_anim/preview"))
    parser.add_argument("--require-all", action="store_true", help="require eight animation choices for every actual roster costume")
    args = parser.parse_args()
    clips = collect_clips(args.root)
    if not clips:
        parser.error("No complete rendered roster preview manifests found")
    from .roster import roster
    expected={(CHARACTERS[f['character_kind']][0],f'{a}_{s}',c['costume_id']) for f in roster()['fighters'] if not f['paired_member'] for c in f['costumes'] for a,s,_ in ACTIONS}
    actual = {(c["character"],c["action_key"], c["costume_id"]) for c in clips}
    if args.require_all and expected != actual:
        parser.error(f"Missing animation/costume combinations: {sorted(expected-actual)}")
    downloads = args.root/"downloads"
    downloads.mkdir(parents=True,exist_ok=True)
    by_action = defaultdict(list)
    for clip in clips:
        by_action[(clip["character"],clip["action_key"])].append(clip)
    animations=[];characters=[]
    for slug,name in CHARACTERS:
        owned=[c for c in clips if c['character']==slug]
        if not owned:continue
        characters.append({'slug':slug,'label':name,'costumes':[{'id':i,'label':next(c['costume_label'] for c in owned if c['costume_id']==i)} for i in sorted({c['costume_id'] for c in owned})]})
        for action,section,label in ACTIONS:
            key=f'{action}_{section}';group=by_action[(slug,key)]
            if not group:continue
            filename=f'{slug}-{key.replace("_","-")}-all-colors.zip'
            write_bundle(args.root,downloads/filename,group)
            stills=downloads/'stills'/f'{slug}-{key}';stills.mkdir(parents=True,exist_ok=True)
            counts={len(c['frames']) for c in group}
            if len(counts)!=1:raise ValueError('Color frame counts differ')
            for i in range(next(iter(counts))):
                with ZipFile(stills/f'frame-{i+1:04d}.zip','w',compression=ZIP_STORED) as z:
                    for c in group:z.write(args.root/c['frames'][i],c['download_name'].replace('.gif',f'-frame-{i+1:04d}.png'))
            animations.append({'character':slug,'key':key,'label':label,'zip':f'downloads/{filename}','download_name':filename,'color_count':len(group),'stills':stills.relative_to(args.root).as_posix()})
    write_bundle(args.root,downloads/'melee-all-characters-all-animations.zip',clips)
    output = args.root/"player.html"
    safe_json = lambda value: json.dumps(value).replace("<", "\\u003c")
    content = TEMPLATE.replace("__CLIPS__",safe_json(clips)).replace("__ANIMATIONS__",safe_json(animations)).replace("__CHARACTERS__",safe_json(characters))
    output.write_text(content,encoding="utf-8")
    print(f"Offline player: {output} ({len(clips)} clips, {len(animations)} animations, {len(characters)} characters)")
    print(f"GIF download bundles: {downloads}")


if __name__ == "__main__":
    main()
