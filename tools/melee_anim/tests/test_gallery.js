// Test the generated player's control/timer logic without a browser connector.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = path.resolve('build/melee_anim/preview/player.html');
const html = fs.readFileSync(page, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = Object.fromEntries(['minimumcycle','cyclehint','downloadsize', 'servicehint', 'character', 'still', 'framezip', 'action', 'costume', 'frame', 'play', 'restart', 'loop', 'scrub', 'time', 'gif', 'animationzip', 'allzip', 'open', 'meta']
  .map(id => [id, {value: '0', textContent: '', checked: false, options: [], append(option) {this.options.push(option);}}]));
const context = vm.createContext({document: {getElementById: id => elements[id], createElement: () => ({})},
  location: {protocol:'file:'}, URLSearchParams,
  performance: {now: () => 0}, Image: class {}, requestAnimationFrame: callback => {context.nextFrame = callback;}});
vm.runInContext(script, context);
const data = expression => vm.runInContext(expression, context);
assert.equal(elements.action.options.length, 8);
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
for (const clip of data('clips')) {
  for (const frame of clip.frames) assert(fs.existsSync(path.join(path.dirname(page), frame)), frame);
  assert(fs.existsSync(path.join(path.dirname(page), clip.gif)), clip.gif);
}

for (const clip of data('clips')) {
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
  elements.minimumcycle.checked=false;elements.minimumcycle.onchange();
  assert.equal(data('frameCount()'),data('clips[current].frames.length'));
  assert.equal(elements.gif.href,data('clips[current].gif'));
}
elements.character.value='mario';elements.character.onchange();
elements.action.value='taunt_source';elements.action.onchange();
assert.equal(elements.minimumcycle.disabled,true);
assert.equal(elements.minimumcycle.checked,false);
// Served pages use their own origin, including a user-selected server port.
const servedElements=Object.fromEntries(Object.keys(elements).map(id=>[id,
  {value:'0',textContent:'',checked:false,options:[],append(option){this.options.push(option)}}]));
vm.runInContext(script,
  vm.createContext({document:{getElementById:id=>servedElements[id],createElement:()=>({})}, location:{protocol:'http:'}, URLSearchParams,
    performance:context.performance, Image:context.Image, requestAnimationFrame:()=>{}}));
assert.equal(servedElements.servicehint.hidden,true);
servedElements.downloadsize.value='512';servedElements.downloadsize.onchange();
assert(servedElements.gif.href.startsWith('/export?'));
console.log('Playback, color/frame retention, sized GIF/PNG downloads, ZIP links, and file/HTTP origins: PASS');
