"""Verified roster identities and costume-specific spawn visibility defaults."""

from functools import lru_cache
import re
from pathlib import Path

from .catalog import CHARACTERS
from .hsd import Dol, load_symbols, read_global
from .inspect_models import costume_catalog


@lru_cache(maxsize=4)
def roster(files=Path("orig/GALE01/files"), *, include_extra=False):
    return costume_catalog(Path(files),Path("orig/GALE01/sys/main.dol"),Path("config/GALE01/symbols.txt"),include_extra=include_extra)


def primary(slug, files=Path("orig/GALE01/files")):
    names={s:i for i,(s,_) in enumerate(CHARACTERS)}
    if slug not in names:raise ValueError(f"Unknown character {slug}")
    return next(f for f in roster(files)["fighters"] if f["character_kind"]==names[slug] and not f["paired_member"])


def color_label(costume, kind):
    if kind==24:return ("Black","Red","Blue","Green")[costume["costume_id"]]
    suffix=Path(costume["file"]).stem[4:]
    if kind==0 and suffix=='Nr':return 'Red (default)'
    colors={"Nr":"Default","Re":"Red","Bu":"Blue","Gr":"Green","Bk":"Black","Wh":"White",
            "Ye":"Yellow","Or":"Orange","Aq":"Aqua","La":"Lavender","Pi":"Pink","Gy":"Gray"}
    return colors.get(suffix,f"Costume {costume['costume_id']+1} ({suffix})")


@lru_cache(maxsize=1)
def death_handlers():
    dol=Dol(Path("orig/GALE01/sys/main.dol").read_bytes())
    symbols=load_symbols("config/GALE01/symbols.txt")
    by_address={v[0]:k for k,v in symbols.items()}
    raw=read_global(dol,symbols,"ftData_OnDeath")
    names=[by_address[int.from_bytes(raw[i:i+4],"big")] for i in range(0,len(raw),4)]
    result={}
    for p in Path("src/melee/ft/kinds").glob("*/*.c"):
        text=p.read_text()
        for name in names:
            match=re.search(r"void "+re.escape(name)+r"\([^)]*\)\s*\{",text)
            if match:
                i=match.end();start=i;depth=1
                while depth:
                    if text[i]=="{":depth+=1
                    elif text[i]=="}":depth-=1
                    i+=1
                result[names.index(name)]=text[start:i-1]
    return result


def visibility_defaults(kind,costume,count):
    """Source OnDeath resets called by Fighter_Spawn; handle costume switches."""
    text=death_handlers()[kind]
    # All handlers' group assignments are literal except the two explicit
    # costume switches below. Read only the unconditional prefix for those.
    if kind in (9,23):text=text.split("switch",1)[0]
    values=[-1]*count
    for group,value in re.findall(r"ftParts_80074A4C\(\w+,\s*(\d+)U?,\s*(-?\d+)\)",text):
        if int(group)<count:values[int(group)]=int(value)
    if kind==9:
        for i,v in ({1:-1,5:0,6:-1} if costume==1 else {1:0,5:-1,6:0}).items():values[i]=v
    if kind==23:
        for i in range(1,4):values[i]=0 if costume==i else -1
    return values


def visible_drawables(model,states=None):
    groups=model["visibility"]["groups"]
    states=states if states is not None else model["visibility"]["defaults"]
    hidden={d for group in groups for option in group for d in option}
    outlines=model['visibility'].get('outline_groups',[])
    hidden.update(d for group in outlines for option in group for d in option)
    visible=set(model["visibility"]["base"])-hidden
    for i,group in enumerate(groups):
        if 0<=states[i]<len(group):visible.update(group[states[i]])
    for i,group in enumerate(outlines):
        if 0<=states[i]<len(group):visible.update(group[states[i]])
    return visible
