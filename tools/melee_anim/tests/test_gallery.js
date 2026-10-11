// Test the generated player's control/timer logic without a browser connector.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = path.resolve('build/melee_anim/preview/player.html');
const html = fs.readFileSync(page, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = Object.fromEntries(['character', 'still', 'framezip', 'action', 'costume', 'frame', 'play', 'restart', 'loop', 'scrub', 'time', 'gif', 'animationzip', 'allzip', 'open', 'meta']
  .map(id => [id, {value: '0', textContent: '', checked: false, options: [], append(option) {this.options.push(option);}}]));
const context = vm.createContext({document: {getElementById: id => elements[id], createElement: () => ({})},
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
  assert.equal(elements.gif.download, clip.download_name);
  assert.match(elements.gif.download, /\.gif$/);
  elements.scrub.value='3';elements.scrub.oninput();
  assert.equal(elements.still.href,clip.frames[3]);assert.equal(elements.still.hidden,false);
  assert.equal(elements.framezip.hidden,false);
  assert.match(elements.still.download,/frame-0004.png$/);
  assert(fs.existsSync(path.join(path.dirname(page),elements.framezip.href)));
  const a = data('animations.find(a => a.key === action.value && a.character === character.value)');
  assert.equal(elements.animationzip.href, a.zip);
  assert.equal(elements.animationzip.download, a.download_name);
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
assert.match(elements.still.download,/frame-0068.png$/);
assert.match(elements.framezip.href,/frame-0068.zip$/);
assert(html.includes('download="melee-all-characters-all-animations.zip"'));
assert(fs.existsSync(path.join(path.dirname(page), 'downloads/melee-all-characters-all-animations.zip')));
console.log('Playback, color retention, selected GIF download, ZIP links, and frame references: PASS');
