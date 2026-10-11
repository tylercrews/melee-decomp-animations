"""Build offline animation/costume controls and downloadable GIF bundles.

python -m tools.melee_anim.preview_gallery --require-all
Open build/melee_anim/preview/player.html. Generated GIFs and ZIP bundles
stay under ignored build/; no server or external resources are required.
"""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile, ZIP_STORED
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
.stage{background:transparent;border:1px solid #354151;border-radius:12px;display:flex;justify-content:center;min-height:400px;align-items:center}
.framewrap{position:relative;width:min(100%,512px)}#saveimage{position:absolute;inset:0;width:100%;height:100%;opacity:0}
#frame{width:min(100%,512px);height:auto}.timeline{display:flex;gap:12px;align-items:center;margin:20px 0}
#scrub{flex:1}a{color:#81baff}.meta{background:#202a36;padding:16px;border-radius:8px}
[hidden]{display:none!important}small{color:#b5c0ce}
</style><h1>Melee animation preview</h1>
<p>Choose a character, animation type, and costume color, then save its GIF or download a bundle of colors.</p>
<div class="controls">
<label>Character <select id="character" aria-label="Character"></select></label>
<label>Animation Type <select id="animationtype" aria-label="Animation Type">
<option value="victory">Victory Pose</option><option value="taunt">Taunt</option>
<option value="clapping">Clapping</option><option value="attack">Attack</option></select></label>
<label id="actionlabel">Animation <select id="action" aria-label="Animation"></select></label>
<label>Costume <select id="costume" aria-label="Costume color"></select></label>
<button id="play">Pause</button><button id="restart">Restart</button>
<label><input id="loop" type="checkbox"> Repeat preview</label></div>
<fieldset id="clapmodes" class="controls"><legend>Clapping mode</legend>
<label><input id="fullcycle" type="radio" name="clapmode" value="full" checked> Full animation</label>
<label><input id="minimumcycle" type="radio" name="clapmode" value="minimum" disabled> Minimum cycle</label>
<label><input id="dirtycycle" type="radio" name="clapmode" value="dirty" disabled> Minimum loop (dirty/jittery)</label>
<label><input id="synccycle" type="radio" name="clapmode" value="sync" disabled> Clapping-sync alteration</label>
<small id="cyclehint"></small></fieldset>
<fieldset class="controls"><legend>Viewing angle</legend>
<label>X tilt <input id="pitch" type="range" min="-180" max="180" step="1" value="0" autocomplete="off" aria-label="X tilt"><output id="pitchvalue">0°</output></label>
<label>Y turn <input id="yaw" type="range" min="-180" max="180" step="1" value="0" autocomplete="off" aria-label="Y turn"><output id="yawvalue">0°</output></label>
<label>Z roll <input id="roll" type="range" min="-180" max="180" step="1" value="0" autocomplete="off" aria-label="Z roll"><output id="rollvalue">0°</output></label>
<button id="applyangle">Apply</button><button id="resetangle">Reset</button>
<small id="rotationstatus" role="status" aria-live="polite">Angles apply to previews and every GIF/PNG download. New angles need rendering.</small></fieldset>
<div class="stage"><div class="framewrap"><img id="frame" alt="Animated character costume preview"><img id="saveimage" aria-hidden="true" alt="" title="Right-click to save"></div></div>
<small>Right-click the character to save its transparent GIF while playing or its transparent PNG while paused.</small>
<div class="timeline"><input id="scrub" type="range" min="0" value="0" step="1" aria-label="Animation frame"><span id="time"></span></div>
<div class="controls"><label>Download size <select id="downloadsize" aria-label="Download size">
<option value="128">Extra small (128 × 128)</option><option value="256" selected>Small (256 × 256)</option>
<option value="512">Medium (512 × 512)</option><option value="1024">Large (1024 × 1024)</option>
</select></label><small>Medium and Large enlarge the current renders.</small></div>
<div class="downloads" id="downloadpanel"><a class="download primary" id="gif" download>Download GIF</a>
<a class="download" id="animationzip" download>Download this animation in all colors</a>
<a class="download" id="allzip" download="melee-all-characters-all-animations.zip" href="downloads/melee-all-characters-all-animations.zip">Download all GIFs</a>
<a class="download" id="still" hidden download>Download paused frame PNG</a>
<a class="download" id="framezip" hidden download>Download paused frame in all colors</a>
<a id="open" target="_blank" rel="noopener">Open GIF</a></div>
<small>Repeat preview does not alter the saved GIF. Victory loops are the separate authored wait animations. If a browser opens a local file instead of downloading it, use Save link as.</small>
<p id="servicehint" hidden>For attacks, viewing angles, or resized downloads, open the <a href="http://127.0.0.1:8765/player.html">local download player</a>.
If it is closed, start it from the repository with <code>python -m tools.melee_anim.player_server</code>.</p>
<div class="meta" id="meta"></div>
<p>This prototype uses original models and motion curves with approximate shading. Timed game scripts, effects, props, dynamics, and audio are not played; native seams are preserved.</p>
<script>
const clips=__CLIPS__, animations=__ANIMATIONS__, characters=__CHARACTERS__;
const character=document.getElementById("character"), still=document.getElementById("still"), framezip=document.getElementById("framezip");
const saveimage=document.getElementById('saveimage');
const animationtype=document.getElementById('animationtype'), actionlabel=document.getElementById('actionlabel');
const action=document.getElementById('action'), costume=document.getElementById('costume'), frame=document.getElementById('frame'),
play=document.getElementById('play'), restart=document.getElementById('restart'), loop=document.getElementById('loop'),
scrub=document.getElementById('scrub'), clock=document.getElementById('time'), gif=document.getElementById('gif'),
archive=document.getElementById('animationzip'), open=document.getElementById('open'),
downloadsize=document.getElementById('downloadsize'), allzip=document.getElementById('allzip'),
fullcycle=document.getElementById('fullcycle'), minimumcycle=document.getElementById('minimumcycle'),
dirtycycle=document.getElementById('dirtycycle'), synccycle=document.getElementById('synccycle'),
cyclehint=document.getElementById('cyclehint');
downloadsize.value='256';
animationtype.value='clapping';
const preparedCount=clips.filter(c=>!c.lazy).length;
const exportBase=location.protocol==='http:'?'':'http://127.0.0.1:8765';
document.getElementById('servicehint').hidden=location.protocol==='http:';
let current=0,index=0,playing=true,last=performance.now(),carry=0,lastImage=null;
const angleInputs=['pitch','yaw','roll'].map(id=>document.getElementById(id));
const rotationstatus=document.getElementById('rotationstatus'), applyangle=document.getElementById('applyangle'), resetangle=document.getElementById('resetangle');
let angles=[0,0,0], rotated=null, rotationBusy=false, rotationFailed=false, rotationGeneration=0;
angleInputs.forEach((input,i)=>{input.value='0';input.oninput=()=>document.getElementById(['pitchvalue','yawvalue','rollvalue'][i]).textContent=`${input.value}°`});
if(location.protocol!=='http:')rotationstatus.textContent='Choose an angle. Apply opens the local rendering player with your current selections.';
function hasAngle(){return angles.some(v=>v!==0)}
function angleSuffix(){return hasAngle()?'-view-'+angles.map((v,i)=>'xyz'[i]+v).join('-'):''}
function angleName(name){return name.replace(/(\.[^.]+)$/,`${angleSuffix()}$1`)}
function previewUnavailable(){return rotationBusy||rotationFailed}
function updateRotationState(){frame.hidden=previewUnavailable();saveimage.hidden=previewUnavailable();play.disabled=previewUnavailable();scrub.disabled=previewUnavailable();
document.getElementById('downloadpanel').hidden=previewUnavailable()}
async function loadRotation(){const generation=++rotationGeneration;rotated=null;rotationBusy=false;rotationFailed=false;
if(!hasAngle()&&!clips[current].lazy){rotationstatus.textContent=location.protocol==='http:'?'Default angle. Angles apply to previews and every GIF/PNG download.':'Choose an angle. Apply opens the local rendering player with your current selections.';updateRotationState();show();return}
if(location.protocol!=='http:'){let c=clips[current];let query=new URLSearchParams({character:c.character,action:c.action_key,costume:String(c.costume_id),cycle:cycleMode(),frame:String(index),playing:String(playing),repeat:String(loop.checked),size:downloadsize.value,pitch:String(angles[0]),yaw:String(angles[1]),roll:String(angles[2])});
location.href=`${exportBase}/player.html#${query}`;return}
rotationBusy=true;rotationstatus.textContent=clips[current].lazy?'Preparing this attack animation… Each color is rendered and saved when needed.':'Rendering this viewing angle… Downloads will be ready with the preview. All-color downloads render additional costumes as needed.';
updateRotationState();
try{let c=clips[current];let query=new URLSearchParams({character:c.character,action:c.action_key,costume:String(c.costume_id),cycle:cycleMode(),pitch:String(angles[0]),yaw:String(angles[1]),roll:String(angles[2])});
let response=await fetch(`/rotation?${query}`);if(!response.ok)throw Error(response.status===503?'Renderer is busy; try Apply again shortly.':'Render failed. Check the player service log, then try Apply again or Reset.');
let result=await response.json();if(generation!==rotationGeneration)return;
if(result.frames.length!==frameCount())throw Error('Rendered frame count differs from this animation.');
rotated=result;rotationBusy=false;last=performance.now();carry=0;
rotationstatus.textContent=`Viewing angle: X ${angles[0]}°, Y ${angles[1]}°, Z ${angles[2]}°. Preview and downloads use this angle.`;
result.frames.forEach(src=>{let image=new Image();image.src=src});updateRotationState();show();
}catch(error){if(generation!==rotationGeneration)return;rotationBusy=false;rotationFailed=true;
rotationstatus.textContent=error.message||'Cannot reach the local player service. Try Apply again or Reset.';updateRotationState()}}
applyangle.onclick=()=>{angles=angleInputs.map(input=>{let value=Number(input.value);return value===180?-180:value});loadRotation()};
function syncAngleInputs(){angleInputs.forEach((input,i)=>{input.value=String(angles[i]);input.oninput()})}
resetangle.onclick=()=>{angles=[0,0,0];syncAngleInputs();loadRotation()};
// Form restoration can run after this script; also reset a cached page when
// returning through browser history. Explicit file-to-server handoffs still
// keep their requested angles on the first visit.
if(typeof addEventListener==='function')addEventListener('pageshow',event=>{
if(event.persisted)resetangle.onclick();else syncAngleInputs()});
function checkMode(mode){[fullcycle,minimumcycle,dirtycycle,synccycle].forEach((r,i)=>r.checked=['full','minimum','dirty','sync'][i]===mode)}
checkMode('full');
characters.forEach(c=>{let o=document.createElement('option');o.value=c.slug;o.textContent=c.label;character.append(o)});
character.value=characters.some(c=>c.slug==='mario')?'mario':characters[0].slug;
function colors(){let list=characters.find(c=>c.slug===character.value).costumes;let old=costume.value;costume.options.length=0;
list.forEach(c=>{let o=document.createElement('option');o.value=String(c.id);o.textContent=c.label;costume.append(o)});
costume.value=list.some(c=>String(c.id)===old)?old:String(list[0].id)}
function typeForAction(key){return key.startsWith('attack-')?'attack':key.startsWith('victory')?'victory':key==='taunt_source'?'taunt':'clapping'}
function actions(){let old=action.value;let list=animations.filter(a=>a.character===character.value&&typeForAction(a.key)===animationtype.value);action.options.length=0;
list.forEach(a=>{let o=document.createElement('option');o.value=a.key;o.textContent=a.unavailable?a.label+' — unavailable (copy model needed)':a.label;o.disabled=Boolean(a.unavailable);action.append(o)});
action.value=list.some(a=>a.key===old&&!a.unavailable)?old:list.find(a=>!a.unavailable).key;
actionlabel.hidden=list.filter(a=>!a.unavailable).length<=1}
colors();actions();
allzip.textContent=`Download all ${preparedCount} results/taunt GIFs`;
function cycleMode(){let c=clips[current];return synccycle.checked&&c.sync_cycle?'sync':dirtycycle.checked&&c.dirty_cycle?'dirty':minimumcycle.checked&&c.minimum_cycle?'minimum':'full'}
function activeCycle(){let c=clips[current];return cycleMode()==='sync'?c.sync_cycle:cycleMode()==='dirty'?c.dirty_cycle:cycleMode()==='minimum'?c.minimum_cycle:null}
function useMinimum(){return current>=0&&Boolean(activeCycle())}
function frameCount(){let c=clips[current];let short=activeCycle();return short?short.length:c.lazy?c.frame_count:c.frames.length}
function sourceIndex(){let short=activeCycle();return index+(short&&!short.frames?short.start:0)}
function framePath(){if(rotated)return rotated.frames[index];let short=activeCycle();return short&&short.frames?short.frames[index]:clips[current].frames[sourceIndex()]}
function sourceTime(){let c=clips[current];let short=activeCycle();return short&&short.frames?short.source_times[index]:c.lazy?(rotated&&rotated.source_times?rotated.source_times[index]:c.period*index/Math.max(1,Math.ceil(c.period/60*c.fps))):c.source_times[sourceIndex()]}
function markedName(name){let suffix=cycleMode()==='sync'?'-clapping-sync':cycleMode()==='dirty'?'-dirty-loop':'-minimum-cycle';return useMinimum()?name.replace(/(\.[^.]+)$/,`${suffix}$1`):name}
function sizedName(name){return name.replace(/(\.[^.]+)$/,`-${downloadsize.value}px$1`)}
function updateCycleInfo(){if(current<0)return;let c=clips[current];minimumcycle.disabled=!c.minimum_cycle;dirtycycle.disabled=!c.dirty_cycle;
synccycle.disabled=!c.sync_cycle;document.getElementById('clapmodes').hidden=c.action_key!=='results-clap_source';
if(cycleMode()==='full')checkMode('full');
let short=activeCycle()||c.minimum_cycle||c.dirty_cycle;
cyclehint.textContent=cycleMode()==='sync'?`42 frames / 0.84s. ${short.repeats} repeats; ${short.hold_frames_per_cycle} held frames per repeat; moving speed ${short.moving_rate.toFixed(2)}x. ${short.selection}.`:
short?`${short.length} frames / ${(short.length/c.fps).toFixed(2)}s instead of ${c.frames.length} frames. ${short.dirty?'Dirty review: '+short.failed_checks.join('; '):'Edited repeat; subtle motion may differ.'}`:
(c.action_key==='results-clap_source'?'No shorter repeat passed the checks.':'Minimum cycle is available for repeating claps.');
scrub.max=frameCount()-1;
document.getElementById('meta').textContent=`${c.symbol} / ${frameCount()} frames at ${c.fps} fps / ${(frameCount()/c.fps).toFixed(2)}s / ${cycleMode()==='sync'?'clapping-sync alteration':cycleMode()==='dirty'?'minimum loop (dirty/jittery)':useMinimum()?'minimum cycle (edited loop)':c.authored_loop?'full authored loop':'one-shot action'}`}
function exportURL(kind,scope){let c=clips[current];let query=new URLSearchParams({character:c.character,action:c.action_key,
costume:String(c.costume_id),size:downloadsize.value,kind,scope,frame:String(index),cycle:cycleMode()});
if(hasAngle()){['pitch','yaw','roll'].forEach((key,i)=>query.set(key,String(angles[i])))}return `${exportBase}/export?${query}`}
function updateDownloads(){if(current<0)return;let c=clips[current];let a=animations.find(a=>a.key===c.action_key&&a.character===c.character);
let original=downloadsize.value==='256'&&!useMinimum()&&!hasAngle()&&!c.lazy;
gif.href=original?c.gif:exportURL('gif','costume');gif.download=sizedName(angleName(markedName(c.download_name)));
open.href=original?c.gif:exportURL('gif','costume')+'&view=1';
archive.href=original?a.zip:exportURL('gif','colors');archive.download=sizedName(angleName(markedName(a.download_name)));
allzip.href=original?'downloads/melee-all-characters-all-animations.zip':exportURL('gif','all');
allzip.hidden=Boolean(c.lazy);
allzip.textContent=cycleMode()==='sync'?`Download all ${clips.filter(c=>c.sync_cycle).length} synced claps`:`Download all ${preparedCount} results/taunt GIFs`;
allzip.download=cycleMode()==='sync'?sizedName(angleName('melee-all-characters-clapping-sync.zip')):sizedName(angleName(markedName('melee-all-characters-all-animations.zip')));
still.href=original?c.frames[index]:exportURL('png','costume');
still.download=sizedName(angleName(markedName(c.download_name).replace('.gif',`-frame-${String(index+1).padStart(4,'0')}.png`)));
framezip.href=original?`${a.stills}/frame-${String(index+1).padStart(4,'0')}.zip`:exportURL('png','colors');
framezip.download=sizedName(angleName(markedName(`${c.character}-${c.action_key.replaceAll('_','-')}-frame-${String(index+1).padStart(4,'0')}-all-colors.zip`)))}
function show(){if(current<0||previewUnavailable())return;let c=clips[current];let src=framePath();if(lastImage!==src){frame.src=src;lastImage=src}scrub.value=index;
updateDownloads();
still.hidden=playing;framezip.hidden=playing;
// A real image receives the browser's native Save image as operation. The
// timed PNG underneath preserves scrubbing/repeat semantics; the save target
// is the actual GIF while playing and the exact PNG while paused. Remove the
// irrelevant GIF frame query so animation ticks never refetch the same GIF.
let savedSrc=playing?open.href.replace(/([?&])frame=\d+(&|$)/,'$1').replace(/[?&]$/,''):still.href;
if(saveimage.getAttribute?saveimage.getAttribute('src')!==savedSrc:saveimage.src!==savedSrc)saveimage.src=savedSrc;
saveimage.title=playing?'Right-click to save transparent GIF':'Right-click to save transparent PNG';
clock.textContent=`${index+1}/${frameCount()} / source ${sourceTime().toFixed(2)}`}
function select(render=true){current=clips.findIndex(c=>c.character===character.value&&c.action_key===action.value&&String(c.costume_id)===costume.value);
index=0;carry=0;last=performance.now();
let a=animations.find(a=>a.key===action.value&&a.character===character.value);archive.href=a.zip;archive.download=a.download_name;
archive.textContent=`Download this animation — ${a.color_count} colors`;
if(current<0){playing=false;play.textContent='Play';frame.hidden=true;gif.hidden=true;open.hidden=true;
still.hidden=true;framezip.hidden=true;
document.getElementById('meta').textContent='This animation/color has not been rendered yet.';return}
let c=clips[current];frame.hidden=false;gif.hidden=false;open.hidden=false;scrub.max=c.frames.length-1;
loop.checked=c.authored_loop;playing=true;play.textContent='Pause';
gif.href=c.gif;gif.download=c.download_name;gif.textContent=`Download GIF / ${c.costume_label}`;open.href=c.gif;
updateCycleInfo();
c.frames.forEach(src=>{let image=new Image();image.src=src});if(render)loadRotation()}
character.onchange=()=>{colors();actions();select()};animationtype.onchange=()=>{actions();select()};
action.onchange=()=>{animationtype.value=typeForAction(action.value);actions();select()};costume.onchange=select;
downloadsize.onchange=updateDownloads;
function changeCycle(){if(current<0)return;index=0;carry=0;last=performance.now();updateCycleInfo();let short=activeCycle();if(short&&short.frames)short.frames.forEach(src=>{let image=new Image();image.src=src});if(hasAngle())loadRotation();else show()}
[fullcycle,minimumcycle,dirtycycle,synccycle].forEach((r,i)=>r.onchange=()=>{if(r.checked){checkMode(['full','minimum','dirty','sync'][i]);changeCycle()}});
play.onclick=()=>{if(current<0)return;playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now();carry=0;show()};
restart.onclick=()=>{if(current<0)return;index=0;last=performance.now();carry=0;playing=true;play.textContent='Pause';show()};
scrub.oninput=()=>{if(current<0)return;index=Number(scrub.value);playing=false;play.textContent='Play';show()};
function tick(now){if(current>=0&&playing&&!previewUnavailable()){let c=clips[current];carry+=Math.min(now-last,250);let step=1000/c.fps;
while(carry>=step){carry-=step;if(index+1<frameCount())index++;else if(loop.checked)index=0;else{playing=false;play.textContent='Play';break}}show()}
last=now;requestAnimationFrame(tick)}
function restoreSelection(){let incoming=new URLSearchParams((location.hash||'').slice(1));
// Consume this one-time handoff so refresh/reopen cannot replay old angles.
if(location.hash&&typeof history!=='undefined')history.replaceState(null,'',location.pathname+location.search);
if(characters.some(c=>c.slug===incoming.get('character'))){character.value=incoming.get('character');colors();actions()}
if(animations.some(a=>a.character===character.value&&a.key===incoming.get('action')&&!a.unavailable)){animationtype.value=typeForAction(incoming.get('action'));action.value=incoming.get('action');actions()}
if(characters.find(c=>c.slug===character.value).costumes.some(c=>String(c.id)===incoming.get('costume')))costume.value=incoming.get('costume');
if(['full','minimum','dirty','sync'].includes(incoming.get('cycle')))checkMode(incoming.get('cycle'));
if(['128','256','512','1024'].includes(incoming.get('size')))downloadsize.value=incoming.get('size');
select(false);
let savedFrame=Number(incoming.get('frame'));if(Number.isInteger(savedFrame)&&savedFrame>=0&&savedFrame<frameCount())index=savedFrame;
if(incoming.has('playing')){playing=incoming.get('playing')==='true';play.textContent=playing?'Pause':'Play'}
if(incoming.has('repeat'))loop.checked=incoming.get('repeat')==='true';
let savedAngles=['pitch','yaw','roll'].map(key=>Number(incoming.get(key)||0));
if(savedAngles.every(v=>Number.isFinite(v)&&Math.abs(v)<=180)&&savedAngles.some(v=>v!==0)){
angleInputs.forEach((input,i)=>{input.value=String(savedAngles[i]);input.oninput()});angles=savedAngles.map(v=>v===180?-180:v);loadRotation();
}else loadRotation()}
restoreSelection();requestAnimationFrame(tick);
</script></html>'''


def collect_clips(root, include_attacks=True):
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
    from .cycles import attach_cycles
    attach_cycles(root, clips)
    from .sync_claps import attach_sync
    attach_sync(root, clips)
    if include_attacks:
        from .attacks import virtual_clips
        clips.extend(virtual_clips(root))
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


def write_still_bundle(root, path, clips, index):
    """Reuse byte-matching complete ZIPs; replace interrupted/stale bundles."""
    files = {c['download_name'].replace('.gif', f'-frame-{index+1:04d}.png'):
             (root/c['frames'][index]).read_bytes() for c in clips}
    if path.is_file():
        try:
            with ZipFile(path) as archive:
                if set(archive.namelist()) == set(files) and all(
                        archive.read(name) == data for name, data in files.items()):
                    return
        except (BadZipFile, OSError, KeyError):
            pass
    temporary = path.with_suffix('.zip.tmp')
    with ZipFile(temporary, 'w', compression=ZIP_STORED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("build/melee_anim/preview"))
    parser.add_argument("--require-all", action="store_true", help="require eight animation choices for every actual roster costume")
    parser.add_argument('--player-only', action='store_true', help='refresh controls using existing download bundles')
    args = parser.parse_args()
    clips = collect_clips(args.root, include_attacks=False)
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
    animations=[];characters=[];bundle_jobs=[]
    for slug,name in CHARACTERS:
        owned=[c for c in clips if c['character']==slug]
        if not owned:continue
        characters.append({'slug':slug,'label':name,'costumes':[{'id':i,'label':next(c['costume_label'] for c in owned if c['costume_id']==i)} for i in sorted({c['costume_id'] for c in owned})]})
        for action,section,label in ACTIONS:
            key=f'{action}_{section}';group=by_action[(slug,key)]
            if not group:continue
            filename=f'{slug}-{key.replace("_","-")}-all-colors.zip'
            stills=downloads/'stills'/f'{slug}-{key}';stills.mkdir(parents=True,exist_ok=True)
            counts={len(c['frames']) for c in group}
            if len(counts)!=1:raise ValueError('Color frame counts differ')
            bundle_jobs.append((downloads/filename, stills, group, next(iter(counts))))
            animations.append({'character':slug,'key':key,'label':label,'zip':f'downloads/{filename}','download_name':filename,'color_count':len(group),'stills':stills.relative_to(args.root).as_posix()})
    def bundles(job):
        path, folder, group, count = job
        write_bundle(args.root, path, group)
        for i in range(count):
            write_still_bundle(args.root, folder/f'frame-{i+1:04d}.zip', group, i)
    if args.player_only:
        if not (downloads/'melee-all-characters-all-animations.zip').is_file() or any(
                not path.is_file() or any(not (folder/f'frame-{i+1:04d}.zip').is_file() for i in range(count))
                for path, folder, _, count in bundle_jobs):
            parser.error('download bundles are missing; regenerate without --player-only')
    else:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for i, future in enumerate(as_completed([pool.submit(bundles, job) for job in bundle_jobs]), 1):
                future.result()
                if i % 10 == 0 or i == len(bundle_jobs):
                    print(f'Packaged {i}/{len(bundle_jobs)} character/animation downloads', flush=True)
        write_bundle(args.root,downloads/'melee-all-characters-all-animations.zip',clips)
    output = args.root/"player.html"
    from .attacks import virtual_clips
    attack_clips = virtual_clips(args.root)
    attack_groups = defaultdict(list)
    for clip in attack_clips:
        attack_groups[(clip['character'],clip['action_key'])].append(clip)
    for (slug,key), group in attack_groups.items():
        filename = f'{slug}-{key.replace("_","-")}-all-colors.zip'
        animations.append({'character':slug,'key':key,'label':group[0]['action_label'],
                           'type':'attack','lazy':True,'color_count':len(group),
                           'download_name':filename,'zip':'','stills':''})
    catalog_path = args.root/'attack-catalog.json'
    if catalog_path.is_file():
        for fighter in json.loads(catalog_path.read_text())['characters']:
            for a in fighter['actions']:
                if not a['available']:
                    animations.append({'character':fighter['character'],'key':a['key'],'label':a['label'],
                                       'type':'attack','unavailable':a['unavailable_reason']})
    clips.extend(attack_clips)
    safe_json = lambda value: json.dumps(value).replace("<", "\\u003c")
    content = TEMPLATE.replace("__CLIPS__",safe_json(clips)).replace("__ANIMATIONS__",safe_json(animations)).replace("__CHARACTERS__",safe_json(characters))
    output.write_text(content,encoding="utf-8")
    print(f"Offline player: {output} ({len(clips)} clips, {len(animations)} animations, {len(characters)} characters)")
    print(f"GIF download bundles: {downloads}")


if __name__ == "__main__":
    main()
