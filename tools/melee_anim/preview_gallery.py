"""Create an offline playback page from completed preview manifests.

Open build/melee_anim/preview/player.html in a browser. No server, CDN,
account, or package download is required; generated game-derived frames
remain ignored alongside the player output.
"""

import argparse
import json
from pathlib import Path


TEMPLATE = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Melee animation preview</title>
<style>
body{font:16px system-ui;background:#161b22;color:#edf2f7;margin:0;padding:32px;max-width:1040px;margin:auto}
h1{margin:0 0 8px;font-size:28px}p{color:#b5c0ce;line-height:1.5}select,button,input{font:inherit}
select,button{padding:10px;border:1px solid #445368;border-radius:6px;background:#263243;color:inherit}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}
.stage{background:#22262e;border:1px solid #354151;border-radius:12px;display:flex;justify-content:center;min-height:400px;align-items:center}
#frame{image-rendering:auto;width:min(100%,512px);height:auto}.timeline{display:flex;gap:12px;align-items:center;margin:20px 0}
#scrub{flex:1}a{color:#81baff}.meta{background:#202a36;padding:16px;border-radius:8px}
</style><h1>Melee animation preview</h1>
<p>Original Mario models, costumes, and animation curves. This prototype approximates lighting and materials; game scripts, effects, props, dynamics, and audio are not played.</p>
<div class="controls"><select id="clip" aria-label="Animation and costume"></select>
<button id="play">Pause</button><button id="restart">Restart</button>
<label><input id="loop" type="checkbox"> Repeat</label><a id="gif">Open GIF</a></div>
<div class="stage"><img id="frame" alt="Animated character preview"></div>
<div class="timeline"><input id="scrub" type="range" min="0" value="0" step="1" aria-label="Source frame"><span id="time"></span></div>
<div class="meta" id="meta"></div>
<p>Zelda and Sheik and all other characters have separate verified action/costume catalog entries. This first rendered player currently supports Mario. Nonlooping actions may jump if Repeat is enabled; the original clapping seam is preserved.</p>
<script>
const clips=__CLIPS__;
const choose=document.getElementById('clip'), frame=document.getElementById('frame'),
play=document.getElementById('play'), restart=document.getElementById('restart'),
loop=document.getElementById('loop'), scrub=document.getElementById('scrub'), clock=document.getElementById('time');
let current=0,index=0,playing=true,last=performance.now(),carry=0;
clips.forEach((c,i)=>{let option=document.createElement('option');option.value=i;option.textContent=c.label;choose.append(option)});
function show(){let c=clips[current];frame.src=c.frames[index];scrub.value=index;
clock.textContent=`${index+1}/${c.frames.length} · source ${c.source_times[index].toFixed(2)}`}
function select(){current=Number(choose.value);index=0;carry=0;last=performance.now();let c=clips[current];
scrub.max=c.frames.length-1;loop.checked=c.authored_loop;playing=true;play.textContent='Pause';
document.getElementById('gif').href=c.gif;
document.getElementById('meta').textContent=`${c.symbol} · ${c.period} source frames · ${c.fps} fps preview · ${c.authored_loop?'authored loop':'one-shot action'}`;
c.frames.forEach(src=>{let image=new Image();image.src=src});show()}
choose.onchange=select;play.onclick=()=>{playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now();carry=0};
restart.onclick=()=>{index=0;last=performance.now();carry=0;playing=true;play.textContent='Pause';show()};
scrub.oninput=()=>{index=Number(scrub.value);playing=false;play.textContent='Play';show()};
function tick(now){let c=clips[current];if(playing){carry+=Math.min(now-last,250);let step=1000/c.fps;
while(carry>=step){carry-=step;if(index+1<c.frames.length)index++;else if(loop.checked)index=0;else{playing=false;play.textContent='Play';break}}show()}last=now;requestAnimationFrame(tick)}
if(clips.length){select();requestAnimationFrame(tick)}
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("build/melee_anim/preview"))
    args = parser.parse_args()
    clips = []
    for path in sorted((args.root / "mario").rglob("preview-manifest.json")):
        manifest = json.loads(path.read_text())
        if not manifest["complete_interval"]:
            continue
        relative = path.parent.relative_to(args.root).as_posix()
        times = manifest["sample_source_times"]
        if not (path.parent/"preview.gif").is_file() or not all((path.parent/f"frame_{i:04d}.png").is_file() for i in range(len(times))):
            raise ValueError(f"Incomplete preview files: {path}")
        costume = path.parent.parent.name
        clips.append({"label": f"Mario {costume.replace('_', ' ')} — {manifest['action']} / {manifest['section']}",
                      "fps": manifest["fps"], "period": manifest["source_period_frames"],
                      "authored_loop": manifest["authored_loop"], "symbol": manifest["source_symbol"],
                      "source_times": times, "gif": f"{relative}/preview.gif",
                      "frames": [f"{relative}/frame_{i:04d}.png" for i in range(len(times))]})
    if not clips:
        parser.error("No complete rendered Mario preview manifests found")
    output = args.root / "player.html"
    output.write_text(TEMPLATE.replace("__CLIPS__", json.dumps(clips).replace("<", "\\u003c")), encoding="utf-8")
    print(f"Offline player: {output} ({len(clips)} completed clips)")


if __name__ == "__main__":
    main()
