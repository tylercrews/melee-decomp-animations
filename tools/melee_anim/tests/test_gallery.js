// Test the generated player's control/timer logic without a browser connector.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = path.resolve('build/melee_anim/preview/player.html');
const html = fs.readFileSync(page, 'utf8');
assert.match(html,/<option value="tech">Knockdown<\/option>/);
assert.match(html,/<option value="movement">Movement<\/option>/);
assert.match(html,/\.stage\{background:transparent;/);
assert(!html.includes('repeating-conic-gradient'),'preview must have no checkerboard');
assert.match(html,/<option value="2048">⚠ X-Large \(2048 × 2048\)<\/option>/);
assert.match(html,/#sizewarning\{color:#b59a19\}/);
assert.match(html,/<small id="sizewarning"[^>]* hidden>Extremely large GIF files<\/small>/);
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = Object.fromEntries(['centerjump','jumpcontrols','movementhint','kirbypower','powerlabel','groundeffects','techcontrols','techhint','sizewarning','saveimage','animationtype','actionlabel','pitch','yaw','roll','pitchvalue','yawvalue','rollvalue','rotationstatus','applyangle','resetangle','downloadpanel','fullcycle','synccycle','clapmodes','dirtycycle','minimumcycle','cyclehint','downloadsize', 'servicehint', 'character', 'still', 'framezip', 'action', 'costume', 'frame', 'play', 'restart', 'loop', 'scrub', 'time', 'gif', 'animationzip', 'allzip', 'open', 'meta']
  .map(id => [id, {value: '0', textContent: '', checked: false, options: [], append(option) {this.options.push(option);}}]));
const context = vm.createContext({document: {getElementById: id => elements[id], createElement: () => ({})},
  location: {protocol:'file:'}, URLSearchParams,
  performance: {now: () => 0}, Image: class {}, requestAnimationFrame: callback => {context.nextFrame = callback;}});
vm.runInContext(script, context);
const data = expression => vm.runInContext(expression, context);
assert.equal(elements.sizewarning.hidden,true,'default size has no warning');
assert.equal(elements.action.options.length, 1);
assert.equal(elements.actionlabel.hidden, true);
elements.animationtype.value="victory";elements.animationtype.onchange();
assert.equal(elements.action.options.length, 6);assert.equal(elements.actionlabel.hidden,false);
elements.animationtype.value="clapping";elements.animationtype.onchange();
assert.equal(elements.costume.options.length, 5);
assert(elements.character.options.length>=1);
assert.equal(elements.character.options.length, 32);
assert.equal(elements.powerlabel.hidden,true);
assert.equal(elements.kirbypower.options.length,26);
assert.equal(elements.kirbypower.options[0].value,'none');
const characterLabels = elements.character.options.map(option => option.textContent);
assert.deepEqual(characterLabels, [...characterLabels].sort((a,b) => a.localeCompare(b,'en')));
assert.equal(elements.character.value, 'mario', 'alphabetical ordering preserves the default character');
assert(elements.character.options.some(option => option.value === 'zelda'));
assert(elements.character.options.some(option => option.value === 'sheik'));
assert.match(elements.frame.src, /frame_0000.png$/);
assert.equal(elements.saveimage.src,data('clips[current].gif'),'native right-click target is the actual GIF while playing');
elements.play.onclick();
assert.equal(data('playing'), false);
assert.equal(elements.play.textContent, 'Play');
elements.scrub.value = '3';
elements.scrub.oninput();
assert.equal(data('index'), 3);
assert.match(elements.frame.src, /frame_0003.png$/);
assert.equal(elements.saveimage.src,elements.still.href,'native right-click target is the exact PNG while paused');
elements.restart.onclick();
assert.equal(data('index'), 0);
assert.equal(data('playing'), true);
context.nextFrame(40);
assert.equal(data('index'), 2);
elements.action.value = 'victory1_source';
elements.action.onchange();
assert.equal(elements.loop.checked, true);
const count = data('clips[current].frames.length');
elements.scrub.value = String(count - 1);
elements.scrub.oninput();
elements.play.onclick();
context.nextFrame(40);
assert.equal(data('playing'), true, 'one-shot previews repeat by default');
assert(data('index') < count - 1, 'repeat wraps to the beginning');
elements.loop.checked = false;
elements.scrub.value = String(count - 1);
elements.scrub.oninput();
elements.play.onclick();
context.nextFrame(40);
assert.equal(data('playing'), false);
assert.equal(data('index'), count - 1);
for (const clip of data('clips.filter(c=>!c.lazy)')) {
  for (const frame of clip.frames) assert(fs.existsSync(path.join(path.dirname(page), frame)), frame);
  assert(fs.existsSync(path.join(path.dirname(page), clip.gif)), clip.gif);
}

for (const clip of data('clips.filter(c=>!c.lazy)')) {
  elements.character.value=clip.character;elements.character.onchange();
  elements.costume.value = String(clip.costume_id);
  elements.costume.onchange();
  elements.action.value = clip.action_key;
  elements.action.onchange();
  assert.equal(data('clips[current].costume_id'), clip.costume_id);
  assert.equal(elements.costume.value, String(clip.costume_id), 'changing animations must preserve the chosen color');
  assert.equal(elements.gif.href, clip.gif);
  assert.equal(elements.gif.download, clip.download_name.replace('.gif','-256px.gif'));
  assert.match(elements.gif.download, /\.gif$/);
  elements.scrub.value='3';elements.scrub.oninput();
  assert.equal(elements.still.href,clip.frames[3]);assert.equal(elements.still.hidden,false);
  assert.equal(elements.framezip.hidden,false);
  assert.match(elements.still.download,/frame-0004-256px.png$/);
  assert(fs.existsSync(path.join(path.dirname(page),elements.framezip.href)));
  const a = data('animations.find(a => a.key === action.value && a.character === character.value)');
  assert.equal(elements.animationzip.href, a.zip);
  assert.equal(elements.animationzip.download, a.download_name.replace('.zip','-256px.zip'));
  assert(fs.existsSync(path.join(path.dirname(page), a.zip)));
  elements.play.onclick();
  assert.equal(elements.still.hidden,true);
  assert.equal(elements.framezip.hidden,true);
}
elements.character.value='mario';elements.character.onchange();
elements.action.value='victory3_source';elements.action.onchange();
elements.scrub.value='67';elements.scrub.oninput();
assert.match(elements.time.textContent,/^68\/101/);
assert.match(elements.still.href,/frame_0067.png$/);
assert.match(elements.still.download,/frame-0068-256px.png$/);
assert.match(elements.framezip.href,/frame-0068.zip$/);
for (const size of [128,512,1024,2048]) {
  elements.downloadsize.value=String(size);elements.downloadsize.onchange();
  assert.equal(elements.sizewarning.hidden,size!==2048,'warning appears only for X-Large');
  assert.equal(data('index'),67,'size changes must preserve the paused frame');
  assert.equal(data('playing'),false);
  assert.equal(elements.still.hidden,false);
  for (const [id,kind,scope] of [['gif','gif','costume'],['animationzip','gif','colors'],['allzip','gif','all'],['still','png','costume'],['framezip','png','colors']]) {
    const url=new URL(elements[id].href);
    assert.equal(url.searchParams.get('size'),String(size));
    assert.equal(url.searchParams.get('kind'),kind);
    assert.equal(url.searchParams.get('scope'),scope);
    assert.equal(url.searchParams.get('frame'),'67');
    assert.equal(url.searchParams.get('character'),'mario');
    assert.equal(url.searchParams.get('action'),'victory3_source');
    assert.match(elements[id].download,new RegExp(`-${size}px\\.(gif|png|zip)$`));
  }
}
elements.downloadsize.value='256';elements.downloadsize.onchange();
assert.equal(elements.sizewarning.hidden,true,'switching away from X-Large hides the warning');
assert.match(elements.still.href,/frame_0067.png$/);
assert(html.includes('download="melee-all-characters-all-animations.zip"'));
assert(fs.existsSync(path.join(path.dirname(page), 'downloads/melee-all-characters-all-animations.zip')));
for (const [slug,length] of [['luigi',20],['kirby',34],['link',12]]) {
  elements.character.value=slug;elements.character.onchange();
  elements.action.value='results-clap_source';elements.action.onchange();
  elements.scrub.value='3';elements.scrub.oninput();
  assert.equal(elements.minimumcycle.disabled,false);
  elements.minimumcycle.checked=true;elements.minimumcycle.onchange();
  const start=data('clips[current].minimum_cycle.start');
  assert.equal(data('playing'),false);
  assert.equal(data('frameCount()'),length);
  assert.equal(elements.scrub.max,length-1);
  assert.equal(elements.frame.src,data(`clips[current].frames[${start}]`));
  assert.equal(new URL(elements.gif.href).searchParams.get('cycle'),'minimum');
  assert.equal(new URL(elements.open.href).searchParams.get('cycle'),'minimum');
  assert.equal(new URL(elements.open.href).searchParams.get('view'),'1');
  assert.match(elements.gif.download,/-minimum-cycle-256px.gif$/);
  elements.scrub.value=String(length-1);elements.scrub.oninput();
  assert.equal(new URL(elements.still.href).searchParams.get('frame'),String(length-1));
  elements.play.onclick();context.nextFrame(20);
  assert.equal(data('index'),0,'short loops wrap without an extra endpoint');
  elements.fullcycle.checked=true;elements.fullcycle.onchange();
  assert.equal(data('frameCount()'),data('clips[current].frames.length'));
  assert.equal(elements.gif.href,data('clips[current].gif'));
}
elements.character.value='mario';elements.character.onchange();
elements.action.value='taunt_source';elements.action.onchange();
assert.equal(elements.minimumcycle.disabled,true);
assert.equal(elements.minimumcycle.checked,false);
assert(!html.includes('Dirty loop candidates to review'));assert(!html.includes('dirtylist'));
const dirtyCharacters=data('characters.filter(ch=>clips.some(c=>c.character===ch.slug&&c.dirty_cycle))');
assert.equal(dirtyCharacters.length,11);
for (const ch of dirtyCharacters) {
  elements.character.value=ch.slug;elements.character.onchange();
  elements.action.value='results-clap_source';elements.action.onchange();
  elements.dirtycycle.checked=true;elements.dirtycycle.onchange();
  assert.equal(elements.action.value,'results-clap_source');
  assert.equal(elements.dirtycycle.checked,true);
  assert.equal(elements.minimumcycle.checked,false);
  const short=data('clips[current].dirty_cycle');
  assert.equal(data('frameCount()'),short.length);
  assert.equal(elements.frame.src,data(`clips[current].frames[${short.start}]`));
  assert.equal(new URL(elements.gif.href).searchParams.get('cycle'),'dirty');
  assert.match(elements.gif.download,/-dirty-loop-256px.gif$/);
  assert(elements.cyclehint.textContent.includes(short.failed_checks[0]));
  elements.scrub.value=String(short.length-1);elements.scrub.oninput();
  assert.equal(new URL(elements.still.href).searchParams.get('frame'),String(short.length-1));
  elements.play.onclick();context.nextFrame(20);
  assert.equal(data('index'),0);
  elements.fullcycle.checked=true;elements.fullcycle.onchange();
  assert.equal(elements.gif.href,data('clips[current].gif'));
}
assert.equal((html.match(/type="radio" name="clapmode"/g)||[]).length,4);
for (const clip of data('clips.filter(c=>c.sync_cycle)')) {
  elements.character.value=clip.character;elements.character.onchange();
  elements.action.value='results-clap_source';elements.action.onchange();
  elements.costume.value=String(clip.costume_id);elements.costume.onchange();
  elements.synccycle.checked=true;elements.synccycle.onchange();
  assert.equal(data('cycleMode()'),'sync');
  assert.equal(data('frameCount()'),42);
  assert.equal(elements.scrub.max,41);
  assert.equal(elements.frame.src,clip.sync_cycle.frames[0]);
  assert.equal([elements.fullcycle,elements.minimumcycle,elements.dirtycycle,elements.synccycle].filter(r=>r.checked).length,1);
  assert.match(elements.meta.textContent,/42 frames at 50 fps \/ 0.84s/);
  assert.equal(new URL(elements.gif.href).searchParams.get('cycle'),'sync');
  assert.match(elements.gif.download,/-clapping-sync-256px.gif$/);
  elements.scrub.value='41';elements.scrub.oninput();
  assert.equal(elements.frame.src,clip.sync_cycle.frames[41]);
  assert.equal(new URL(elements.still.href).searchParams.get('frame'),'41');
  elements.play.onclick();context.nextFrame(20);
  assert.equal(data('index'),0);
  elements.fullcycle.checked=true;elements.fullcycle.onchange();
}
elements.action.value='taunt_source';elements.action.onchange();
assert.equal(elements.clapmodes.hidden,true);
assert.equal(data('cycleMode()'),'full');
// Served pages use their own origin, including a user-selected server port.
const servedElements=Object.fromEntries(Object.keys(elements).map(id=>[id,
  {value:'90',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
const requests=[];
let servedPageShow;
const servedContext=vm.createContext({document:{getElementById:id=>servedElements[id],createElement:()=>({})}, location:{protocol:'http:'}, URLSearchParams,
    addEventListener:(name,callback)=>{if(name==='pageshow')servedPageShow=callback},
    performance:context.performance, Image:context.Image, requestAnimationFrame:()=>{},
    fetch:url=>new Promise(resolve=>requests.push({url,resolve}))});
vm.runInContext(script,servedContext);
// Fresh loads override stale restored form values, even if restoration is late.
for(const id of ['pitch','yaw','roll'])assert.equal(servedElements[id].value,'0');
for(const id of ['pitch','yaw','roll'])servedElements[id].value='75';
servedPageShow({persisted:false});
for(const id of ['pitch','yaw','roll']){
  assert.equal(servedElements[id].value,'0');assert.equal(servedElements[id+'value'].textContent,'0°');
}
assert.equal(servedElements.servicehint.hidden,true);
servedElements.downloadsize.value='512';servedElements.downloadsize.onchange();
assert(servedElements.gif.href.startsWith('/export?'));
console.log('Playback, color/frame retention, sized GIF/PNG downloads, ZIP links, and file/HTTP origins: PASS');

(async()=>{
  for(const id of ['pitch','yaw','roll','applyangle','resetangle'])assert.notEqual(elements[id].disabled,true,'local-file rotation controls must remain usable');
  elements.character.value='mario';elements.character.onchange();elements.action.value='victory3_source';elements.action.onchange();
  elements.costume.value='2';elements.costume.onchange();elements.scrub.value='67';elements.scrub.oninput();
  elements.downloadsize.value='2048';elements.downloadsize.onchange();elements.loop.checked=true;
  elements.pitch.value='20';elements.pitch.oninput();elements.yaw.value='45';elements.roll.value='10';elements.applyangle.onclick();
  const handoff=new URL(context.location.href);assert.equal(handoff.origin,'http://127.0.0.1:8765');assert.equal(handoff.pathname,'/player.html');
  const saved=new URLSearchParams(handoff.hash.slice(1));
  for(const [key,value] of Object.entries({character:'mario',action:'victory3_source',costume:'2',frame:'67',playing:'false',repeat:'true',size:'2048',pitch:'20',yaw:'45',roll:'10',cycle:'full'}))assert.equal(saved.get(key),value);
  elements.resetangle.onclick();assert.equal(elements.yaw.value,'0');assert.match(elements.frame.src,/costume_02\/victory3_source\/frame_0067.png$/);
  // The served page restores the file player's exact selection before rendering.
  const restoredElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
  let restoredRequest;
  let restoredPageShow;
  const restoredLocation={protocol:'http:',hash:handoff.hash,pathname:'/player.html',search:''};
  const replacedURLs=[];
  const restoredContext=vm.createContext({document:{getElementById:id=>restoredElements[id],createElement:()=>({})},URLSearchParams,
    location:restoredLocation,
    history:{replaceState:(state,title,url)=>{replacedURLs.push(url);restoredLocation.hash=''}},
    addEventListener:(name,callback)=>{if(name==='pageshow')restoredPageShow=callback},
    performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},fetch:url=>new Promise(resolve=>{restoredRequest={url,resolve}})});
  vm.runInContext(script,restoredContext);
  assert.deepEqual(replacedURLs,['/player.html']);assert.equal(restoredLocation.hash,'');
  restoredElements.yaw.value='123';restoredPageShow({persisted:false});
  assert.equal(restoredElements.yaw.value,'45','first handoff keeps its requested angle after form restoration');
  assert.equal(vm.runInContext('index',restoredContext),67);assert.equal(vm.runInContext('playing',restoredContext),false);
  assert.equal(restoredElements.costume.value,'2');assert.equal(restoredElements.downloadsize.value,'2048');
  assert.equal(restoredElements.sizewarning.hidden,false,'restored X-Large shows warning even while rendering');
  assert.equal(restoredElements.groundeffects.checked,true,'non-Tech handoffs must not disable default impact effects');
  assert.equal(restoredElements.loop.checked,true);
  assert.equal(new URL(restoredRequest.url,'http://localhost').searchParams.get('yaw'),'45');
  restoredRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:101},(_,i)=>`rotations/restored/frame_${String(i).padStart(4,'0')}.png`)})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(restoredElements.frame.src,'rotations/restored/frame_0067.png');assert.equal(restoredElements.still.hidden,false);
  // Reload the consumed handoff: no rotation request and every axis starts at 0.
  const reloadElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'90',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
  const reloadContext=vm.createContext({document:{getElementById:id=>reloadElements[id],createElement:()=>({})},location:restoredLocation,URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},fetch:()=>{throw Error('reload must use default prepared masters')}});
  vm.runInContext(script,reloadContext);
  for(const id of ['pitch','yaw','roll'])assert.equal(reloadElements[id].value,'0');
  assert.equal(vm.runInContext('hasAngle()',reloadContext),false);
  // A browser back/forward cache return resets the actual render and exports.
  restoredPageShow({persisted:true});
  assert.equal(vm.runInContext('hasAngle()',restoredContext),false);
  for(const id of ['pitch','yaw','roll'])assert.equal(restoredElements[id].value,'0');
  assert.match(restoredElements.frame.src,/costume_02\/victory3_source\/frame_0067.png$/);
  assert.equal(new URL(restoredElements.still.href,'http://localhost').searchParams.has('yaw'),false);
  const inspect=expression=>vm.runInContext(expression,servedContext);
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  function complete(request,label){const count=inspect('frameCount()');request.resolve({ok:true,json:async()=>({frames:Array.from({length:count},(_,i)=>`rotations/${label}/frame_${String(i).padStart(4,'0')}.png`)})})}
  servedElements.downloadsize.value='256';servedElements.downloadsize.onchange();
  servedElements.action.value='victory3_source';servedElements.action.onchange();
  servedElements.scrub.value='67';servedElements.scrub.oninput();
  servedElements.pitch.value='20';servedElements.pitch.oninput();servedElements.yaw.value='45';servedElements.roll.value='10';
  assert.equal(servedElements.pitchvalue.textContent,'20°');
  servedElements.applyangle.onclick();
  assert.equal(servedElements.frame.hidden,true);assert.equal(servedElements.downloadpanel.hidden,true);
  const first=requests.shift();assert.equal(new URL(first.url,'http://localhost').searchParams.get('yaw'),'45');
  complete(first,'first');await settle();
  assert.equal(inspect('index'),67);assert.equal(inspect('playing'),false);
  assert.equal(servedElements.saveimage.src,servedElements.still.href);
  assert.equal(servedElements.frame.src,'rotations/first/frame_0067.png');
  assert.equal(servedElements.frame.hidden,false);assert.equal(servedElements.downloadpanel.hidden,false);
  for(const id of ['gif','animationzip','allzip','still','framezip']){
    const url=new URL(servedElements[id].href,'http://localhost');assert.equal(url.searchParams.get('pitch'),'20');assert.equal(url.searchParams.get('roll'),'10');
    assert.match(servedElements[id].download,/-view-x20-y45-z10-256px\.(gif|png|zip)$/);
  }
  servedElements.downloadsize.value='1024';servedElements.downloadsize.onchange();
  assert.equal(inspect('index'),67);assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('size'),'1024');
  // A superseded request cannot replace a later selection or undo Reset.
  servedElements.yaw.value='90';servedElements.applyangle.onclick();const stale=requests.shift();
  servedElements.resetangle.onclick();complete(stale,'stale');await settle();
  assert.equal(inspect('hasAngle()'),false);assert.match(servedElements.frame.src,/mario\/costume_00\/victory3_source\/frame_0067.png$/);
  assert.equal(servedElements.pitch.value,'0');assert.equal(servedElements.pitchvalue.textContent,'0°');
  servedElements.character.value='luigi';servedElements.character.onchange();servedElements.action.value='results-clap_source';servedElements.action.onchange();
  servedElements.yaw.value='90';servedElements.applyangle.onclick();complete(requests.shift(),'full');await settle();
  servedElements.minimumcycle.checked=true;servedElements.minimumcycle.onchange();
  let minimum=requests.shift();assert.equal(new URL(minimum.url,'http://localhost').searchParams.get('cycle'),'minimum');complete(minimum,'minimum');await settle();
  assert.equal(inspect('frameCount()'),20);assert.match(servedElements.frame.src,/rotations\/minimum/);
  servedElements.synccycle.checked=true;servedElements.synccycle.onchange();
  complete(requests.shift(),'sync');await settle();assert.equal(inspect('frameCount()'),42);
  servedElements.scrub.value='41';servedElements.scrub.oninput();assert.match(servedElements.frame.src,/rotations\/sync\/frame_0041.png$/);
  assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('cycle'),'sync');
  servedElements.costume.value='1';servedElements.costume.onchange();
  const failed=requests.shift();assert.equal(new URL(failed.url,'http://localhost').searchParams.get('costume'),'1');failed.resolve({ok:false,status:503});await settle();
  assert.equal(servedElements.downloadpanel.hidden,true);assert.match(servedElements.rotationstatus.textContent,/busy/);
  servedElements.resetangle.onclick();assert.equal(servedElements.downloadpanel.hidden,false);
  // Attack filtering, default-angle lazy preparation, exact frame exports,
  // and a stale attack response after switching back to a prepared type.
  servedElements.character.value='mario';servedElements.character.onchange();
  servedElements.costume.value='2';servedElements.costume.onchange();
  servedElements.animationtype.value='taunt';servedElements.animationtype.onchange();
  assert.equal(servedElements.action.options.length,1);assert.equal(servedElements.actionlabel.hidden,true);
  servedElements.animationtype.value='attack';servedElements.animationtype.onchange();
  assert.equal(servedElements.costume.value,'2');assert.equal(servedElements.actionlabel.hidden,false);
  assert(servedElements.action.options.length>30);
  assert(servedElements.action.options.every(o=>o.value.startsWith('attack-')));
  assert.equal(servedElements.clapmodes.hidden,true);
  assert.equal(servedElements.downloadpanel.hidden,true);
  let attackRequest=requests.shift();assert.equal(new URL(attackRequest.url,'http://localhost').searchParams.get('yaw'),'0');
  complete(attackRequest,'attack');await settle();
  assert.match(servedElements.frame.src,/rotations\/attack\/frame_0000.png$/);
  assert.equal(new URL(servedElements.saveimage.src,'http://localhost').searchParams.get('kind'),'gif');
  assert.equal(new URL(servedElements.saveimage.src,'http://localhost').searchParams.get('view'),'1');
  assert.equal(new URL(servedElements.saveimage.src,'http://localhost').searchParams.has('frame'),false,'animation ticks do not reload right-click GIF');
  assert.equal(servedElements.allzip.hidden,true);
  servedElements.scrub.value='3';servedElements.scrub.oninput();
  assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('frame'),'3');
  assert.equal(new URL(servedElements.framezip.href,'http://localhost').searchParams.get('scope'),'colors');
  servedElements.costume.value='3';servedElements.costume.onchange();
  const abandoned=requests.shift();
  servedElements.animationtype.value='clapping';servedElements.animationtype.onchange();
  abandoned.resolve({ok:true,json:async()=>({frames:[]})});await settle();
  assert.equal(inspect('rotationBusy'),false);assert.equal(inspect('rotationFailed'),false);
  assert.equal(servedElements.animationtype.value,'clapping');assert.equal(servedElements.actionlabel.hidden,true);
  assert.match(servedElements.frame.src,/mario\/costume_03\/results-clap_source/);
  assert.equal(servedElements.allzip.hidden,false);
  elements.animationtype.value='attack';elements.animationtype.onchange();
  const attackHandoff=new URLSearchParams(new URL(context.location.href).hash.slice(1));
  assert.match(attackHandoff.get('action'),/^attack-/);assert.equal(attackHandoff.get('costume'),'2');
  assert.equal(attackHandoff.get('yaw'),'0');
  for(const c of data("characters.filter(c=>!['master-hand','crazy-hand','male-wireframe','female-wireframe','giga-bowser','sandbag'].includes(c.slug))")){
    const techs=data('clips').filter(clip=>clip.character===c.slug&&clip.animation_type==='tech');
    assert.equal(techs.length,c.costumes.length*7,'seven tech/ground choices per actual costume');
    assert.equal(new Set(techs.map(clip=>clip.action_key)).size,7);
  }
  assert.equal(data('clips.filter(c=>c.animation_type===\'tech\').length'),886);
  assert.equal(servedElements.techcontrols.hidden,true);
  servedElements.animationtype.value='tech';servedElements.animationtype.onchange();
  assert.equal(servedElements.action.options.length,7);assert.equal(servedElements.techcontrols.hidden,false);
  assert.equal(servedElements.groundeffects.disabled,false);
  let techRequest=requests.shift();assert.equal(new URL(techRequest.url,'http://localhost').searchParams.get('effects'),'on');
  complete(techRequest,'tech-on');await settle();
  assert.equal(servedElements.allzip.hidden,true);
  assert.equal(new URL(servedElements.saveimage.src,'http://localhost').searchParams.get('effects'),'on');
  assert.match(servedElements.gif.download,/-ground-effects-/);
  servedElements.scrub.value='3';servedElements.scrub.oninput();
  servedElements.groundeffects.checked=false;servedElements.groundeffects.onchange();
  let off=requests.shift();assert.equal(new URL(off.url,'http://localhost').searchParams.get('effects'),'off');
  complete(off,'tech-off');await settle();
  assert.equal(inspect('index'),3);assert.equal(inspect('playing'),false);
  assert.equal(servedElements.saveimage.src,servedElements.still.href);
  for(const id of ['gif','animationzip','still','framezip']){
    assert.equal(new URL(servedElements[id].href,'http://localhost').searchParams.get('effects'),'off');
    assert(!servedElements[id].download.includes('ground-effects'));
  }
  servedElements.groundeffects.checked=true;servedElements.groundeffects.onchange();const obsoleteTech=requests.shift();
  servedElements.groundeffects.checked=false;servedElements.groundeffects.onchange();complete(requests.shift(),'new-off');await settle();
  complete(obsoleteTech,'old-on');await settle();assert.match(servedElements.frame.src,/new-off/);
  servedElements.action.value='tech-184_source';servedElements.action.onchange();
  assert.equal(servedElements.groundeffects.disabled,true);assert.match(servedElements.techhint.textContent,/no ground-impact/);
  complete(requests.shift(),'lying');await settle();
  assert.equal(new URL(servedElements.gif.href,'http://localhost').searchParams.get('effects'),'off');
  elements.animationtype.value='tech';elements.animationtype.onchange();
  elements.groundeffects.checked=false;elements.groundeffects.onchange();
  const techHandoff=new URLSearchParams(new URL(context.location.href).hash.slice(1));
  assert.match(techHandoff.get('action'),/^tech-/);assert.equal(techHandoff.get('effects'),'off');
  const techRestoredElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
  let techRestoreRequest,techPageShow;
  const techRestoredContext=vm.createContext({document:{getElementById:id=>techRestoredElements[id],createElement:()=>({})},
    location:{protocol:'http:',hash:'#character=mario&action=tech-199_source&effects=off&costume=2&frame=3&playing=false'},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},
    addEventListener:(name,callback)=>{if(name==='pageshow')techPageShow=callback},
    fetch:url=>new Promise(resolve=>{techRestoreRequest={url,resolve}})});
  vm.runInContext(script,techRestoredContext);
  assert.equal(techRestoredElements.animationtype.value,'tech');assert.equal(techRestoredElements.groundeffects.checked,false);
  assert.equal(new URL(techRestoreRequest.url,'http://localhost').searchParams.get('effects'),'off');
  techRestoredElements.groundeffects.checked=true;techPageShow({persisted:false});
  assert.equal(techRestoredElements.groundeffects.checked,false,'late form restoration cannot disagree with the actual rendered effect state');
  techRestoreRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',techRestoredContext)},(_,i)=>`tech-restored/frame_${String(i).padStart(4,'0')}.png`)})});
  await settle();assert.equal(vm.runInContext('index',techRestoredContext),3);
  assert.equal(new URL(techRestoredElements.still.href,'http://localhost').searchParams.get('effects'),'off');
  console.log('All-character/costume Tech choices, impact toggle, paused frame, export URLs and stale effects: PASS');
  // Kirby power is appearance state, independent of action, color and camera.
  servedElements.resetangle.onclick();
  servedElements.animationtype.value='clapping';servedElements.animationtype.onchange();
  servedElements.character.value='kirby';servedElements.character.onchange();
  assert.equal(servedElements.powerlabel.hidden,false);
  servedElements.scrub.value='4';servedElements.scrub.oninput();
  servedElements.kirbypower.value='mario';servedElements.kirbypower.onchange();
  const hatRequest=requests.at(-1);
  assert.equal(new URL(hatRequest.url,'http://localhost').searchParams.get('power'),'mario');
  assert.equal(servedElements.downloadpanel.hidden,true);
  hatRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',servedContext)},(_,i)=>`powers/mario/frame_${i}.png`)})});
  await settle();
  assert.equal(vm.runInContext('index',servedContext),4);
  assert.equal(vm.runInContext('playing',servedContext),false);
  assert.equal(servedElements.frame.src,'powers/mario/frame_4.png');
  assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('power'),'mario');
  assert.equal(new URL(servedElements.framezip.href,'http://localhost').searchParams.get('power'),'mario');
  assert.match(servedElements.gif.download,/-power-mario/);
  assert.equal(servedElements.allzip.hidden,true);
  servedElements.kirbypower.value='luigi';servedElements.kirbypower.onchange();const staleHat=requests.at(-1);
  servedElements.kirbypower.value='none';servedElements.kirbypower.onchange();
  const noneFrame=servedElements.frame.src;
  staleHat.resolve({ok:true,json:async()=>({frames:['stale-hat.png']})});await settle();
  assert.equal(servedElements.frame.src,noneFrame,'None selection rejects a late hat render');
  assert.equal(vm.runInContext('powerSetting()',servedContext),'none');
  servedElements.kirbypower.value='falco';servedElements.kirbypower.onchange();
  servedElements.synccycle.checked=true;servedElements.synccycle.onchange();
  const syncHat=requests.at(-1);
  assert.equal(new URL(syncHat.url,'http://localhost').searchParams.get('cycle'),'sync');
  assert.equal(new URL(syncHat.url,'http://localhost').searchParams.get('power'),'falco');
  syncHat.resolve({ok:true,json:async()=>({frames:Array.from({length:42},(_,i)=>`powers/falco/sync-${i}.png`)})});await settle();
  assert.equal(vm.runInContext('frameCount()',servedContext),42);
  servedElements.character.value='fox';servedElements.character.onchange();
  assert.equal(servedElements.powerlabel.hidden,true);
  assert.equal(vm.runInContext('powerSetting()',servedContext),'none');
  assert(!servedElements.gif.href.includes('power='));
  // Local-file handoff carries the hat and consumes it only on that visit.
  elements.resetangle.onclick();elements.character.value='kirby';elements.character.onchange();
  elements.animationtype.value='victory';elements.animationtype.onchange();
  elements.action.value='victory3_source';elements.action.onchange();
  elements.costume.value='3';elements.costume.onchange();elements.scrub.value='8';elements.scrub.oninput();
  elements.kirbypower.value='mewtwo';elements.kirbypower.onchange();
  const powerHandoff=new URL(context.location.href);
  assert.equal(new URLSearchParams(powerHandoff.hash.slice(1)).get('power'),'mewtwo');
  const powerElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
  let powerRequest;
  const powerContext=vm.createContext({document:{getElementById:id=>powerElements[id],createElement:()=>({})},URLSearchParams,
    location:{protocol:'http:',hash:powerHandoff.hash},performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},
    fetch:url=>new Promise(resolve=>powerRequest={url,resolve})});
  vm.runInContext(script,powerContext);
  assert.equal(powerElements.kirbypower.value,'mewtwo');
  assert.equal(powerElements.powerlabel.hidden,false);
  assert.equal(powerElements.costume.value,'3');assert.equal(vm.runInContext('index',powerContext),8);
  assert.equal(vm.runInContext('playing',powerContext),false);
  assert.equal(new URL(powerRequest.url,'http://localhost').searchParams.get('power'),'mewtwo');
  console.log('Kirby Power visibility, zero-angle preparation, paused-frame retention, sync, native exports, stale requests and file handoff: PASS');
  servedElements.character.value='mario';servedElements.character.onchange();
  servedElements.animationtype.value='movement';servedElements.animationtype.onchange();
  assert.equal(servedElements.movementhint.hidden,false);
  assert.equal(servedElements.clapmodes.hidden,true);assert.equal(servedElements.techcontrols.hidden,true);
  assert(servedElements.action.options.some(o=>o.value==='movement-fullhop_source'));
  assert(servedElements.action.options.some(o=>o.value==='movement-shorthop_source'));
  assert(servedElements.action.options.some(o=>o.value==='movement-2_source'));
  servedElements.action.value='movement-fullhop_source';servedElements.action.onchange();
  const movementRequest=requests.at(-1);
  assert.equal(new URL(movementRequest.url,'http://localhost').searchParams.get('action'),'movement-fullhop_source');
  movementRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',servedContext)},(_,i)=>`movement/full-${i}.png`)})});await settle();
  servedElements.scrub.value='4';servedElements.scrub.oninput();
  assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('action'),'movement-fullhop_source');
  assert.equal(new URL(servedElements.framezip.href,'http://localhost').searchParams.get('frame'),'4');
  for(const c of data("characters.filter(c=>!['master-hand','crazy-hand','male-wireframe','female-wireframe','giga-bowser','sandbag'].includes(c.slug))")){
    const list=data(`clips.filter(c=>c.character==='${c.slug}'&&c.action_key.startsWith('movement-'))`);
    assert(list.some(c=>c.action_key==='movement-fullhop_source'));
    assert(list.some(c=>c.action_key==='movement-shorthop_source'));
    for(const a of new Set(list.map(c=>c.action_key)))assert.equal(list.filter(c=>c.action_key===a).length,c.costumes.length);
  }
  assert.equal(servedElements.jumpcontrols.hidden,false);
  assert.equal(servedElements.centerjump.checked,false);
  servedElements.centerjump.checked=true;servedElements.centerjump.onchange();
  let centeredRequest=requests.at(-1);
  assert.equal(new URL(centeredRequest.url,'http://localhost').searchParams.get('center'),'on');
  centeredRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',servedContext)},(_,i)=>`movement/center-${i}.png`)})});await settle();
  assert.equal(inspect('index'),4);assert.equal(inspect('playing'),false);
  for(const id of ['gif','animationzip','still','framezip']){
    assert.equal(new URL(servedElements[id].href,'http://localhost').searchParams.get('center'),'on');
    assert.match(servedElements[id].download,/-centered/);
  }
  assert.equal(servedElements.saveimage.src,servedElements.still.href);
  servedElements.centerjump.checked=false;servedElements.centerjump.onchange();
  assert.equal(new URL(requests.at(-1).url,'http://localhost').searchParams.get('center'),'off');
  servedElements.action.value='movement-2_source';servedElements.action.onchange();
  assert.equal(servedElements.jumpcontrols.hidden,true);
  assert(!new URL(requests.at(-1).url,'http://localhost').searchParams.has('center'));
  elements.character.value='mario';elements.character.onchange();
  elements.animationtype.value='movement';elements.animationtype.onchange();
  elements.action.value='movement-shorthop_source';elements.action.onchange();
  elements.scrub.value='4';elements.scrub.oninput();
  elements.centerjump.checked=true;elements.centerjump.onchange();
  const centerHandoff=new URL(context.location.href);
  assert.equal(new URLSearchParams(centerHandoff.hash.slice(1)).get('center'),'on');
  const centerElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
  let centerRequest,centerPageShow;
  const centerContext=vm.createContext({document:{getElementById:id=>centerElements[id],createElement:()=>({})},URLSearchParams,
    location:{protocol:'http:',hash:centerHandoff.hash},performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},
    addEventListener:(event,callback)=>{if(event==='pageshow')centerPageShow=callback},
    fetch:url=>new Promise(resolve=>centerRequest={url,resolve})});
  vm.runInContext(script,centerContext);
  assert.equal(centerElements.centerjump.checked,true);assert.equal(centerElements.jumpcontrols.hidden,false);
  assert.equal(vm.runInContext('index',centerContext),4);assert.equal(vm.runInContext('playing',centerContext),false);
  assert.equal(new URL(centerRequest.url,'http://localhost').searchParams.get('center'),'on');
  centerElements.centerjump.checked=false;centerPageShow({persisted:false});
  assert.equal(centerElements.centerjump.checked,true,'restored browser form must match the requested render setting');
  console.log('Centered hop visibility, toggle, paused frame and all download controls: PASS');
  console.log('Movement dropdown, all-character/costume coverage, lazy jump preview and exact-frame export controls: PASS');
  servedElements.animationtype.options=['victory','taunt','clapping','attack','tech','movement','hit','other'].map(value=>({value}));
  for(const slug of ['master-hand','crazy-hand','male-wireframe','female-wireframe','giga-bowser','sandbag']){
    servedElements.animationtype.value='clapping';servedElements.character.value=slug;servedElements.character.onchange();
    assert.equal(servedElements.animationtype.value,'movement');
    assert.equal(servedElements.costume.options.length,1);
    assert.equal(servedElements.powerlabel.hidden,true);
    assert(servedElements.action.options.length>0);
    assert(servedElements.animationtype.options.find(o=>o.value==='clapping').hidden);
    assert(servedElements.animationtype.options.find(o=>o.value==='victory').hidden);
    const extraType=slug==='sandbag'?'hit':'other';
    assert.equal(servedElements.animationtype.options.find(o=>o.value===extraType).hidden,false);
    servedElements.animationtype.value=extraType;servedElements.animationtype.onchange();
    assert(servedElements.action.options.length>0);
    const extraRequest=requests.at(-1);
    assert.equal(new URL(extraRequest.url,'http://localhost').searchParams.get('character'),slug);
    extraRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',servedContext)},(_,i)=>`extras/${slug}-${i}.png`)})});await settle();
    servedElements.scrub.value='1';servedElements.scrub.oninput();
    assert.equal(new URL(servedElements.framezip.href,'http://localhost').searchParams.get('character'),slug);
    assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('frame'),'1');
  }
  console.log('Six non-playable fighters, one-costume menus, valid type fallback, Other motions and exact-frame links: PASS');
  console.log('Animation Type filtering, hidden single-choice menus, attack loading/stills/colors and stale selection protection: PASS');
  console.log('Rotation Apply/Reset, pending/error states, stale responses, exact paused frames, mode/costume retention and sized downloads: PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
