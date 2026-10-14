// Test the generated player's control/timer logic without a browser connector.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = path.resolve('build/melee_anim/preview/player.html');
const html = fs.readFileSync(page, 'utf8');
for(const [row,ids] of [['charactercontrols',['character','kirbypower','costume']],['animationcontrols',['animationtype','action','hidepartials']],['playbackcontrols',['play','restart','loop']]]){
  const markup=html.match(new RegExp(`<div class="controls" id="${row}">([\\s\\S]*?)<\\/div>`))[1];
  const positions=ids.map(id=>markup.indexOf(`id="${id}"`));
  assert(positions.every(p=>p>=0));assert.deepEqual(positions,[...positions].sort((a,b)=>a-b));
}
assert.match(html,/<input id="hidepartials" type="checkbox" checked autocomplete="off"> Hide partial animations/);
assert.match(html,/<option value="tech">Knockdown<\/option>/);
assert.match(html,/<option value="movement">Movement<\/option>/);
assert.match(html,/\.stage\{background:transparent;/);
assert(!html.includes('repeating-conic-gradient'),'preview must have no checkerboard');
assert.match(html,/<option value="2048">⚠ X-Large \(2048 × 2048\)<\/option>/);
assert.match(html,/#sizewarning\{color:#b59a19\}/);
assert.match(html,/<small id="sizewarning"[^>]* hidden>Extremely large GIF files<\/small>/);
assert.match(html,/<a class="download hd" id="hdstill" hidden download>Rerender Selected Frame In HD<\/a>/);
assert.match(html,/<a class="download hd-colors" id="hdcolors" hidden download>Rerender Selected Frame In HD In All Colors<\/a>/);
assert.match(html,/<input id="cropborder" type="checkbox" checked autocomplete="off"> Crop Transparent Border/);
assert(html.indexOf('id="hdcolors"')<html.indexOf('id="hdcroplabel"'));
assert(html.indexOf('id="framezip"')<html.indexOf('id="hdstill"')&&html.indexOf('id="hdstill"')<html.indexOf('id="hdcolors"'));
assert.match(html,/\.download\.hd\{background:#7540b0/);assert.match(html,/\.download\.hd-colors\{background:#45206c/);
for(const id of ['pitch','yaw','roll']){
  assert.match(html,new RegExp(`<input id="${id}"[^>]*step="1"[^>]*list="anglestops"`));
  assert.match(html,new RegExp(`<input id="${id}value" type="number"[^>]*min="-180" max="180" step="1"`));
}
const stops=html.match(/<datalist id="anglestops">([\s\S]*?)<\/datalist>/)[1];
assert.deepEqual([...stops.matchAll(/value="(-?\d+)"/g)].map(match=>Number(match[1])),[-180,-135,-90,-45,0,45,90,135,180]);
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = Object.fromEntries(['hdcroplabel','cropborder','hdstill','hdcolors','hdsize','hdcontrols','downloadprogress','downloadbar','downloadcount','electriccontrols','judgeelectric','kirbymode','upsizenotice','downloadstatus','hidepartials','effecthint','sequencehint','itemhint','centerjump','jumpcontrols','movementhint','kirbypower','powerlabel','groundeffects','techcontrols','techhint','sizewarning','saveimage','animationtype','actionlabel','pitch','yaw','roll','pitchvalue','yawvalue','rollvalue','rotationstatus','applyangle','resetangle','downloadpanel','fullcycle','synccycle','clapmodes','dirtycycle','minimumcycle','cyclehint','downloadsize', 'servicehint', 'character', 'still', 'framezip', 'action', 'costume', 'frame', 'play', 'restart', 'loop', 'scrub', 'time', 'gif', 'animationzip', 'allzip', 'open', 'meta']
  .map(id => [id, {value: '0', textContent: '', checked: false, options: id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[], append(option) {this.options.push(option);}}]));
const context = vm.createContext({document: {getElementById: id => elements[id], createElement: () => ({})},
  location: {protocol:'file:'}, URLSearchParams,
  performance: {now: () => 0}, Image: class {}, requestAnimationFrame: callback => {context.nextFrame = callback;}});
vm.runInContext(script, context);
const data = expression => vm.runInContext(expression, context);
for(const [slug,id,label] of [['fox',2,'Lavender'],['captain-falcon',1,'Gray'],['samus',4,'Lavender'],['ganondorf',4,'Lavender']]){
  const costume=data('characters').find(c=>c.slug===slug).costumes.find(c=>c.id===id);
  assert.equal(costume.label,label);
  assert(data('clips').filter(c=>c.character===slug&&c.costume_id===id).every(c=>c.costume_label===label));
}
assert(data('characters').every(c=>c.costumes.every(costume=>!costume.label.startsWith('Costume '))));

assert.equal(elements.hidepartials.checked,true,'partial clips are hidden on fresh loads');
assert.equal(elements.downloadsize.value,'1024');
assert(data('clips.filter(c=>!c.lazy)').every(c=>c.master_size===1024),'prebuilt results must be native1024');
assert.equal(elements.upsizenotice.hidden,true);
assert(elements.downloadsize.options.find(o=>o.value==='1024').textContent.startsWith('\u2605'));
assert(!elements.downloadsize.options.find(o=>o.value==='512').textContent.startsWith('\u2605'));

assert.match(html,/<option value="1024" selected>\u2605 Large \(1024 \u00d7 1024, native render\)<\/option>/);
elements.hidepartials.checked=false;elements.hidepartials.onchange();
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
  assert.equal(elements.gif.download, clip.download_name.replace('.gif','-1024px.gif'));
  assert.match(elements.gif.download, /\.gif$/);
  elements.scrub.value='3';elements.scrub.oninput();
  assert.equal(elements.still.href,clip.frames[3]);assert.equal(elements.still.hidden,false);
  assert.equal(elements.framezip.hidden,false);
  assert.match(elements.still.download,/frame-0004-1024px.png$/);
  assert(fs.existsSync(path.join(path.dirname(page),elements.framezip.href)));
  const a = data('animations.find(a => a.key === action.value && a.character === character.value)');
  assert.equal(elements.animationzip.href, a.zip);
  assert.equal(elements.animationzip.download, a.download_name.replace('.zip','-1024px.zip'));
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
assert.match(elements.still.download,/frame-0068-1024px.png$/);
assert.match(elements.framezip.href,/frame-0068.zip$/);
for (const size of [128,256,512,2048]) {
  elements.downloadsize.value=String(size);elements.downloadsize.onchange();
  assert.equal(elements.sizewarning.hidden,size!==2048,'warning appears only for X-Large');
  assert.equal(elements.upsizenotice.hidden,size<=1024,'upsizing notice only above native resolution');
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
elements.downloadsize.value='1024';elements.downloadsize.onchange();
assert.equal(elements.sizewarning.hidden,true,'switching away from X-Large hides the warning');
assert.match(elements.still.href,/frame_0067.png$/);
assert.match(html,/id="allzip" download>Download matching animations for all characters/);
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
  assert.match(elements.gif.download,/-minimum-cycle-1024px.gif$/);
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
assert(dirtyCharacters.length>0,'dirty loop choices must remain available after source texture changes');
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
  assert.match(elements.gif.download,/-dirty-loop-1024px.gif$/);
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
  assert.match(elements.gif.download,/-clapping-sync-1024px.gif$/);
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
  {value:'90',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
const requests=[];
let servedPageShow;
const servedContext=vm.createContext({document:{getElementById:id=>servedElements[id],createElement:()=>({})}, location:{protocol:'http:'}, URLSearchParams,
    addEventListener:(name,callback)=>{if(name==='pageshow')servedPageShow=callback},
    performance:context.performance, Image:context.Image, requestAnimationFrame:()=>{},
    fetch:url=>new Promise(resolve=>requests.push({url,resolve}))});
vm.runInContext(script,servedContext);
assert.equal(servedElements.hidepartials.checked,true);
servedElements.hidepartials.checked=false;servedElements.hidepartials.onchange();
// Fresh loads override stale restored form values, even if restoration is late.
for(const id of ['pitch','yaw','roll'])assert.equal(servedElements[id].value,'0');
for(const id of ['pitch','yaw','roll'])servedElements[id].value='75';
servedPageShow({persisted:false});
for(const id of ['pitch','yaw','roll']){
  assert.equal(servedElements[id].value,'0');assert.equal(servedElements[id+'value'].value,'0');
}
for(const id of ['pitch','yaw','roll']){
  const slider=servedElements[id],exact=servedElements[id+'value'];
  slider.onpointerdown();
  for(const stop of [-180,-135,-90,-45,0,45,90,135,180]){
    const nearby=stop===180?177:stop+3;
    slider.value=String(nearby);slider.oninput();
    assert.equal(slider.value,String(stop),'dragging lands on every 45-degree stop');
    assert.equal(exact.value,String(stop));
  }
  slider.value='41';slider.oninput();assert.equal(slider.value,'41','outside the snap zone remains arbitrary');
  slider.onpointerup();slider.value='43';slider.oninput();assert.equal(slider.value,'43','non-pointer input stays exact');
  slider.onpointerdown();slider.onkeydown();slider.value='44';slider.oninput();assert.equal(slider.value,'44','keyboard adjustments bypass snapping');
  slider.onpointerdown();slider.onpointercancel();slider.value='-43';slider.oninput();assert.equal(slider.value,'-43');
  exact.value='43';exact.oninput();assert.equal(slider.value,'43','typed degrees bypass snapping');
  exact.value='-179';exact.oninput();assert.equal(slider.value,'-179');
  for(const invalid of ['', '181', '-181', '1.5']){exact.value=invalid;exact.oninput();assert.equal(slider.value,'-179','invalid entry cannot change the angle');}
}
servedPageShow({persisted:false});
let reportedInvalid=false;
servedElements.yawvalue.checkValidity=()=>false;
servedElements.yawvalue.reportValidity=()=>{reportedInvalid=true};
const beforeInvalidApply=requests.length;
servedElements.applyangle.onclick();
assert(reportedInvalid);assert.equal(requests.length,beforeInvalidApply,'invalid exact degrees cannot start a render');
delete servedElements.yawvalue.checkValidity;delete servedElements.yawvalue.reportValidity;
assert.equal(servedElements.servicehint.hidden,true);
servedElements.downloadsize.value='256';servedElements.downloadsize.onchange();
assert(servedElements.gif.href.startsWith('/export?'));
console.log('Playback, color/frame retention, sized GIF/PNG downloads, ZIP links, and file/HTTP origins: PASS');

(async()=>{
  {
  const hdElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  hdElements.hdstill.className='download hd';hdElements.hdcolors.className='download hd-colors';
  const pending=[],saved=[];
  const hdContext=vm.createContext({document:{getElementById:id=>hdElements[id],body:{append(){}},createElement:()=>({click(){saved.push({href:this.href,name:this.download})},remove(){}})},location:{protocol:'http:',hash:''},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame(){},fetch:url=>new Promise(resolve=>pending.push({url,resolve}))});
  vm.runInContext(script,hdContext);
  assert.equal(hdElements.hdsize.value,'4096','HD starts at native 4096, independently of ordinary export size');
  assert.equal(hdElements.cropborder.checked,true);assert.equal(hdElements.hdcroplabel.hidden,true);
  assert.equal(hdElements.hdstill.hidden,true);assert.equal(hdElements.hdcontrols.hidden,true);
  hdElements.scrub.value='5';hdElements.scrub.oninput();
  assert.equal(hdElements.hdstill.hidden,false);assert.equal(hdElements.hdcolors.hidden,false);assert.equal(hdElements.hdcontrols.hidden,false);
  assert.equal(hdElements.hdcroplabel.hidden,false);
  hdElements.yawvalue.value='43';hdElements.yawvalue.oninput();hdElements.applyangle.onclick();
  assert.equal(hdElements.downloadpanel.hidden,true);assert.equal(hdElements.hdcontrols.hidden,true);
  pending.shift().resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',hdContext)},(_,i)=>`rotations/hd/frame_${i}.png`)})});
  await new Promise(resolve=>setImmediate(resolve));
  hdElements.hdsize.value='4096';hdElements.hdsize.onchange();
  const query=new URL(hdElements.hdstill.href,'http://localhost').searchParams;
  for(const [key,value] of Object.entries({render:'hd',crop:'on',kind:'png',scope:'costume',size:'4096',frame:'5',yaw:'43'}))assert.equal(query.get(key),value);
  assert.equal(new URL(hdElements.still.href,'http://localhost').searchParams.has('crop'),false);
  assert.equal(new URL(hdElements.still.href,'http://localhost').searchParams.get('size'),'1024','HD size does not alter ordinary downloads');
  const originalName=hdElements.hdstill.download;
  const saving=hdElements.hdstill.onclick({preventDefault(){}});
  assert.match(hdElements.hdstill.className,/hd busy/);assert.equal(hdElements.hdstill.ariaBusy,'true');
  for(const id of ['gif','still','animationzip','framezip','allzip','hdstill','hdcolors'])assert.equal(hdElements[id].ariaDisabled,'true');
  await hdElements.hdcolors.onclick({preventDefault(){}});assert.equal(pending.length,1);
  assert.match(pending[0].url,/prepare-export.*render=hd.*progress=/);
  hdElements.hdsize.value='2048';hdElements.hdsize.onchange();hdElements.scrub.value='7';hdElements.scrub.oninput();
  hdElements.cropborder.checked=false;hdElements.cropborder.onchange();
  assert.equal(new URL(hdElements.hdcolors.href,'http://localhost').searchParams.get('crop'),'off');
  pending.shift().resolve({ok:true,json:async()=>({url:'/hd-export/selected.png',progress:{percent:100,total:1,completed:1,files_completed:1,phase:'HD frame ready'}})});
  await saving;
  assert.equal(saved[0].name,originalName);assert.match(saved[0].name,/-frame-0006-view-x0-y43-z0-cropped-hd-4096px\.png$/);
  assert.equal(hdElements.hdstill.className,'download hd');assert.equal(hdElements.downloadbar.value,100);
  assert.equal(new URL(hdElements.hdcolors.href,'http://localhost').searchParams.get('scope'),'colors');
  const failed=hdElements.hdcolors.onclick({preventDefault(){}});
  pending.shift().resolve({ok:false,status:500});await failed;
  assert.equal(hdElements.hdcolors.className,'download hd-colors');assert.equal(hdElements.hdcolors.ariaDisabled,'false');
  assert.match(hdElements.downloadstatus.textContent,/500/);
  const fileElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  const fileContext=vm.createContext({document:{getElementById:id=>fileElements[id],createElement:()=>({})},location:{protocol:'file:',hash:''},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame(){}});
  vm.runInContext(script,fileContext);
  fileElements.scrub.value='7';fileElements.scrub.oninput();fileElements.yawvalue.value='43';fileElements.yawvalue.oninput();fileElements.applyangle.onclick();
  fileElements.cropborder.checked=false;fileElements.cropborder.onchange();
  fileElements.hdsize.value='4096';fileElements.hdsize.onchange();await fileElements.hdstill.onclick({preventDefault(){}});
  const handoff=new URL(fileContext.location.href),state=new URLSearchParams(handoff.hash.slice(1));
  assert.equal(state.get('batch'),'hd-single');assert.equal(state.get('hdsize'),'4096');assert.equal(state.get('frame'),'7');assert.equal(state.get('yaw'),'43');assert.equal(state.get('crop'),'off');
  await fileElements.hdcolors.onclick({preventDefault(){}});assert.equal(new URLSearchParams(new URL(fileContext.location.href).hash.slice(1)).get('batch'),'hd-colors');
  const restoreElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  let restoring;
  const restoreContext=vm.createContext({document:{getElementById:id=>restoreElements[id],createElement:()=>({click(){},remove(){}}),body:{append(){}}},location:{protocol:'http:',hash:new URL(fileContext.location.href).hash},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame(){},fetch:url=>new Promise(resolve=>{restoring={url,resolve}})});
  vm.runInContext(script,restoreContext);assert.equal(restoreElements.cropborder.checked,false);
  assert.equal(new URL(restoring.url,'http://localhost').searchParams.has('crop'),false,'crop is not a preview/render option');
  restoreElements.cropborder.checked=true;vm.runInContext('syncAngleInputs()',restoreContext);assert.equal(restoreElements.cropborder.checked,false);
  restoring.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',restoreContext)},(_,i)=>`rotations/crop/frame_${i}.png`)})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(new URL(restoring.url,'http://localhost').searchParams.get('crop'),'off');
  restoring.resolve({ok:true,json:async()=>({url:'/hd-export/restored.zip'})});await new Promise(resolve=>setImmediate(resolve));
  console.log('Purple HD PNG buttons, independent 2048/4096 sizes, exact paused angle/frame, spinner, shared lock, snapshots, errors and file handoff: PASS');
  }
  {
  const savedDownloads=[];
  servedContext.document.body={append:()=>{}};
  servedContext.document.createElement=()=>({click(){savedDownloads.push({href:this.href,download:this.download})},remove(){}});
  const requestedHref=servedElements.animationzip.href,requestedName=servedElements.animationzip.download;
  const before=requests.length;
  const saving=servedElements.animationzip.onclick({preventDefault(){}});
  assert.equal(requests.length,before+1);
  assert.match(requests.at(-1).url,/\/prepare-export\?/);
  assert.equal(servedElements.animationzip.ariaBusy,'true');
  assert.match(servedElements.animationzip.className,/busy/);
  for(const id of ['animationzip','framezip','allzip'])assert.equal(servedElements[id].ariaDisabled,'true');
  await servedElements.framezip.onclick({preventDefault(){}});
  assert.equal(requests.length,before+1,'second batch is blocked during preparation');
  servedElements.costume.value='2';servedElements.costume.onchange();
  assert.equal(servedElements.animationzip.ariaBusy,'true','selection updates do not remove busy state');
  requests.at(-1).resolve({ok:true,json:async()=>({url:'/downloads/ready.zip'})});
  await saving;
  assert.equal(savedDownloads[0].href,'/downloads/ready.zip');
  assert.equal(savedDownloads[0].download,requestedName,'download uses the click-time selection');
  assert.equal(servedElements.animationzip.ariaDisabled,'false');
  assert.equal(servedElements.animationzip.ariaBusy,'false');
  assert(!servedElements.animationzip.className.includes('busy'));
  const failed=servedElements.animationzip.onclick({preventDefault(){}});
  requests.at(-1).resolve({ok:false,status:503});await failed;
  assert.equal(servedElements.animationzip.ariaDisabled,'false');
  assert.match(servedElements.downloadstatus.textContent,/503/);
  assert.equal(savedDownloads.length,1,'failed preparations never start a download');
  servedElements.costume.value='0';servedElements.costume.onchange();
  requests.splice(before);
  console.log('Batch spinner, shared duplicate lock, selection snapshot, ready URL and error recovery: PASS');
  }
  {
  const progressElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  const pending=[],saved=[],timers=new Map();let timerId=0;
  const progressContext=vm.createContext({document:{getElementById:id=>progressElements[id],body:{append(){}},createElement:()=>({click(){saved.push({href:this.href,name:this.download})},remove(){}})},
    location:{protocol:'http:',hash:''},URLSearchParams,performance:context.performance,Image:context.Image,requestAnimationFrame(){},
    setTimeout(callback){timers.set(++timerId,callback);return timerId},clearTimeout(id){timers.delete(id)},
    fetch:url=>new Promise(resolve=>pending.push({url,resolve}))});
  vm.runInContext(script,progressContext);
  progressElements.downloadsize.value='512';progressElements.downloadsize.onchange();
  const originalName=progressElements.gif.download;
  const saving=progressElements.gif.onclick({preventDefault(){}});
  assert.equal(pending.length,1);assert.match(pending[0].url,/prepare-export.*progress=/);
  assert.equal(progressElements.downloadprogress.hidden,false);
  for(const id of ['gif','still','animationzip','framezip','allzip'])assert.equal(progressElements[id].ariaDisabled,'true');
  await progressElements.still.onclick({preventDefault(){}});assert.equal(pending.length,1);
  let tick=timers.entries().next().value;timers.delete(tick[0]);const polling=tick[1]();
  assert.match(pending[1].url,/export-progress\?id=/);
  pending[1].resolve({ok:true,json:async()=>({percent:23,total:5,completed:2,files_completed:0,phase:'Rendering frames',frames_done:40,frames_total:101,unit:'frames',label:'Mario / Blue'})});
  await polling;
  assert.equal(progressElements.downloadbar.value,23);assert.match(progressElements.downloadcount.textContent,/2\/5/);
  assert.match(progressElements.downloadstatus.textContent,/40\/101 frames/);
  tick=timers.entries().next().value;timers.delete(tick[0]);const latePoll=tick[1]();
  const stale=pending[2];
  pending[0].resolve({ok:true,json:async()=>({url:'/downloads/ready.gif',progress:{percent:100,total:5,completed:5,files_completed:5,phase:'Download ready'}})});
  await saving;
  assert.equal(progressElements.downloadbar.value,100);assert.match(progressElements.downloadcount.textContent,/5\/5/);
  assert.equal(saved[0].name,originalName);assert.equal(timers.size,0);
  const next=progressElements.gif.onclick({preventDefault(){}});
  assert.equal(progressElements.downloadbar.value,0);
  stale.resolve({ok:true,json:async()=>({percent:80,total:5,completed:4,files_completed:3,phase:'Old request'})});await latePoll;
  assert.equal(progressElements.downloadbar.value,0,'late polling cannot overwrite a new download');
  pending.at(-1).resolve({ok:false,status:500});await next;
  assert.equal(progressElements.gif.ariaDisabled,'false');assert.equal(timers.size,0);
  assert.match(progressElements.downloadstatus.textContent,/Preparation failed/);
  console.log('Single/batch download progress, frame counts, shared lock, completion, stale polls and error cleanup: PASS');
  }
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
  const restoredElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
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
  assert.equal(restoredElements.upsizenotice.hidden,false,'restored X-Large explains upscaling even while rendering');
  assert.equal(restoredElements.groundeffects.checked,true,'non-Tech handoffs must not disable default impact effects');
  assert.equal(restoredElements.loop.checked,true);
  assert.equal(new URL(restoredRequest.url,'http://localhost').searchParams.get('yaw'),'45');
  restoredRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:101},(_,i)=>`rotations/restored/frame_${String(i).padStart(4,'0')}.png`)})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(restoredElements.frame.src,'rotations/restored/frame_0067.png');assert.equal(restoredElements.still.hidden,false);
  // Reload the consumed handoff: no rotation request and every axis starts at 0.
  const reloadElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'90',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
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
  servedElements.pitch.value='20';servedElements.pitch.oninput();servedElements.yawvalue.value='43';servedElements.yawvalue.oninput();servedElements.roll.value='10';
  assert.equal(servedElements.pitchvalue.value,'20');
  servedElements.applyangle.onclick();
  assert.equal(servedElements.frame.hidden,true);assert.equal(servedElements.downloadpanel.hidden,true);
  const first=requests.shift();assert.equal(new URL(first.url,'http://localhost').searchParams.get('yaw'),'43');
  complete(first,'first');await settle();
  assert.equal(inspect('index'),67);assert.equal(inspect('playing'),false);
  assert.equal(servedElements.saveimage.src,servedElements.still.href);
  assert.equal(servedElements.frame.src,'rotations/first/frame_0067.png');
  assert.equal(servedElements.frame.hidden,false);assert.equal(servedElements.downloadpanel.hidden,false);
  for(const id of ['gif','animationzip','allzip','still','framezip']){
    const url=new URL(servedElements[id].href,'http://localhost');assert.equal(url.searchParams.get('pitch'),'20');assert.equal(url.searchParams.get('roll'),'10');
    assert.equal(url.searchParams.get('yaw'),'43');
    assert.match(servedElements[id].download,/-view-x20-y43-z10-256px\.(gif|png|zip)$/);
  }
  servedElements.downloadsize.value='1024';servedElements.downloadsize.onchange();
  assert.equal(inspect('index'),67);assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('size'),'1024');
  // A superseded request cannot replace a later selection or undo Reset.
  servedElements.yaw.value='90';servedElements.applyangle.onclick();const stale=requests.shift();
  servedElements.resetangle.onclick();complete(stale,'stale');await settle();
  assert.equal(inspect('hasAngle()'),false);assert.match(servedElements.frame.src,/mario\/costume_00\/victory3_source\/frame_0067.png$/);
  assert.equal(servedElements.pitch.value,'0');assert.equal(servedElements.pitchvalue.value,'0');
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
  assert.equal(servedElements.allzip.hidden,false);
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
    assert.equal(techs.length,c.costumes.length*9,'seven clips plus two missed-tech sequences per actual costume');
    assert.equal(new Set(techs.map(clip=>clip.action_key)).size,9);
  }
  assert.equal(data('clips.filter(c=>c.animation_type===\'tech\').length'),1134);
  assert.equal(servedElements.techcontrols.hidden,true);
  servedElements.animationtype.value='tech';servedElements.animationtype.onchange();
  assert.equal(servedElements.action.options.length,9);assert.equal(servedElements.techcontrols.hidden,false);
  assert.equal(servedElements.groundeffects.disabled,false);
  let techRequest=requests.shift();assert.equal(new URL(techRequest.url,'http://localhost').searchParams.get('effects'),'on');
  complete(techRequest,'tech-on');await settle();
  assert.equal(servedElements.allzip.hidden,false);
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
  const techRestoredElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
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
  assert.equal(servedElements.allzip.hidden,false);
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
  const powerElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
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
    for(const id of [41,42,43,206,207,208])assert(list.some(c=>c.action_key===`movement-${id}_source`));
    assert.equal(list.some(c=>c.action_key==='movement-37_source'),c.slug==='yoshi');
    assert(!list.some(c=>['movement-38_source','movement-39_source','movement-40_source'].includes(c.action_key)));
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
  const centerElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
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
  servedElements.character.value='mario';servedElements.character.onchange();
  servedElements.animationtype.value='attack';servedElements.animationtype.onchange();
  servedElements.action.value='attack-112_source';servedElements.action.onchange();
  assert.equal(servedElements.itemhint.hidden,false);
  assert.match(servedElements.itemhint.textContent,/Home-Run Bat/);
  assert(servedElements.action.options.some(o=>/Home-Run Bat/.test(o.textContent)));
  servedElements.action.value='attack-44_source';servedElements.action.onchange();
  assert.equal(servedElements.itemhint.hidden,true);
  for(const [slug,aid,label] of [['fox',296,'Blaster'],['falco',299,'Blaster'],['sheik',298,'Released needles'],['kirby',325,'Final Cutter blade']]){
    servedElements.character.value=slug;servedElements.character.onchange();
    servedElements.animationtype.value='attack';servedElements.animationtype.onchange();
    servedElements.action.value=`attack-${aid}_source`;servedElements.action.onchange();
    assert.equal(servedElements.itemhint.hidden,false);assert(servedElements.itemhint.textContent.includes(label));
    const propRequest=requests.at(-1);propRequest.resolve({ok:true,json:async()=>({frames:Array.from({length:vm.runInContext('frameCount()',servedContext)},(_,i)=>`props/${slug}-${i}.png`)})});await settle();
    assert.equal(new URL(servedElements.animationzip.href,'http://localhost').searchParams.get('action'),`attack-${aid}_source`);
  }
  assert.match(servedElements.itemhint.textContent,/Final Cutter/);
  console.log('Held-item labels and action-specific preview/export hint: PASS');
  for(const [slug,key,type] of [['fox','attack-295-combined_source','attack'],['kirby','attack-324-combined_source','attack'],['mario','tech-183-combined_source','tech']]){
    servedElements.character.value=slug;servedElements.character.onchange();
    servedElements.animationtype.value=type;servedElements.animationtype.onchange();
    servedElements.action.value=key;servedElements.action.onchange();
    assert.equal(servedElements.sequencehint.hidden,false);
    assert.match(servedElements.sequencehint.textContent,/Uncheck Hide partial animations/);
    assert.equal(vm.runInContext('clips[current].authored_loop',servedContext),false);
    complete(requests.at(-1),'combined-'+slug);await settle();
    servedElements.scrub.value='20';servedElements.scrub.oninput();
    for(const id of ['gif','animationzip','still','framezip']){
      assert.equal(new URL(servedElements[id].href,'http://localhost').searchParams.get('action'),key);
    }
    assert.equal(new URL(servedElements.still.href,'http://localhost').searchParams.get('frame'),'20');
  }
  servedElements.action.value='tech-184_source';servedElements.action.onchange();
  assert.equal(servedElements.sequencehint.hidden,true);
  console.log('Combined phase presets, hints, paused frame and selected/all-color export URLs: PASS');
  for(const [slug,key,label] of [['fox','attack-314_source','Reflector'],['falco','attack-317-combined_source','Reflector'],['ness','attack-318-combined_source','PSI Magnet'],['mario','attack-301_source','Tornado'],['luigi','attack-311_source','Luigi Cyclone']]){
    servedElements.character.value=slug;servedElements.character.onchange();
    servedElements.animationtype.value='attack';servedElements.animationtype.onchange();
    servedElements.action.value=key;servedElements.action.onchange();
    assert.equal(servedElements.effecthint.hidden,false);assert(servedElements.effecthint.textContent.includes(label));
    complete(requests.at(-1),'effect-'+slug);await settle();
    assert.equal(new URL(servedElements.gif.href,'http://localhost').searchParams.get('action'),key);
    assert.equal(new URL(servedElements.framezip.href,'http://localhost').searchParams.get('action'),key);
  }
  servedElements.action.value='attack-44_source';servedElements.action.onchange();
  assert.equal(servedElements.effecthint.hidden,true);
  console.log('Reflector/magnet/cyclone hints, combined phases and effect export URLs: PASS');
  for(const [slug,key,label] of [['mario','movement-41_source','Spot dodge'],['fox','movement-42_source','Roll forward'],['yoshi','movement-37_source','Yoshi egg'],['yoshi','movement-43_source','Roll backward']]){
    servedElements.character.value=slug;servedElements.character.onchange();
    servedElements.animationtype.value='movement';servedElements.animationtype.onchange();
    servedElements.action.value=key;servedElements.action.onchange();
    assert(servedElements.action.options.some(o=>o.value===key&&o.textContent===label));
    assert.equal(servedElements.jumpcontrols.hidden,true);assert.equal(servedElements.techcontrols.hidden,true);
    complete(requests.at(-1),'dodge-'+slug);await settle();
    servedElements.scrub.value='1';servedElements.scrub.oninput();
    for(const id of ['gif','animationzip','still','framezip'])assert.equal(new URL(servedElements[id].href,'http://localhost').searchParams.get('action'),key);
  }
  console.log('Roll/spot-dodge coverage, Yoshi-only egg, no shield entries and exact/color export URLs: PASS');
  // Fresh pages hide parts for every family; showing parts keeps each family
  // contiguous, including shared ground/air Kirby Cutter phase variants.
  const filteredElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  const filteredContext=vm.createContext({document:{getElementById:id=>filteredElements[id],createElement:()=>({})},location:{protocol:'file:'},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{}});
  vm.runInContext(script,filteredContext);
  const filtered=expression=>vm.runInContext(expression,filteredContext);
  assert.equal(filteredElements.hidepartials.checked,true);
  for(const c of filtered('characters')){
    filteredElements.character.value=c.slug;filteredElements.character.onchange();
    for(const type of ['attack','tech']){
      const owned=filtered('animations').filter(a=>a.character===c.slug&&a.type===type&&!a.unavailable);
      if(!owned.length)continue;
      filteredElements.animationtype.value=type;filteredElements.animationtype.onchange();
      const keys=filteredElements.action.options.map(o=>o.value);
      for(const a of owned)assert.equal(keys.includes(a.key),!a.partial,`${c.slug}/${a.key}`);
    }
  }
  filteredElements.character.value='fox';filteredElements.character.onchange();
  filteredElements.animationtype.value='attack';filteredElements.animationtype.onchange();
  assert(filteredElements.action.options.some(o=>o.value==='attack-315_source'),'reflection response is not a hidden combined phase');
  filteredElements.hidepartials.checked=false;filteredElements.hidepartials.onchange();
  let keys=filteredElements.action.options.map(o=>o.value),start=keys.indexOf('attack-295-combined_source');
  assert.deepEqual(keys.slice(start,start+4),['attack-295-combined_source','attack-295_source','attack-296_source','attack-297_source']);
  filteredElements.action.value='attack-296_source';filteredElements.action.onchange();
  filteredElements.costume.value='2';filteredElements.costume.onchange();
  filteredElements.scrub.value='5';filteredElements.scrub.oninput();
  assert.equal(new URLSearchParams(new URL(filteredContext.location.href).hash.slice(1)).get('partials'),'show');
  filteredElements.hidepartials.checked=true;filteredElements.hidepartials.onchange();
  assert.equal(filteredElements.action.value,'attack-295-combined_source');assert.equal(filteredElements.costume.value,'2');
  assert.equal(filtered('index'),0);
  filteredElements.scrub.value='9';filteredElements.scrub.oninput();
  filteredElements.hidepartials.checked=false;filteredElements.hidepartials.onchange();
  assert.equal(filteredElements.action.value,'attack-295-combined_source');assert.equal(filtered('index'),9);assert.equal(filtered('playing'),false);
  filteredElements.character.value='kirby';filteredElements.character.onchange();
  keys=filteredElements.action.options.map(o=>o.value);
  const cutterKeys=['attack-324-combined_source','attack-328-combined_source',...Array.from({length:8},(_,i)=>`attack-${324+i}_source`)];
  const cutterPositions=cutterKeys.map(key=>keys.indexOf(key)).sort((a,b)=>a-b);
  assert(cutterPositions.every((p,i)=>p===cutterPositions[0]+i));
  filteredElements.hidepartials.checked=true;filteredElements.hidepartials.onchange();
  assert(Array.from({length:8},(_,i)=>`attack-${324+i}_source`).every(key=>!filteredElements.action.options.some(o=>o.value===key)));
  filteredElements.character.value='mario';filteredElements.character.onchange();
  filteredElements.animationtype.value='tech';filteredElements.animationtype.onchange();
  assert.equal(filteredElements.action.options.length,5,'three tech rolls and two combined missed-tech choices');
  // Existing links to individual phases remain usable without opting in again.
  const linkElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  const linkContext=vm.createContext({document:{getElementById:id=>linkElements[id],createElement:()=>({})},location:{protocol:'file:',hash:'#character=fox&action=attack-296_source&costume=2'},URLSearchParams,
    performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{}});
  vm.runInContext(script,linkContext);
  assert.equal(linkElements.hidepartials.checked,false);assert.equal(linkElements.action.value,'attack-296_source');assert.equal(linkElements.costume.value,'2');

  // Native HTMLSelectElement clears values that are absent from its current options.
  // Handoffs must rebuild the category before selecting a requested animation.
  for(const [slug,key,partial] of [['mario','victory3_source',false],['fox','attack-296_source',true],['mario','movement-fullhop_source',false]]){
    const nativeElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
    let selected='';
    Object.defineProperty(nativeElements.action,'value',{
      get(){return this.options.some(o=>o.value===selected)?selected:''},
      set(value){selected=this.options.some(o=>o.value===String(value))?String(value):''}
    });
    nativeElements.action.append=function(option){if(!this.options.length)selected=option.value;this.options.push(option)};
    const nativeContext=vm.createContext({document:{getElementById:id=>nativeElements[id],createElement:()=>({})},location:{protocol:'file:',hash:`#character=${slug}&action=${key}&costume=0&frame=3&playing=false`},URLSearchParams,
      history:{replaceState(){}},performance:{now:()=>0},Image:class{},requestAnimationFrame(){}});
    vm.runInContext(script,nativeContext);
    assert.equal(nativeElements.action.value,key,'cross-category handoff keeps the requested native-select choice');
    assert.equal(nativeElements.hidepartials.checked,!partial);
    assert.equal(vm.runInContext('index',nativeContext),3);
    assert.equal(vm.runInContext('playing',nativeContext),false);
  }

  // File-origin resized batches transfer their exact selection to HTTP first.
  elements.character.value='mario';elements.character.onchange();elements.animationtype.value='victory';elements.animationtype.onchange();
  elements.action.value='victory3_source';elements.action.onchange();elements.scrub.value='7';elements.scrub.oninput();
  elements.downloadsize.value='256';elements.downloadsize.onchange();
  await elements.framezip.onclick({preventDefault(){}});
  const batchFragment=new URL(context.location.href).hash;
  assert.equal(new URLSearchParams(batchFragment.slice(1)).get('batch'),'png');
  const batchElements=Object.fromEntries(Object.keys(elements).map(id=>[id,{value:'0',textContent:'',checked:false,options:id==='downloadsize'?[128,256,512,1024,2048].map(value=>({value:String(value),textContent:''})):[],append(option){this.options.push(option)}}]));
  const batchSaved=[];let batchRequest;
  const batchContext=vm.createContext({document:{getElementById:id=>batchElements[id],body:{append(){}},createElement:()=>({click(){batchSaved.push(this.download)},remove(){}})},
    location:{protocol:'http:',hash:batchFragment},URLSearchParams,performance:context.performance,Image:context.Image,requestAnimationFrame:()=>{},
    fetch:url=>new Promise(resolve=>{batchRequest={url,resolve}})});
  vm.runInContext(script,batchContext);
  const batchQuery=new URL(batchRequest.url,'http://localhost');assert.equal(batchQuery.pathname,'/prepare-export');
  for(const [key,value] of Object.entries({kind:'png',scope:'colors',frame:'7',size:'256'}))assert.equal(batchQuery.searchParams.get(key),value);
  batchRequest.resolve({ok:true,json:async()=>({url:'/downloads/still.zip'})});await settle();
  assert.equal(batchSaved.length,1);assert.match(batchSaved[0],/frame-0008-all-colors-256px.zip$/);

  assert.equal(data('clips.filter(c=>c.sleep_bubbles).length'),18);
  elements.character.value='pikachu';elements.character.onchange();elements.animationtype.value='victory';elements.animationtype.onchange();
  elements.action.value='victory3_source';elements.action.onchange();
  assert.equal(elements.effecthint.hidden,false);assert.match(elements.effecthint.textContent,/Sleep bubbles/);
  elements.action.value='victory3_wait';elements.action.onchange();assert.match(elements.effecthint.textContent,/fading bubbles/);
  elements.action.value='victory1_source';elements.action.onchange();assert.equal(elements.effecthint.hidden,true);

  // Batch scopes track the selected type/family, independently of costume and partial display.
  elements.character.value='mario';elements.character.onchange();elements.animationtype.value='victory';elements.animationtype.onchange();
  assert.match(elements.allzip.textContent,/738 GIFs/);assert.match(elements.allzip.textContent,/victory poses/);
  assert.equal(elements.kirbymode.checked,false);
  elements.kirbymode.checked=true;elements.kirbymode.onchange();
  assert.match(elements.allzip.textContent,/1638 GIFs/);
  assert.equal(new URL(elements.allzip.href).searchParams.get('hats'),'all');
  assert(!new URL(elements.gif.href).searchParams.has('hats'),'individual files keep the selected appearance');
  elements.animationtype.value='clapping';elements.animationtype.onchange();
  assert.match(elements.allzip.textContent,/273 GIFs/);
  elements.synccycle.checked=true;elements.synccycle.onchange();assert.match(elements.allzip.textContent,/synced/);
  assert.equal(new URL(elements.allzip.href).searchParams.get('cycle'),'sync');
  elements.character.value='kirby';elements.character.onchange();
  elements.scrub.value='3';elements.scrub.oninput();
  assert.equal(new URL(elements.framezip.href).searchParams.get('hats'),'all');
  assert.match(elements.animationzip.textContent,/156 GIFs/);
  const retainedIndex=data('index');elements.kirbymode.checked=false;elements.kirbymode.onchange();
  assert.equal(data('index'),retainedIndex);assert.equal(data('playing'),false);
  assert.match(elements.allzip.textContent,/123 GIFs/);
  elements.character.value='fox';elements.character.onchange();elements.animationtype.value='attack';elements.animationtype.onchange();
  elements.action.value='attack-295-combined_source';elements.action.onchange();
  const family=data('clips[current].batch_family');
  const matching=data('clips').filter(c=>c.batch_family===family&&!c.batch_partial);
  assert(matching.some(c=>c.character==='mario'));assert(matching.some(c=>c.character==='falco'));
  assert(matching.some(c=>c.sequence));assert(matching.every(c=>!c.batch_partial));
  assert.match(elements.allzip.textContent,/Neutral special/);
  assert.equal(new URL(elements.allzip.href).searchParams.get('scope'),'all');
  elements.hidepartials.checked=false;elements.hidepartials.onchange();
  const sameCount=elements.allzip.textContent;elements.action.value='attack-295_source';elements.action.onchange();
  assert.equal(elements.allzip.textContent,sameCount,'a phase and its combined action select the same all-character family');
  elements.character.value='kirby';elements.character.onchange();elements.animationtype.value='clapping';elements.animationtype.onchange();
  elements.kirbymode.checked=true;elements.kirbymode.onchange();
  await elements.animationzip.onclick({preventDefault(){}});
  assert.equal(new URLSearchParams(new URL(context.location.href).hash.slice(1)).get('hats'),'all');

  // Resolution labels/notices follow type, and explicit requested sizes survive handoff.
  elements.character.value='mario';elements.character.onchange();elements.animationtype.value='clapping';elements.animationtype.onchange();
  elements.downloadsize.value='1024';elements.downloadsize.onchange();
  assert.equal(data('nativeDefaultSize'),1024);assert.equal(elements.upsizenotice.hidden,true);
  elements.downloadsize.value='512';elements.downloadsize.onchange();
  assert.equal(elements.upsizenotice.hidden,true);
  elements.downloadsize.value='2048';elements.downloadsize.onchange();
  assert.equal(elements.upsizenotice.hidden,false);assert.match(elements.upsizenotice.textContent,/1024/);
  elements.downloadsize.value='1024';elements.downloadsize.onchange();
  elements.animationtype.value='attack';elements.animationtype.onchange();
  assert.equal(elements.downloadsize.value,'512');assert.equal(data('nativeDefaultSize'),512);
  assert(elements.downloadsize.options.find(o=>o.value==='512').textContent.startsWith('\u2605'));
  assert(!elements.downloadsize.options.find(o=>o.value==='1024').textContent.startsWith('\u2605'));
  elements.downloadsize.value='1024';elements.downloadsize.onchange();
  assert.equal(elements.upsizenotice.hidden,false);assert.match(elements.upsizenotice.textContent,/512/);
  elements.animationtype.value='taunt';elements.animationtype.onchange();
  assert.equal(data('nativeDefaultSize'),1024);assert.equal(elements.upsizenotice.hidden,true);
  console.log('Type-specific1024 results/512 actions, native stars, default transitions and upsize notices: PASS');
  elements.character.value='game-and-watch';elements.character.onchange();
  elements.animationtype.value='attack';elements.animationtype.onchange();
  elements.action.value='attack-305_source';elements.action.onchange();
  assert.equal(elements.electriccontrols.hidden,false);assert.equal(elements.judgeelectric.checked,true);
  elements.scrub.value='3';elements.scrub.oninput();
  elements.judgeelectric.checked=false;elements.judgeelectric.onchange();
  assert.equal(new URL(elements.gif.href).searchParams.get('electric'),'off');
  assert.equal(new URL(elements.framezip.href).searchParams.get('electric'),'off');
  assert.equal(data('index'),3);assert.equal(data('playing'),false);
  assert.match(elements.gif.download,/-no-electric-512px.gif$/);
  assert.equal(new URL(data('playerHandoff()')).hash.includes('electric=off'),true);
  elements.action.value='attack-304_source';elements.action.onchange();
  assert.equal(elements.electriccontrols.hidden,true);assert.equal(new URL(elements.gif.href).searchParams.has('electric'),false);
  console.log('Judgment9-only default-on electric toggle, exact/color exports, paused retention and handoff: PASS');
  console.log('Scoped victory/clap/attack groups, counts, all hats/colors, exact stills, retained frame and batch handoff: PASS');
  console.log('Shared roster color names and exact file-to-HTTP batch handoff: PASS');
  console.log('Selector rows, default partial filter, all-character choices, contiguous families, fallback, paused retention and handoff: PASS');
  console.log('Animation Type filtering, hidden single-choice menus, attack loading/stills/colors and stale selection protection: PASS');
  console.log('Rotation Apply/Reset, pending/error states, stale responses, exact paused frames, mode/costume retention and sized downloads: PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
