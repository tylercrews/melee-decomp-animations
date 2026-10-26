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
.controls label{display:flex;align-items:center;gap:8px;min-width:0;max-width:100%}.controls select{min-width:0;max-width:100%}.download{display:inline-block;text-decoration:none}
.download.primary{background:#235da8;border-color:#3878cb}.download:hover{filter:brightness(1.15)}
.download.hd{background:#7540b0;border-color:#a677df}.download.hd-colors{background:#45206c;border-color:#8153ad}
.downloads label{display:flex;align-items:center;gap:8px}
.download[aria-disabled="true"]{opacity:.65;cursor:wait}.download.busy::before{content:"";display:inline-block;width:1em;height:1em;margin-right:8px;vertical-align:-2px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.stage{background:transparent;border:1px solid #354151;border-radius:12px;display:flex;justify-content:center;min-height:400px;align-items:center}
.framewrap{position:relative;width:min(100%,512px)}#saveimage{position:absolute;inset:0;width:100%;height:100%;opacity:0}
#frame{width:min(100%,512px);height:auto}
.loading{position:relative;width:min(100%,512px);aspect-ratio:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px}#loadingframe{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;opacity:.5}
.loading .spinner{position:relative;width:56px;height:56px;border:5px solid rgba(255,255,255,.25);border-top-color:#81baff;border-radius:50%;animation:spin .8s linear infinite}#loadingtext{position:relative;color:#e5ebf2;text-shadow:0 1px 3px #000}
.timeline{display:flex;gap:12px;align-items:center;margin:20px 0}
#scrub{flex:1}a{color:#81baff}.meta{background:#202a36;padding:16px;border-radius:8px}
[hidden]{display:none!important}small{color:#b5c0ce}
#sizewarning{color:#b59a19}
.controls .angle-control{flex:1 1 280px}.angle-control input[type="range"]{flex:1;width:160px;min-width:80px}.angle-control input[type="number"]{width:4.5em;padding:5px;border:1px solid #445368;border-radius:4px;background:#263243;color:inherit}#anglehint,#rotationstatus{flex-basis:100%}
.axis-x{color:#ef5b5b;font-weight:700}.axis-y{color:#5cc46a;font-weight:700}.axis-z{color:#5b9cf0;font-weight:700}
.anglepreview{margin:0;display:flex;flex-direction:column;align-items:center;gap:6px}.anglepreview figcaption{font-weight:600}.anglepreviewwrap{position:relative;width:220px;height:220px;border:1px solid #354151;border-radius:8px}#anglepreview{width:100%;height:100%;object-fit:contain}.anglepreviewwrap svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;font:700 8px system-ui}#anglepreviewstatus{max-width:260px;text-align:center}
#downloadprogress{margin:12px 0}#downloadbar{width:100%;height:18px;accent-color:#3878cb}#downloadcount{display:block;margin-top:6px}
</style><h1>Melee animation preview</h1>
<p>Choose a character and costume color, then an animation type and animation. Save its GIF or download a bundle of colors.</p>
<div class="controls" id="charactercontrols">
<label>Character <select id="character" aria-label="Character"></select></label>
<label id="powerlabel" hidden>Kirby Power <select id="kirbypower" aria-label="Kirby Power" autocomplete="off"></select></label>
<label>Costume <select id="costume" aria-label="Costume color"></select></label></div>
<div class="controls" id="animationcontrols">
<label>Animation Type <select id="animationtype" aria-label="Animation Type">
<option value="victory">Victory Pose</option><option value="taunt">Taunt</option>
<option value="clapping">Clapping</option><option value="attack">Attack</option><option value="tech">Knockdown</option><option value="movement">Movement</option><option value="hit">Hit</option><option value="other">Other</option></select></label>
<label id="actionlabel">Animation <select id="action" aria-label="Animation"></select></label>
<label><input id="hidepartials" type="checkbox" checked autocomplete="off"> Hide partial animations</label></div>
<div class="controls" id="playbackcontrols">
<button id="play">Pause</button><button id="restart">Restart</button>
<label><input id="loop" type="checkbox" checked autocomplete="off"> Repeat preview</label></div>
<fieldset id="clapmodes" class="controls"><legend>Clapping mode</legend>
<label><input id="fullcycle" type="radio" name="clapmode" value="full" checked> Full animation</label>
<label><input id="minimumcycle" type="radio" name="clapmode" value="minimum" disabled> Minimum cycle</label>
<label><input id="dirtycycle" type="radio" name="clapmode" value="dirty" disabled> Minimum loop (dirty/jittery)</label>
<label><input id="synccycle" type="radio" name="clapmode" value="sync" disabled> Clapping-sync alteration</label>
<small id="cyclehint"></small></fieldset>
<div id="jumpcontrols" class="controls" hidden><label><input id="centerjump" type="checkbox" autocomplete="off"> Keep character centered</label>
<small>The camera follows the character at a fixed zoom. Applies to previews and GIF/PNG downloads.</small></div>
<p id="movementhint" hidden>Standing includes the normal idle loop; alternate idles vary by character. Walking, running and dashing preview the original motion in place. Rolls and spot dodge use their original motion clips; forward/backward are relative to facing. Yoshi rolls in his egg and spot dodges outside it; his egg pose is also available. Full/short hops use neutral jump squat, flight and landing with source movement attributes and shared framing; stage physics and movement effects are not simulated.</p>
<p id="sequencehint" hidden></p>
<div id="electriccontrols" class="controls" hidden><label><input id="judgeelectric" type="checkbox" checked autocomplete="off"> Electric hit explosion (9)</label>
<small>Shows the original electric-hit particles at the hammer strike. This is a contact preview preset; no opponent is simulated.</small></div>
<p id="effecthint" hidden></p>
<p id="itemhint" hidden></p>
<div id="techcontrols" class="controls" hidden>
<label><input id="groundeffects" type="checkbox" checked> Ground-impact effects</label>
<small id="techhint">Towards/away follow the character's facing. With impacts on, the whole effect fits; turning them off zooms in on the character. Fighter flashes remain with impacts off. Extra dust/sparkle particles are not included yet.</small></div>
<fieldset class="controls"><legend>Viewing angle</legend>
<label class="angle-control"><span class="axis-x">X</span> tilt <input id="pitch" type="range" min="-180" max="180" step="1" value="0" list="anglestops" autocomplete="off" aria-label="X tilt" aria-describedby="anglehint"><input id="pitchvalue" type="number" min="-180" max="180" step="1" value="0" required autocomplete="off" aria-label="Exact X tilt degrees">°</label>
<label class="angle-control"><span class="axis-y">Y</span> turn <input id="yaw" type="range" min="-180" max="180" step="1" value="0" list="anglestops" autocomplete="off" aria-label="Y turn" aria-describedby="anglehint"><input id="yawvalue" type="number" min="-180" max="180" step="1" value="0" required autocomplete="off" aria-label="Exact Y turn degrees">°</label>
<label class="angle-control"><span class="axis-z">Z</span> roll <input id="roll" type="range" min="-180" max="180" step="1" value="0" list="anglestops" autocomplete="off" aria-label="Z roll" aria-describedby="anglehint"><input id="rollvalue" type="number" min="-180" max="180" step="1" value="0" required autocomplete="off" aria-label="Exact Z roll degrees">°</label>
<datalist id="anglestops"><option value="-180"></option><option value="-135"></option><option value="-90"></option><option value="-45"></option><option value="0"></option><option value="45"></option><option value="90"></option><option value="135"></option><option value="180"></option></datalist>
<figure id="anglepreviewpanel" class="anglepreview"><figcaption>Viewing Angle Preview</figcaption><div class="anglepreviewwrap"><img id="anglepreview" alt="Selected frame at the chosen viewing angle"><svg viewBox="0 0 100 100" aria-hidden="true"><defs><marker id="axisx" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L10 5L0 10z" fill="#ef5b5b"/></marker><marker id="axisy" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5cc46a"/></marker><marker id="axisz" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b9cf0"/></marker></defs><path d="M14 60A36 7 0 0 1 86 60" fill="none" stroke="#5cc46a" stroke-width="1.2" stroke-dasharray="2 2" opacity=".5"/><path d="M86 60A36 7 0 0 1 14 60" fill="none" stroke="#5cc46a" stroke-width="1.6" marker-end="url(#axisy)"/><text x="89" y="67" fill="#5cc46a">Y</text><path d="M93 80A5 22 0 0 1 93 36" fill="none" stroke="#ef5b5b" stroke-width="1.6" marker-end="url(#axisx)"/><path d="M93 36A5 22 0 0 1 93 80" fill="none" stroke="#ef5b5b" stroke-width="1.2" stroke-dasharray="2 2" opacity=".5"/><text x="90" y="32" fill="#ef5b5b">X</text><path d="M10.2 27A46 46 0 0 1 89.8 27" fill="none" stroke="#5b9cf0" stroke-width="1.6" marker-end="url(#axisz)"/><text x="47" y="8" fill="#5b9cf0">Z</text></svg></div><small id="anglepreviewstatus" role="status" aria-live="polite"></small></figure>
<small id="anglehint">Sliders snap near each 45° mark. Enter any exact degree in the number boxes, or use the slider's arrow keys for 1° steps.</small>
<button id="applyangle">Apply</button><button id="resetangle">Reset</button>
<small id="rotationstatus" role="status" aria-live="polite">Angles apply to previews and every GIF/PNG download. New angles need rendering.</small></fieldset>
<div class="stage"><div id="loading" class="loading" role="status" aria-live="polite" hidden><img id="loadingframe" alt="" hidden><span class="spinner"></span><small id="loadingtext">Loading animation…</small></div><div class="framewrap"><img id="frame" alt="Animated character costume preview"><img id="saveimage" aria-hidden="true" alt="" title="Right-click to save"></div></div>
<small>Right-click the character to save its transparent GIF while playing or its transparent PNG while paused.</small>
<div class="timeline"><input id="scrub" type="range" min="0" value="0" step="1" aria-label="Animation frame"><span id="time"></span></div>
<div class="controls"><label>Download size <select id="downloadsize" aria-label="Download size">
<option value="128">Extra small (128 × 128)</option><option value="256">Small (256 × 256)</option>
<option value="512">Medium (512 × 512)</option><option value="1024" selected>★ Large (1024 × 1024, native render)</option>
<option value="2048">⚠ X-Large (2048 × 2048)</option>
</select></label><small id="sizewarning" role="status" aria-live="polite" hidden>Extremely large GIF files</small>
<small id="upsizenotice" role="status" aria-live="polite" hidden></small>
</div>
<div class="controls" id="downloadoptions"><label><input id="kirbymode" type="checkbox" autocomplete="off"> Kirby Mode - include all hats all colors</label>
<small>Adds every Kirby copy appearance to batch ZIPs. First downloads may need additional rendering.</small></div>
<div class="downloads" id="downloadpanel"><a class="download primary" id="gif" download>Download GIF</a>
<a class="download" id="animationzip" download>Download this animation in all colors</a>
<a class="download" id="allzip" download>Download matching animations for all characters</a>
<a class="download" id="still" hidden download>Download paused frame PNG</a>
<a class="download" id="framezip" hidden download>Download paused frame in all colors</a>
<a class="download hd" id="hdstill" hidden download>Rerender Selected Frame In HD</a>
<a class="download hd-colors" id="hdcolors" hidden download>Rerender Selected Frame In HD In All Colors</a>
<label id="hdcroplabel" hidden><input id="cropborder" type="checkbox" checked autocomplete="off"> Crop Transparent Border</label>
<a id="open" target="_blank" rel="noopener">Open GIF</a></div>
<div class="controls" id="hdcontrols" hidden><label>HD PNG size <select id="hdsize" aria-label="HD PNG size"><option value="2048">2048 × 2048</option><option value="4096" selected>4096 × 4096</option></select></label>
<small>Renders the selected pose from the model with your applied angles. Cropping removes transparent outer margins without resizing; final PNG dimensions may be smaller than the render size. Temporary exports expire after 10 minutes. Original texture detail is retained.</small></div>
<small id="downloadstatus" role="status" aria-live="polite"></small>
<div id="downloadprogress" hidden><progress id="downloadbar" max="100" value="0" aria-label="Download preparation progress"></progress><small id="downloadcount"></small></div>
<small>Repeat preview does not alter the saved GIF. Victory loops are the separate authored wait animations. If a browser opens a local file instead of downloading it, use Save link as.</small>
<p id="servicehint" hidden>For attacks, viewing angles, or resized downloads, open the <a href="http://127.0.0.1:8765/player.html">local download player</a>.
If it is closed, start it from the repository with <code>python -m tools.melee_anim.player_server</code>.</p>
<div class="meta" id="meta"></div>
<p>This prototype uses original models and motion curves with approximate shading. Common swing weapons and supported character props are included in attacks. Ground-impact effects are optional; projectiles, unsupported props, complete game scripts, dynamics and audio remain unfinished. Native seams are preserved.</p>
<script>
const clips=__CLIPS__, animations=__ANIMATIONS__, characters=__CHARACTERS__, powers=__POWERS__;
const batchGroups=new Map();for(const c of clips){if(c.batch_partial)continue;let group=batchGroups.get(c.batch_family);if(!group){group={count:0,sync:0,kirby:0,label:c.batch_label};batchGroups.set(c.batch_family,group)}group.count++;if(c.sync_cycle)group.sync++;if(c.character==='kirby')group.kirby++}
const kirbymode=document.getElementById('kirbymode');let includeKirbyHats=false;kirbymode.checked=false;
function batchHats(){return includeKirbyHats?'all':'off'}
function hatsName(name){return includeKirbyHats?name.replace(/(\.[^.]+)$/,'-kirby-all-hats-all-colors$1'):name}
function batchMarkedName(name,scope){let marked=markedName(name);if(scope==='all')marked=marked.replace(`-power-${powerSetting()}`,'');const kirby=scope==='all'?batchGroups.get(clips[current].batch_family)?.kirby:character.value==='kirby';if(includeKirbyHats&&kirby){marked=marked.replace(`-power-${powerSetting()}`,'');marked=hatsName(marked)}return marked}
const animationTypes=new Map(animations.filter(a=>a.type).map(a=>[a.character+':'+a.key,a.type]));
const kirbypower=document.getElementById('kirbypower'),powerlabel=document.getElementById('powerlabel');
let kirbyPower='none';
powers.forEach(p=>{let o=document.createElement('option');o.value=p.slug;o.textContent=p.label;kirbypower.append(o)});kirbypower.value='none';
function powerSetting(){return character.value==='kirby'?kirbyPower:'none'}
function hasPower(){return powerSetting()!=='none'}
function powerName(name){return hasPower()?name.replace(/(\.[^.]+)$/,`-power-${powerSetting()}$1`):name}
const character=document.getElementById("character"), still=document.getElementById("still"), framezip=document.getElementById("framezip");
const hdstill=document.getElementById('hdstill'),hdcolors=document.getElementById('hdcolors'),hdsize=document.getElementById('hdsize'),hdcontrols=document.getElementById('hdcontrols');
const cropborder=document.getElementById('cropborder'),hdcroplabel=document.getElementById('hdcroplabel');let cropTransparentBorder=true;cropborder.checked=true;
hdsize.value='4096';
const saveimage=document.getElementById('saveimage');
const groundeffects=document.getElementById('groundeffects'),techcontrols=document.getElementById('techcontrols'),techhint=document.getElementById('techhint');
let groundEffectsEnabled=true;
groundeffects.checked=groundEffectsEnabled;
const centerjump=document.getElementById('centerjump'),jumpcontrols=document.getElementById('jumpcontrols');
let centerJumpEnabled=false;centerjump.checked=false;
function isHop(){return ['movement-fullhop_source','movement-shorthop_source'].includes(clips[current].action_key)}
function centerSetting(){return isHop()&&centerJumpEnabled?'on':'off'}
function centeredName(name){return centerSetting()==='on'?name.replace(/(\.[^.]+)$/,'-centered$1'):name}
const animationtype=document.getElementById('animationtype'), actionlabel=document.getElementById('actionlabel');
const hidepartials=document.getElementById('hidepartials');
let partialsHidden=true;hidepartials.checked=true;
const action=document.getElementById('action'), costume=document.getElementById('costume'), frame=document.getElementById('frame'),
play=document.getElementById('play'), restart=document.getElementById('restart'), loop=document.getElementById('loop'),
scrub=document.getElementById('scrub'), clock=document.getElementById('time'), gif=document.getElementById('gif'),
archive=document.getElementById('animationzip'), open=document.getElementById('open'),
downloadsize=document.getElementById('downloadsize'), allzip=document.getElementById('allzip'),
fullcycle=document.getElementById('fullcycle'), minimumcycle=document.getElementById('minimumcycle'),
dirtycycle=document.getElementById('dirtycycle'), synccycle=document.getElementById('synccycle'),
cyclehint=document.getElementById('cyclehint');
let nativeDefaultSize=1024;downloadsize.value='1024';
animationtype.value='clapping';
const preparedCount=clips.filter(c=>!c.lazy).length;
const exportBase=location.protocol==='http:'?'':'http://127.0.0.1:8765';
document.getElementById('servicehint').hidden=location.protocol==='http:';
let current=0,index=0,playing=true,last=performance.now(),carry=0,lastImage=null;
const electriccontrols=document.getElementById('electriccontrols'),judgeelectric=document.getElementById('judgeelectric');
let judgeElectricEnabled=true;judgeelectric.checked=true;
function isJudgeNine(){return current>=0&&clips[current].character==='game-and-watch'&&['attack-305_source','attack-314_source'].includes(clips[current].action_key)}
function electricSetting(){return judgeElectricEnabled?'on':'off'}
judgeelectric.onchange=()=>{judgeElectricEnabled=judgeelectric.checked;updateDownloads();loadRotation()};
const angleInputs=['pitch','yaw','roll'].map(id=>document.getElementById(id));
const angleValues=['pitchvalue','yawvalue','rollvalue'].map(id=>document.getElementById(id));
const rotationstatus=document.getElementById('rotationstatus'), applyangle=document.getElementById('applyangle'), resetangle=document.getElementById('resetangle');
let angles=[0,0,0], rotated=null, rotationBusy=false, rotationFailed=false, rotationGeneration=0;
angleInputs.forEach((input,i)=>{
input.value=angleValues[i].value='0';let dragging=false;
input.onpointerdown=()=>{dragging=true};
input.onpointerup=input.onpointercancel=input.onblur=()=>{dragging=false};
input.onkeydown=()=>{dragging=false};
input.oninput=()=>{let value=Number(input.value),stop=Math.round(value/45)*45;
if(dragging&&Math.abs(value-stop)<=3)input.value=String(stop);
angleValues[i].value=input.value;refreshAnglePreview()};
angleValues[i].oninput=()=>{let value=Number(angleValues[i].value);
if(angleValues[i].value!==''&&Number.isInteger(value)&&Math.abs(value)<=180){input.value=String(value);refreshAnglePreview()}};
});
if(location.protocol!=='http:')rotationstatus.textContent='Choose an angle. Apply opens the local rendering player with your current selections.';
function hasAngle(){return angles.some(v=>v!==0)}
function effectSetting(){return clips[current].ground_effect&&groundEffectsEnabled?'on':'off'}
function effectName(name){return effectSetting()==='on'?name.replace(/(\.[^.]+)$/,'-ground-effects$1'):name}
function angleSuffix(){return hasAngle()?'-view-'+angles.map((v,i)=>'xyz'[i]+v).join('-'):''}
function angleName(name){return name.replace(/(\.[^.]+)$/,`${angleSuffix()}$1`)}
function previewUnavailable(){return rotationBusy||rotationFailed}
function updateRotationState(){frame.hidden=previewUnavailable();saveimage.hidden=previewUnavailable();play.disabled=previewUnavailable();scrub.disabled=previewUnavailable();
document.getElementById('downloadpanel').hidden=previewUnavailable();hdcontrols.hidden=previewUnavailable()||playing;
loading.hidden=!rotationBusy;if(!rotationBusy){loadingframe.hidden=true;if(typeof clearTimeout==='function')clearTimeout(loadingTimer)}}
// Render options shared by the full animation, angle previews and loading frames.
function renderQuery(view,frameIndex=null){let c=clips[current];let query=new URLSearchParams({character:c.character,action:c.action_key,costume:String(c.costume_id),cycle:cycleMode()});
if(frameIndex!==null)query.set('frame',String(frameIndex));
['pitch','yaw','roll'].forEach((key,i)=>query.set(key,String(view[i])));
if(isJudgeNine())query.set('electric',electricSetting());
if(hasPower())query.set('power',powerSetting());
if(isHop())query.set('center',centerSetting());
if(c.action_key.startsWith('tech-'))query.set('effects',effectSetting());return query}
// A new animation starts at the default view, which is prebuilt or the
// quickest render; Apply renders another angle on request.
let angleResetNotice=false;
function resetViewForNewAnimation(){if(hasAngle())angleResetNotice=true;angles=[0,0,0];syncAngleInputs()}
function resetNotice(text){if(!angleResetNotice)return text;angleResetNotice=false;return `Viewing angle reset to default for this animation. ${text}`}
async function loadRotation(){const generation=++rotationGeneration;rotated=null;rotationBusy=false;rotationFailed=false;
if(!hasAngle()&&!hasPower()&&!clips[current].lazy){rotationstatus.textContent=resetNotice(location.protocol==='http:'?'Default angle. Angles apply to previews and every GIF/PNG download.':'Choose an angle. Apply opens the local rendering player with your current selections.');updateRotationState();show();refreshAnglePreview();runPendingBatch();return}
if(location.protocol!=='http:'){location.href=playerHandoff();return}
rotationBusy=true;rotationstatus.textContent=clips[current].lazy?'Preparing this animation… Each color is rendered and saved when needed.':'Rendering this viewing angle… Downloads will be ready with the preview. All-color downloads render additional costumes as needed.';
updateRotationState();scheduleLoadingFrame();
try{let response=await fetch(`/rotation?${renderQuery(angles)}`);if(!response.ok)throw Error(response.status===503?'Renderer is busy; try Apply again shortly.':'Render failed. Check the player service log, then try Apply again or Reset.');
let result=await response.json();if(generation!==rotationGeneration)return;
if(result.frames.length!==frameCount())throw Error('Rendered frame count differs from this animation.');
rotated=result;rotationBusy=false;last=performance.now();carry=0;
rotationstatus.textContent=resetNotice(`Viewing angle: X ${angles[0]}°, Y ${angles[1]}°, Z ${angles[2]}°. Preview and downloads use this angle.`);
result.frames.forEach(src=>{let image=new Image();image.src=src});updateRotationState();show();refreshAnglePreview();runPendingBatch();
}catch(error){if(generation!==rotationGeneration)return;rotationBusy=false;rotationFailed=true;angleResetNotice=false;
rotationstatus.textContent=error.message||'Cannot reach the local player service. Try Apply again or Reset.';updateRotationState();refreshAnglePreview()}}
// Loading placeholder: while the full animation renders, one quick
// low-resolution frame (the middle frame, or the paused frame) shows under
// the spinner. The short delay skips it when the render is already cached.
const loading=document.getElementById('loading'),loadingframe=document.getElementById('loadingframe');
let loadingTimer=null,loadingBusy=false,loadingQueued=false;
function loadingFrameIndex(){return playing?Math.floor(frameCount()/2):index}
function scheduleLoadingFrame(){loadingframe.hidden=true;if(typeof setTimeout!=='function')return;clearTimeout(loadingTimer);loadingTimer=setTimeout(requestLoadingFrame,300)}
async function requestLoadingFrame(){if(!rotationBusy)return;
if(loadingBusy){loadingQueued=true;return}
loadingBusy=true;const generation=rotationGeneration;
try{let response=await fetch(`/angle-preview?${renderQuery(angles,loadingFrameIndex())}`);
if(response.ok){let result=await response.json();
if(generation===rotationGeneration&&rotationBusy){loadingframe.onload=()=>{if(generation!==rotationGeneration||!rotationBusy)return;loadingframe.hidden=false;if(!pendingDiffers())setAnglePreviewImage(result.url)};loadingframe.src=result.url}}}
catch(error){}
finally{loadingBusy=false;if(loadingQueued){loadingQueued=false;requestLoadingFrame()}}}
// Viewing Angle Preview: the applied angle shows the current frame directly;
// pending slider values request one quick low-resolution frame from the service.
const anglepreview=document.getElementById('anglepreview'),anglepreviewstatus=document.getElementById('anglepreviewstatus');
let anglePreviewTimer=null,anglePreviewBusy=false,anglePreviewQueued=false,anglePreviewGeneration=0;
function pendingAngles(){return angleInputs.map(input=>{let value=Number(input.value);return value===180?-180:value})}
function pendingDiffers(){return pendingAngles().some((value,i)=>value!==angles[i])}
function previewFrameIndex(){return playing?0:index}
function setAnglePreviewImage(src){if(src&&(anglepreview.getAttribute?anglepreview.getAttribute('src')!==src:anglepreview.src!==src))anglepreview.src=src}
function refreshAnglePreview(){if(!anglepreview||current<0)return;
if(pendingDiffers()){anglepreviewstatus.textContent=location.protocol==='http:'?'Rendering preview…':'Angle previews need the local player service. Apply opens it with these angles.';
if(location.protocol==='http:'&&typeof setTimeout==='function'){clearTimeout(anglePreviewTimer);anglePreviewTimer=setTimeout(requestAnglePreview,200)}return}
anglePreviewGeneration++;
if(previewUnavailable()){anglepreviewstatus.textContent=rotationFailed?'The applied angle failed to render.':'Rendering the applied angle…';return}
setAnglePreviewImage(framePath(previewFrameIndex()));
anglepreviewstatus.textContent=`Current angle: X ${angles[0]}°, Y ${angles[1]}°, Z ${angles[2]}° · frame ${previewFrameIndex()+1}. Adjust X, Y or Z to preview a new angle.`}
async function requestAnglePreview(){if(current<0||!pendingDiffers())return refreshAnglePreview();
if(anglePreviewBusy){anglePreviewQueued=true;return}
anglePreviewBusy=true;const generation=++anglePreviewGeneration,pending=pendingAngles(),frameIndex=previewFrameIndex();
try{let response=await fetch(`/angle-preview?${renderQuery(pending,frameIndex)}`);if(!response.ok)throw Error(response.status===503?'The renderer is busy; adjust again to retry the preview.':'The preview failed to render.');
let result=await response.json();
if(generation===anglePreviewGeneration&&pendingDiffers()){setAnglePreviewImage(result.url);
anglepreviewstatus.textContent=`Preview: X ${pending[0]}°, Y ${pending[1]}°, Z ${pending[2]}° · frame ${frameIndex+1}. Apply renders the full animation at this angle.`}}
catch(error){if(generation===anglePreviewGeneration)anglepreviewstatus.textContent=error.message||'Cannot reach the local player service.'}
finally{anglePreviewBusy=false;if(anglePreviewQueued){anglePreviewQueued=false;requestAnglePreview()}}}
applyangle.onclick=()=>{for(const input of angleValues){if(input.checkValidity&&!input.checkValidity()){input.reportValidity();return}}angles=angleInputs.map(input=>{let value=Number(input.value);return value===180?-180:value});loadRotation()};
function syncAngleInputs(){angleInputs.forEach((input,i)=>{input.value=String(angles[i]);input.oninput()});groundeffects.checked=groundEffectsEnabled;kirbypower.value=kirbyPower;centerjump.checked=centerJumpEnabled;hidepartials.checked=partialsHidden;kirbymode.checked=includeKirbyHats;cropborder.checked=cropTransparentBorder}
resetangle.onclick=()=>{angles=[0,0,0];syncAngleInputs();loadRotation()};
// Form restoration can run after this script; also reset a cached page when
// returning through browser history. Explicit file-to-server handoffs still
// keep their requested angles on the first visit.
if(typeof addEventListener==='function')addEventListener('pageshow',event=>{
updateSizeWarning();if(event.persisted)resetangle.onclick();else syncAngleInputs()});
function checkMode(mode){[fullcycle,minimumcycle,dirtycycle,synccycle].forEach((r,i)=>r.checked=['full','minimum','dirty','sync'][i]===mode)}
checkMode('full');
characters.forEach(c=>{let o=document.createElement('option');o.value=c.slug;o.textContent=c.label;character.append(o)});
character.value=characters.some(c=>c.slug==='mario')?'mario':characters[0].slug;
function colors(){let list=characters.find(c=>c.slug===character.value).costumes;let old=costume.value;costume.options.length=0;
powerlabel.hidden=character.value!=='kirby';kirbypower.value=kirbyPower;
list.forEach(c=>{let o=document.createElement('option');o.value=String(c.id);o.textContent=c.label;costume.append(o)});
costume.value=list.some(c=>String(c.id)===old)?old:String(list[0].id)}
function typeForAction(key){return animationTypes.get(character.value+':'+key)||(key.startsWith('movement-')?'movement':key.startsWith('tech-')?'tech':key.startsWith('attack-')?'attack':key.startsWith('victory')?'victory':key==='taunt_source'?'taunt':'clapping')}
function actions(preferred=action.value){let old=preferred;let owned=animations.filter(a=>a.character===character.value);let available=new Set(owned.filter(a=>!a.unavailable).map(a=>typeForAction(a.key)));
for(const option of animationtype.options){option.disabled=!available.has(option.value);option.hidden=option.disabled}
if(!available.has(animationtype.value))animationtype.value=available.has('movement')?'movement':available.values().next().value;
let list=owned.filter(a=>typeForAction(a.key)===animationtype.value&&(!partialsHidden||!a.partial));action.options.length=0;
list.forEach(a=>{let o=document.createElement('option');o.value=a.key;o.textContent=a.unavailable?a.label+' — unavailable':a.label;o.disabled=Boolean(a.unavailable);action.append(o)});
let replacement=owned.find(a=>a.key===old)?.combined_key;
action.value=list.some(a=>a.key===old&&!a.unavailable)?old:list.some(a=>a.key===replacement&&!a.unavailable)?replacement:list.find(a=>!a.unavailable).key;
actionlabel.hidden=list.filter(a=>!a.unavailable).length<=1}
colors();actions();
allzip.textContent=`Download all ${preparedCount} results/taunt GIFs`;
function cycleMode(){let c=clips[current];return synccycle.checked&&c.sync_cycle?'sync':dirtycycle.checked&&c.dirty_cycle?'dirty':minimumcycle.checked&&c.minimum_cycle?'minimum':'full'}
function activeCycle(){let c=clips[current];return cycleMode()==='sync'?c.sync_cycle:cycleMode()==='dirty'?c.dirty_cycle:cycleMode()==='minimum'?c.minimum_cycle:null}
function useMinimum(){return current>=0&&Boolean(activeCycle())}
function frameCount(){let c=clips[current];let short=activeCycle();return short?short.length:c.lazy?c.frame_count:c.frames.length}
function sourceIndex(){let short=activeCycle();return index+(short&&!short.frames?short.start:0)}
function framePath(i=index){if(rotated)return rotated.frames[i];let short=activeCycle();return short&&short.frames?short.frames[i]:clips[current].frames[i+(short&&!short.frames?short.start:0)]}
function sourceTime(){let c=clips[current];let short=activeCycle();return short&&short.frames?short.source_times[index]:c.lazy?(rotated&&rotated.source_times?rotated.source_times[index]:c.period*index/Math.max(1,Math.ceil(c.period/60*c.fps))):c.source_times[sourceIndex()]}
function markedName(name){name=centeredName(powerName(name));if(isJudgeNine()&&!judgeElectricEnabled)name=name.replace(/(\.[^.]+)$/,'-no-electric$1');let suffix=cycleMode()==='sync'?'-clapping-sync':cycleMode()==='dirty'?'-dirty-loop':'-minimum-cycle';return useMinimum()?name.replace(/(\.[^.]+)$/,`${suffix}$1`):name}
function sizedName(name){return name.replace(/(\.[^.]+)$/,`-${downloadsize.value}px$1`)}
function isClap(c){return c.action_key==='results-clap_source'||c.action_key.endsWith('-results-clap_source')} function updateCycleInfo(){if(current<0)return;let c=clips[current];minimumcycle.disabled=!c.minimum_cycle;dirtycycle.disabled=!c.dirty_cycle;
electriccontrols.hidden=!isJudgeNine();judgeelectric.checked=judgeElectricEnabled;
document.getElementById('movementhint').hidden=!c.action_key.startsWith('movement-');
document.getElementById('sequencehint').hidden=!c.sequence;
document.getElementById('sequencehint').textContent=c.sequence?`Combined sequence: ${c.sequence.policy} Uncheck Hide partial animations to see the individual phases. Repeat Preview repeats the entire sequence.`:'';
document.getElementById('effecthint').hidden=!c.character_effects?.length&&!c.sleep_bubbles;
document.getElementById('effecthint').textContent=c.character_effects?.length?`${[...new Set(c.character_effects.map(e=>e.name))].join(', ')} effects are included in the preview and GIF/PNG downloads. Extra particles and collision responses are not included yet.`:'';
if(c.sleep_bubbles)document.getElementById('effecthint').textContent=c.sleep_bubbles.entrance_time_offset?'Sleep bubbles are included. The wait loop replays the fading bubbles left from the victory entrance.':'Sleep bubbles follow the original victory timing and are included in GIF/PNG downloads.';
document.getElementById('itemhint').hidden=!c.held_item;
document.getElementById('itemhint').textContent=c.held_item?`${c.held_item.name} is included in the preview and GIF/PNG downloads. ${c.held_item.charged_preset?'Needles use a six-needle charged preset. ':''}${c.held_item.behavior==='needle-release'?'Needles follow a deterministic free-flight path and leave the image; collisions are not simulated.':'Projectile and collision effects are not simulated.'}`:'';
jumpcontrols.hidden=!isHop();centerjump.checked=centerJumpEnabled;
techcontrols.hidden=!c.action_key.startsWith('tech-');groundeffects.disabled=!c.ground_effect;
techhint.textContent=c.ground_effect?"Towards/away follow the character's facing. With impacts on, the whole effect fits; turning them off zooms in on the character. Fighter flashes remain with impacts off. Extra dust/sparkle particles are not included yet.":'Lying animations have no ground-impact effect.';
synccycle.disabled=!c.sync_cycle;document.getElementById('clapmodes').hidden=!isClap(c);
if(cycleMode()==='full')checkMode('full');
let short=activeCycle()||c.minimum_cycle||c.dirty_cycle;
cyclehint.textContent=cycleMode()==='sync'?`42 frames / 0.84s. ${short.repeats} repeats; ${short.hold_frames_per_cycle} held frames per repeat; moving speed ${short.moving_rate.toFixed(2)}x. ${short.selection}.`:
short?`${short.length} frames / ${(short.length/c.fps).toFixed(2)}s instead of ${c.lazy?c.frame_count:c.frames.length} frames. ${short.dirty?'Dirty review: '+short.failed_checks.join('; '):'Edited repeat; subtle motion may differ.'}`:
(isClap(c)?'No shorter repeat passed the checks.':'Minimum cycle is available for repeating claps.'); if(short&&short.timing_from)cyclehint.textContent+=` Uses ${short.timing_from}'s original clap timing.`;
scrub.max=frameCount()-1;
document.getElementById('meta').textContent=`${c.symbol} / ${frameCount()} frames at ${c.fps} fps / ${(frameCount()/c.fps).toFixed(2)}s / ${cycleMode()==='sync'?'clapping-sync alteration':cycleMode()==='dirty'?'minimum loop (dirty/jittery)':useMinimum()?'minimum cycle (edited loop)':c.authored_loop?'full authored loop':'one-shot action'}`}
function exportURL(kind,scope,hd=false){let c=clips[current];let query=new URLSearchParams({character:c.character,action:c.action_key,
costume:String(c.costume_id),size:downloadsize.value,kind,scope,frame:String(index),cycle:cycleMode()});
if(hd){query.set('size',hdsize.value);query.set('render','hd');query.set('crop',cropTransparentBorder?'on':'off')}
if(isHop())query.set('center',centerSetting());
if(isJudgeNine())query.set('electric',electricSetting());
if(hasPower()&&scope!=='all'&&!(scope==='colors'&&includeKirbyHats))query.set('power',powerSetting());
if(scope!=='costume'&&includeKirbyHats)query.set('hats','all');
if(c.action_key.startsWith('tech-'))query.set('effects',effectSetting());
if(hasAngle()){['pitch','yaw','roll'].forEach((key,i)=>query.set(key,String(angles[i])))}return `${exportBase}/export?${query}`}
function updateDownloads(){if(current<0)return;let c=clips[current];let a=animations.find(a=>a.key===c.action_key&&a.character===c.character);
let original=Number(downloadsize.value)===nativeDefaultSize&&!useMinimum()&&!hasAngle()&&!hasPower()&&!c.lazy;
gif.href=original?c.gif:exportURL('gif','costume');gif.download=sizedName(angleName(effectName(markedName(c.download_name))));
open.href=original?c.gif:exportURL('gif','costume')+'&view=1';
const colorHats=includeKirbyHats&&c.character==='kirby';
archive.href=original&&!colorHats?a.zip:exportURL('gif','colors');archive.download=sizedName(angleName(effectName(batchMarkedName(a.download_name,'colors'))));
archive.textContent=`Download this animation — ${a.color_count*(colorHats?powers.length:1)} GIFs${colorHats?' (all Kirby hats/colors)':''}`;
allzip.href=exportURL('gif','all');
const group=batchGroups.get(c.batch_family);allzip.hidden=!group||group.count===0;
const count=group?(cycleMode()==='sync'?group.sync:group.count)+(includeKirbyHats?group.kirby*(powers.length-1):0):0;
allzip.textContent=`Download all ${group?.label||'matching animations'}${cycleMode()==='sync'?' (synced)':''} — ${count} GIFs`;
let allName='melee-all-characters-'+(group?.label||'matching').toLowerCase().replace(/[^a-z0-9]+/g,'-');
if(cycleMode()==='sync')allName='melee-all-characters';
allzip.download=sizedName(angleName(effectName(batchMarkedName(allName+'.zip','all'))));
still.href=original?c.frames[index]:exportURL('png','costume');
still.download=sizedName(angleName(effectName(markedName(c.download_name)).replace('.gif',`-frame-${String(index+1).padStart(4,'0')}.png`)));
framezip.href=original&&!colorHats?`${a.stills}/frame-${String(index+1).padStart(4,'0')}.zip`:exportURL('png','colors');
framezip.download=sizedName(angleName(effectName(batchMarkedName(`${c.character}-${c.action_key.replaceAll('_','-')}-frame-${String(index+1).padStart(4,'0')}-all-colors.zip`,'colors'))));
hdstill.href=exportURL('png','costume',true);hdcolors.href=exportURL('png','colors',true);
hdstill.download=still.download.replace(/-\d+px\.png$/,`${cropTransparentBorder?'-cropped':''}-hd-${hdsize.value}px.png`);
hdcolors.download=framezip.download.replace(/-\d+px\.zip$/,`${cropTransparentBorder?'-cropped':''}-hd-${hdsize.value}px.zip`)}
let batchBusy=false,pendingBatch=null;
const batchButtons=[gif,still,archive,framezip,allzip,hdstill,hdcolors];
function playerHandoff(batch=null){let c=clips[current];let query=new URLSearchParams({character:c.character,action:c.action_key,costume:String(c.costume_id),cycle:cycleMode(),frame:String(index),playing:String(playing),repeat:String(loop.checked),size:downloadsize.value,hdsize:hdsize.value,crop:cropTransparentBorder?'on':'off',pitch:String(angles[0]),yaw:String(angles[1]),roll:String(angles[2]),effects:effectSetting(),power:powerSetting(),center:centerSetting(),partials:partialsHidden?'hide':'show',hats:batchHats()});if(isJudgeNine())query.set('electric',electricSetting());if(batch)query.set('batch',batch);return `${exportBase}/player.html#${query}`}
function runPendingBatch(){if(location.protocol!=='http:'||!pendingBatch)return;const button={gif:archive,png:framezip,all:allzip,'single-gif':gif,'single-png':still,'hd-single':hdstill,'hd-colors':hdcolors}[pendingBatch];pendingBatch=null;if(button&&!button.hidden)batchDownload({preventDefault(){}},button)}
function batchState(busy,active){batchBusy=busy;for(const button of batchButtons){button.ariaDisabled=String(busy);button.ariaBusy=String(busy&&button===active);button.tabIndex=busy?-1:0;button.className=(button.className||'download').replace(/\s*busy\b/g,'')+(busy&&button===active?' busy':'')}}
function downloadProgress(state){document.getElementById('downloadprogress').hidden=false;document.getElementById('downloadbar').value=Math.max(0,Math.min(100,Number(state.percent)||0));document.getElementById('downloadcount').textContent=state.total?`Animations ready: ${state.completed}/${state.total} · Files ready: ${state.files_completed}/${state.total}`:'';const frames=state.frames_total?` · ${state.frames_done}/${state.frames_total} ${state.unit||'frames'}`:'';document.getElementById('downloadstatus').textContent=`${state.phase||'Preparing download'}${state.label?' · '+state.label:''}${frames}`}
async function prepareDownload(href){const id=typeof crypto!=='undefined'&&crypto.randomUUID?crypto.randomUUID():`download-${Date.now()}-${Math.random().toString(36).slice(2)}`;let stopped=false,timer=null;
const responsePromise=fetch(href.replace('/export?','/prepare-export?')+`&progress=${id}`);
async function poll(){if(stopped)return;try{const response=await fetch(`${exportBase}/export-progress?id=${id}`);if(response.ok){const state=await response.json();if(!stopped)downloadProgress(state)}}catch(error){}finally{if(!stopped&&typeof setTimeout==='function')timer=setTimeout(poll,500)}}
if(typeof setTimeout==='function')timer=setTimeout(poll,250);
try{const response=await responsePromise;if(!response.ok)throw Error(`Preparation failed (${response.status}). Try again.`);const result=await response.json();if(result.progress)downloadProgress(result.progress);return exportBase+result.url}
finally{stopped=true;if(timer!==null&&typeof clearTimeout==='function')clearTimeout(timer)}}
async function batchDownload(event,button){event.preventDefault();if(batchBusy)return;
const href=button.href,filename=button.download,status=document.getElementById('downloadstatus');
batchState(true,button);downloadProgress({percent:0,phase:button===hdstill||button===hdcolors?'Preparing selected HD frame…':'Preparing download…'});
try{let ready=href;
if(location.protocol!=='http:'&&href.includes('/export?')){location.href=playerHandoff(button===hdstill?'hd-single':button===hdcolors?'hd-colors':button===gif?'single-gif':button===still?'single-png':button===framezip?'png':button===allzip?'all':'gif');return}
if(href.includes('/export?')){ready=await prepareDownload(href)}
else if(location.protocol==='http:'){const response=await fetch(href,{method:'HEAD'});if(!response.ok)throw Error(`Download unavailable (${response.status}).`)}
const link=document.createElement('a');link.href=ready;link.download=filename;document.body.append(link);link.click();link.remove();document.getElementById('downloadbar').value=100;status.textContent='Download ready. Your browser is saving the file.';
}catch(error){status.textContent=`${error.message} Open the local download player if it is not running.`}
finally{batchState(false,button)}}
for(const button of batchButtons)button.onclick=event=>batchDownload(event,button);
function show(){if(current<0||previewUnavailable())return;let c=clips[current];let src=framePath();if(lastImage!==src){frame.src=src;lastImage=src}scrub.value=index;
updateDownloads();
still.hidden=playing;framezip.hidden=playing;hdstill.hidden=playing;hdcolors.hidden=playing;hdcontrols.hidden=playing;hdcroplabel.hidden=playing;
// A real image receives the browser's native Save image as operation. The
// timed PNG underneath preserves scrubbing/repeat semantics; the save target
// is the actual GIF while playing and the exact PNG while paused. Remove the
// irrelevant GIF frame query so animation ticks never refetch the same GIF.
let savedSrc=playing?open.href.replace(/([?&])frame=\d+(&|$)/,'$1').replace(/[?&]$/,''):still.href;
if(saveimage.getAttribute?saveimage.getAttribute('src')!==savedSrc:saveimage.src!==savedSrc)saveimage.src=savedSrc;
saveimage.title=playing?'Right-click to save transparent GIF':'Right-click to save transparent PNG';
clock.textContent=`${index+1}/${frameCount()} / source ${sourceTime().toFixed(2)}`}
function select(render=true,keepDownloadSize=false){current=clips.findIndex(c=>c.character===character.value&&c.action_key===action.value&&String(c.costume_id)===costume.value);
updateNativeSize(keepDownloadSize);
index=0;carry=0;last=performance.now();
let a=animations.find(a=>a.key===action.value&&a.character===character.value);archive.href=a.zip;archive.download=a.download_name;
archive.textContent=`Download this animation — ${a.color_count} colors`;
if(current<0){playing=false;play.textContent='Play';frame.hidden=true;gif.hidden=true;open.hidden=true;
still.hidden=true;framezip.hidden=true;hdstill.hidden=true;hdcolors.hidden=true;hdcontrols.hidden=true;hdcroplabel.hidden=true;
document.getElementById('meta').textContent='This animation/color has not been rendered yet.';return}
let c=clips[current];frame.hidden=false;gif.hidden=false;open.hidden=false;scrub.max=c.frames.length-1;
loop.checked=true;playing=true;play.textContent='Pause';
gif.href=c.gif;gif.download=c.download_name;gif.textContent=`Download GIF / ${c.costume_label}`;open.href=c.gif;
updateCycleInfo();
c.frames.forEach(src=>{let image=new Image();image.src=src});updateDownloads();if(render)loadRotation()}
character.onchange=()=>{resetViewForNewAnimation();colors();actions();select()};animationtype.onchange=()=>{resetViewForNewAnimation();actions();select()};
kirbypower.onchange=()=>{kirbyPower=kirbypower.value;loadRotation()};
action.onchange=()=>{resetViewForNewAnimation();animationtype.value=typeForAction(action.value);actions();select()};costume.onchange=select;
hidepartials.onchange=()=>{let old=action.value;partialsHidden=hidepartials.checked;actions();if(action.value!==old){resetViewForNewAnimation();select()}};
function updateNativeSize(keep=false){const size=['victory','taunt','clapping'].includes(typeForAction(action.value))?1024:512;if(!keep&&Number(downloadsize.value)===nativeDefaultSize)downloadsize.value=String(size);nativeDefaultSize=size;const names={128:'Extra small',256:'Small',512:'Medium',1024:'Large',2048:'X-Large'};for(const option of downloadsize.options){const n=Number(option.value);option.textContent=`${n===size?'★ ':n===2048?'⚠ ':''}${names[n]} (${n} × ${n}${n===size?', native render':''})`}updateSizeWarning()}
function updateSizeWarning(){document.getElementById('sizewarning').hidden=downloadsize.value!=='2048';const notice=document.getElementById('upsizenotice');notice.hidden=Number(downloadsize.value)<=nativeDefaultSize;notice.textContent=`Upsized from the ${nativeDefaultSize} × ${nativeDefaultSize} render; no additional detail.`}
downloadsize.onchange=()=>{updateSizeWarning();show()};
hdsize.onchange=()=>show();
cropborder.onchange=()=>{cropTransparentBorder=cropborder.checked;show()};
kirbymode.onchange=()=>{includeKirbyHats=kirbymode.checked;show()};
groundeffects.onchange=()=>{groundEffectsEnabled=groundeffects.checked;if(clips[current].ground_effect)loadRotation()};
centerjump.onchange=()=>{centerJumpEnabled=centerjump.checked;if(isHop())loadRotation()};
function changeCycle(){if(current<0)return;index=0;carry=0;last=performance.now();updateCycleInfo();let short=activeCycle();if(short&&short.frames)short.frames.forEach(src=>{let image=new Image();image.src=src});if(hasAngle()||hasPower()||clips[current].lazy)loadRotation();else show()}
[fullcycle,minimumcycle,dirtycycle,synccycle].forEach((r,i)=>r.onchange=()=>{if(r.checked){checkMode(['full','minimum','dirty','sync'][i]);changeCycle()}});
play.onclick=()=>{if(current<0)return;playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now();carry=0;show();refreshAnglePreview()};
restart.onclick=()=>{if(current<0)return;index=0;last=performance.now();carry=0;playing=true;play.textContent='Pause';show();refreshAnglePreview()};
scrub.oninput=()=>{if(current<0)return;index=Number(scrub.value);playing=false;play.textContent='Play';show();refreshAnglePreview()};
function tick(now){if(current>=0&&playing&&!previewUnavailable()){let c=clips[current];carry+=Math.min(now-last,250);let step=1000/c.fps;
while(carry>=step){carry-=step;if(index+1<frameCount())index++;else if(loop.checked)index=0;else{playing=false;play.textContent='Play';break}}show()}
last=now;requestAnimationFrame(tick)}
function restoreSelection(){let incoming=new URLSearchParams((location.hash||'').slice(1));
includeKirbyHats=incoming.get('hats')==='all';kirbymode.checked=includeKirbyHats;
pendingBatch=['gif','png','all','single-gif','single-png','hd-single','hd-colors'].includes(incoming.get('batch'))?incoming.get('batch'):null;
// Consume this one-time handoff so refresh/reopen cannot replay old angles.
if(location.hash&&typeof history!=='undefined')history.replaceState(null,'',location.pathname+location.search);
if(characters.some(c=>c.slug===incoming.get('character'))){character.value=incoming.get('character');colors();actions()}
if(character.value==='kirby'&&powers.some(p=>p.slug===incoming.get('power'))){kirbyPower=incoming.get('power');kirbypower.value=kirbyPower}
let requested=animations.find(a=>a.character===character.value&&a.key===incoming.get('action')&&!a.unavailable);
if(['show','hide'].includes(incoming.get('partials')))partialsHidden=incoming.get('partials')==='hide';
else if(requested?.partial)partialsHidden=false;
hidepartials.checked=partialsHidden;
if(requested){animationtype.value=typeForAction(requested.key);actions(requested.key)}
if(characters.find(c=>c.slug===character.value).costumes.some(c=>String(c.id)===incoming.get('costume')))costume.value=incoming.get('costume');
if(['full','minimum','dirty','sync'].includes(incoming.get('cycle')))checkMode(incoming.get('cycle'));
if(['128','256','512','1024','2048'].includes(incoming.get('size')))downloadsize.value=incoming.get('size');
if(['2048','4096'].includes(incoming.get('hdsize')))hdsize.value=incoming.get('hdsize');
if(['on','off'].includes(incoming.get('crop'))){cropTransparentBorder=incoming.get('crop')==='on';cropborder.checked=cropTransparentBorder}
if(action.value.startsWith('tech-')&&['on','off'].includes(incoming.get('effects'))){groundEffectsEnabled=incoming.get('effects')==='on';groundeffects.checked=groundEffectsEnabled}
if(['on','off'].includes(incoming.get('electric'))){judgeElectricEnabled=incoming.get('electric')==='on';judgeelectric.checked=judgeElectricEnabled}
if(['movement-fullhop_source','movement-shorthop_source'].includes(action.value)&&['on','off'].includes(incoming.get('center'))){centerJumpEnabled=incoming.get('center')==='on';centerjump.checked=centerJumpEnabled}
updateSizeWarning();
select(false,incoming.has('size'));
let savedFrame=Number(incoming.get('frame'));if(Number.isInteger(savedFrame)&&savedFrame>=0&&savedFrame<frameCount())index=savedFrame;
if(incoming.has('playing')){playing=incoming.get('playing')==='true';play.textContent=playing?'Pause':'Play'}
if(incoming.has('repeat'))loop.checked=incoming.get('repeat')==='true';
let savedAngles=['pitch','yaw','roll'].map(key=>Number(incoming.get(key)||0));
if(savedAngles.every(v=>Number.isFinite(v)&&Math.abs(v)<=180)&&savedAngles.some(v=>v!==0)){
angleInputs.forEach((input,i)=>{input.value=String(savedAngles[i]);input.oninput()});angles=savedAngles.map(v=>v===180?-180:v);loadRotation();
}else loadRotation()}
restoreSelection();requestAnimationFrame(tick);
</script></html>'''


def arrange_animation_choices(animations, catalog):
    """Group connected sequence families and mark their partial menu choices.

    Keys come from actual source submotions, never duplicate display names.
    This is presentation metadata only; catalog/export identities stay intact.
    """
    lookup={(a['character'],a['key']):a for a in animations}
    groups={}
    for fighter in catalog['characters']:
        slug=fighter['character'];parent={};combos={}
        def root(key):
            parent.setdefault(key,key)
            if parent[key]!=key:parent[key]=root(parent[key])
            return parent[key]
        for action in fighter['actions']:
            if not action.get('available') or not action.get('sequence'):continue
            key=action['key'];prefix=key.split('-',1)[0]
            parts=[f'{prefix}-{p["clip"]["animation_id"]}_source' for p in action['actors'][0]['sequence']['phases']]
            # Alternate Kirby Cutter ground/air states belong to the same
            # multipart move, although the neutral recipe switches air/ground.
            if slug=='kirby' and action['name'] in ('SpecialHi1','SpecialAirHi1'):
                parts.extend(a['key'] for a in fighter['actions'] if a['available'] and not a.get('sequence')
                             and re.fullmatch(r'Special(?:Air)?Hi[1-4]',a['name']))
            parts=list(dict.fromkeys(p for p in parts if (slug,p) in lookup))
            combos[key]=parts
            for part in parts:parent[root(part)]=root(key)
        families=defaultdict(list)
        for key in parent:families[root(key)].append(key)
        for keys in families.values():
            combined=[a['key'] for a in animations if a['character']==slug and a['key'] in keys and a['key'] in combos]
            partial=[a['key'] for a in animations if a['character']==slug and a['key'] in keys and a['key'] not in combos]
            ordered=[lookup[(slug,key)] for key in combined+partial]
            for key in partial:
                preferred=next((c for c in combined if combos[c][0]==key),combined[0])
                lookup[(slug,key)].update(partial=True,combined_key=preferred)
            for key in keys:groups[(slug,key)]=ordered
    result=[];seen=set()
    for animation in animations:
        for choice in groups.get((animation['character'],animation['key']),[animation]):
            identity=(choice['character'],choice['key'])
            if identity not in seen:result.append(choice);seen.add(identity)
    return result


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
        from .roster import color_label
        color=color_label({'file':manifest.get('source_model_archive','PlMrNr.dat'),'costume_id':costume_id},
                          24 if slug=='game-and-watch' else 0 if slug=='mario' else None)
        filename = f"{slug}-{key.replace('_','-')}-costume-{costume_id:02d}-{color.split()[0].lower()}.gif"
        clips.append({"character":slug,"character_label":name,"action_key": key, "costume_id": costume_id, "costume_label": color,
                      "fps": manifest["fps"], "period": manifest["source_period_frames"],
                      "master_size":manifest['size'],
                      "authored_loop": manifest["authored_loop"], "symbol": manifest["source_symbol"],
                      "sleep_bubbles":manifest.get('sleep_bubbles'),
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
    if args.require_all:
        from .render_settings import native_size
        if any(c['master_size']!=native_size(c['action_key'],c.get('animation_type')) for c in clips):
            parser.error('Rebuild native results masters with roster_batch --resume before packaging')
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
                           'type':group[0]['animation_type'],'lazy':True,'color_count':len(group),
                           'download_name':filename,'zip':'','stills':''})
    catalog_path = args.root/'attack-catalog.json'
    if catalog_path.is_file():
        catalog=json.loads(catalog_path.read_text())
        for fighter in catalog['characters']:
            for a in fighter['actions']:
                if not a['available']:
                    animations.append({'character':fighter['character'],'key':a['key'],'label':a['label'],
                                       'type':a.get('animation_type','attack'),'unavailable':a['unavailable_reason']})
        animations=arrange_animation_choices(animations,catalog)
    clips.extend(attack_clips)
    for slug in dict.fromkeys(c['character'] for c in attack_clips):
        if any(c['slug']==slug for c in characters):continue
        owned=[c for c in attack_clips if c['character']==slug]
        characters.append({'slug':slug,'label':owned[0]['character_label'],'costumes':[
            {'id':cid,'label':next(c['costume_label'] for c in owned if c['costume_id']==cid)}
            for cid in sorted({c['costume_id'] for c in owned})]})
    characters.sort(key=lambda character: character['label'].casefold())
    from .batch_exports import enrich
    catalog_path=args.root/'attack-catalog.json'
    clips=enrich(clips,json.loads(catalog_path.read_text()) if catalog_path.is_file() else {})
    safe_json = lambda value: json.dumps(value).replace("<", "\\u003c")
    from .kirby_powers import powers
    content = TEMPLATE.replace("__CLIPS__",safe_json(clips)).replace("__ANIMATIONS__",safe_json(animations)).replace("__CHARACTERS__",safe_json(characters)).replace('__POWERS__',safe_json(powers()))
    output.write_text(content,encoding="utf-8")
    print(f"Offline player: {output} ({len(clips)} clips, {len(animations)} animations, {len(characters)} characters)")
    print(f"GIF download bundles: {downloads}")


if __name__ == "__main__":
    main()
