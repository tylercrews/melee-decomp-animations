// Test the generated player's control/timer logic without a browser connector.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = path.resolve('build/melee_anim/preview/player.html');
const html = fs.readFileSync(page, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = Object.fromEntries(['animationtype','actionlabel','pitch','yaw','roll','pitchvalue','yawvalue','rollvalue','rotationstatus','applyangle','resetangle','downloadpanel','fullcycle','synccycle','clapmodes','dirtycycle','minimumcycle','cyclehint','downloadsize', 'servicehint', 'character', 'still', 'framezip', 'action', 'costume', 'frame', 'play', 'restart', 'loop', 'scrub', 'time', 'gif', 'animationzip', 'allzip', 'open', 'meta']
  .map(id => [id, {value: '0', textContent: '', checked: false, options: [], append(option) {this.options.push(option);}}]));
const context = vm.createContext({document: {getElementById: id => elements[id], createElement: () => ({})},
  location: {protocol:'file:'}, URLSearchParams,
  performance: {now: () => 0}, Image: class {}, requestAnimationFrame: callback => {context.nextFrame = callback;}});
vm.runInContext(script, context);
const data = expression => vm.runInContext(expression, context);
assert.equal(elements.action.options.length, 1);
assert.equal(elements.actionlabel.hidden, true);
elements.animationtype.value="victory";elements.animationtype.onchange();
assert.equal(elements.action.options.length, 6);assert.equal(elements.actionlabel.hidden,false);
elements.animationtype.value="clapping";elements.animationtype.onchange();
assert.equal(elements.costume.options.length, 5);
assert(elements.character.options.length>=1);
assert.equal(elements.character.options.length, 26);
assert.match(elements.frame.src, /frame_0000.png$/);
elements.play.onclick();
assert.equal(data('playing'), false);
assert.equal(elements.play.textContent, 'Play');
elements.scrub.value = '3';
elements.scrub.oninput();
assert.equal(data('index'), 3);
assert.match(elements.frame.src, /frame_0003.png$/);
elements.restart.onclick();
assert.equal(data('index'), 0);
assert.equal(data('playing'), true);
context.nextFrame(40);
assert.equal(data('index'), 2);
elements.action.value = 'victory1_source';
elements.action.onchange();
assert.equal(elements.loop.checked, false);
const count = data('clips[current].frames.length');
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
for (const size of [128,512,1024]) {
  elements.downloadsize.value=String(size);elements.downloadsize.onchange();
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
  {value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
const requests=[];
const servedContext=vm.createContext({document:{getElementById:id=>servedElements[id],createElement:()=>({})}, location:{protocol:'http:'}, URLSearchParams,
    performance:context.performance, Image:context.Image, requestAnimationFrame:()=>{},
    fetch:url=>new Promise(resolve=>requests.push({url,resolve}))});
vm.runInContext(script,servedContext);
assert.equal(servedElements.servicehint.hidden,true);
servedElements.downloadsize.value='512';servedElements.downloadsize.onchange();
assert(servedElements.gif.href.startsWith('/export?'));
console.log('Playback, color/frame retention, sized GIF/PNG downloads, ZIP links, and file/HTTP origins: PASS');

(async()=>{
  for(const id of ['pitch','yaw','roll','applyangle','resetangle'])assert.notEqual(elements[id].disabled,true,'local-file rotation controls must remain usable');
  elements.character.value='mario';elements.character.onchange();elements.action.value='victory3_source';elements.action.onchange();
  elements.costume.value='2';elements.costume.onchange();elements.scrub.value='67';elements.scrub.oninput();
  elements.downloadsize.value='512';elements.downloadsize.onchange();elements.loop.checked=true;
  elements.pitch.value='20';elements.pitch.oninput();elements.yaw.value='45';elements.roll.value='10';elements.applyangle.onclick();
  const handoff=new URL(context.location.href);assert.equal(handoff.origin,'http://127.0.0.1:8765');assert.equal(handoff.pathname,'/player.html');
  const saved=new URLSearchParams(handoff.hash.slice(1));
  for(const [key,value] of Object.entries({character:'mario',action:'victory3_source',costume:'2',frame:'67',playing:'false',repeat:'true',size:'512',pitch:'20',yaw:'45',roll:'10',cycle:'full'}))assert.equal(saved.get(key),value);
  elements.resetangle.onclick();assert.equal(elements.yaw.value,'0');assert.match(elements.frame.src,/costume_02\/victory3_source\/frame_0067.png$/);
  // The served page restores the file player's exact selection before rendering.
  const restoredElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
  let restoredRequest;
  const restoredContext=vm.createContext({document:{getElementById:id=>restoredElements[id],createElement:()=>({})},location:{protocol:'http:',hash:handoff.hash},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},fetch:url=>new Promise(resolve=>{restoredRequest={url,resolve}})});
  vm.runInContext(script,restoredContext);
  assert.equal(vm.runInContext('index',restoredContext),67);assert.equal(vm.runInContext('playing',restoredContext),false);
  assert.equal(restoredElements.costume.value,'2');assert.equal(restoredElements.downloadsize.value,'512');
  assert.equal(restoredElements.loop.checked,true);
  assert.equal(new URL(restoredRequest.url,'http://localhost').searchParams.get('yaw'),'45');
  restoredRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:101},(_,i)=>`rotations/restored/frame_${String(i).padStart(4,'0')}.png`)})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(restoredElements.frame.src,'rotations/restored/frame_0067.png');assert.equal(restoredElements.still.hidden,false);
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
  console.log('Animation Type filtering, hidden single-choice menus, attack loading/stills/colors and stale selection protection: PASS');
  console.log('Rotation Apply/Reset, pending/error states, stale responses, exact paused frames, mode/costume retention and sized downloads: PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
