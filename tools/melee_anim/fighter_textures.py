"""Source texture requests: fighter TObj animations are frozen at rate zero.

Opcode 40 requests a frame in a costume-specific TObj animation, not an image
number. Evaluate its original FObj before selecting the decoded image.
"""
from .held_items import script_events
from .motions import Track


class FighterTextures:
    def __init__(self, model, motion, folder, textures, prefix='', sequence=None):
        import numpy as np
        from PIL import Image
        self.mapping=model.get('texture_script_map',[])
        self.entries={}
        for material in model['materials']:
            for texture in material['textures']:
                images=texture.get('animation_images',[])
                if not images:continue
                tracks=[Track(0,t['channel'],t['startframe'],t['frac_value'],t['frac_slope'],bytes.fromhex(t['data']))
                        for t in texture.get('animation_tracks',[])]
                initial=texture['image_file']
                for name in images:
                    key=prefix+name
                    if key not in textures:textures[key]=np.asarray(Image.open(folder/name).convert('RGBA'))
                self.entries[texture['global_tobj_index']]=(texture,initial,[prefix+s for s in images],tracks)
        self.initial={}
        for script,duration in motion.get('texture_initial_scripts',[]):
            self.initial.update(self.requests(script,duration))
        self.events=script_events(motion.get('script',{}),motion['frames'])
        if sequence:
            self.events=[]
            for start,(_,_,phase) in zip(sequence.starts,sequence.phases):
                duration=phase['duration_ticks']
                self.events.extend((start+time,command) for time,command in
                    script_events(phase['clip'].get('script',{}),duration) if time<duration)

    def requests(self,script,duration):
        result={}
        for tick,command in script_events(script,duration):
            if tick>duration:break
            request=command.get('texture_animation')
            if request:
                result[request['index']]=request['frame']
                if request['both']:result[request['index2']]=request['frame']
        return result

    def apply(self,tick):
        requests=self.initial.copy()
        for time,command in self.events:
            if time>tick:break
            request=command.get('texture_animation')
            if request:
                requests[request['index']]=request['frame']
                if request['both']:requests[request['index2']]=request['frame']
        for _,(texture,initial,images,tracks) in self.entries.items():texture['image_file']=initial
        for index,frame in requests.items():
            if index<0 or index>=len(self.mapping):continue
            entry=self.entries.get(self.mapping[index])
            if entry is None:continue
            texture,_,images,tracks=entry
            for track in tracks:
                value=track.evaluate(frame)
                if value is not None:
                    image=int(value)
                    if not 0<=image<len(images):raise ValueError('Fighter texture image is out of bounds')
                    texture['image_file']=images[image]
