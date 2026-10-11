"""Fast Windows offscreen rasterization using the system OpenGL runtime.

Creates only a memory DC/DIB, no window and no desktop capture. Pose/skinning
remain in Python. The native triangle/depth/texture rasterizer avoids a Python
loop per triangle. Win32 layouts follow Microsoft's wingdi/WGL documentation.
"""

import ctypes as C
from ctypes import wintypes as W
import os

import numpy as np
from PIL import Image,ImageFilter


class PFD(C.Structure):
    _fields_ = [("nSize", W.WORD), ("nVersion", W.WORD), ("dwFlags", W.DWORD)] + [
        (n, W.BYTE) for n in ("iPixelType", "cColorBits", "cRedBits", "cRedShift", "cGreenBits", "cGreenShift",
        "cBlueBits", "cBlueShift", "cAlphaBits", "cAlphaShift", "cAccumBits", "cAccumRedBits", "cAccumGreenBits",
        "cAccumBlueBits", "cAccumAlphaBits", "cDepthBits", "cStencilBits", "cAuxBuffers", "iLayerType", "bReserved")
    ] + [(n, W.DWORD) for n in ("dwLayerMask", "dwVisibleMask", "dwDamageMask")]


class BMI(C.Structure):
    _fields_ = [("size", W.DWORD), ("width", W.LONG), ("height", W.LONG), ("planes", W.WORD),
                ("bits", W.WORD), ("compression", W.DWORD), ("image_size", W.DWORD),
                ("xppm", W.LONG), ("yppm", W.LONG), ("used", W.DWORD), ("important", W.DWORD)]


class NativeRaster:
    def __init__(self, size):
        if os.name != "nt":
            raise RuntimeError("Native bitmap rasterizer requires Windows")
        self.size, self.texture_ids = size, {}
        self.gdi, self.gl = C.WinDLL("gdi32", use_last_error=True), C.WinDLL("opengl32", use_last_error=True)
        def api(lib, name, restype, args):
            f = getattr(lib, name); f.restype = restype; f.argtypes = args; return f
        ptr, ui, integer, fl = C.c_void_p, C.c_uint, C.c_int, C.c_float
        self.dc = api(self.gdi, "CreateCompatibleDC", ptr, [ptr])(None)
        self.select = api(self.gdi, "SelectObject", ptr, [ptr, ptr])
        self.delete_dc = api(self.gdi, "DeleteDC", W.BOOL, [ptr])
        self.delete_object = api(self.gdi, "DeleteObject", W.BOOL, [ptr])
        bmi = BMI(C.sizeof(BMI), size, -size, 1, 32, 0, size*size*4, 0, 0, 0, 0)
        bits = ptr()
        self.bitmap = api(self.gdi, "CreateDIBSection", ptr, [ptr, C.POINTER(BMI), ui, C.POINTER(ptr), ptr, ui])(
            self.dc, C.byref(bmi), 0, C.byref(bits), None, 0)
        if not self.dc or not self.bitmap:
            raise C.WinError(C.get_last_error())
        self.previous = self.select(self.dc, self.bitmap)
        pfd = PFD(); pfd.nSize=C.sizeof(PFD); pfd.nVersion=1; pfd.dwFlags=0x28; pfd.cColorBits=32; pfd.cDepthBits=24
        fmt = api(self.gdi, "ChoosePixelFormat", integer, [ptr, C.POINTER(PFD)])(self.dc, C.byref(pfd))
        if not fmt or not api(self.gdi, "SetPixelFormat", W.BOOL, [ptr, integer, C.POINTER(PFD)])(self.dc, fmt, C.byref(pfd)):
            raise C.WinError(C.get_last_error())
        self.context = api(self.gl, "wglCreateContext", ptr, [ptr])(self.dc)
        self.make_current = api(self.gl, "wglMakeCurrent", W.BOOL, [ptr, ptr])
        self.delete_context = api(self.gl, "wglDeleteContext", W.BOOL, [ptr])
        if not self.context or not self.make_current(self.dc, self.context):
            raise C.WinError(C.get_last_error())
        specs = {
            "glViewport":[integer]*4, "glClearColor":[fl]*4,"glClear":[ui],"glEnable":[ui],"glDisable":[ui],
            "glDepthFunc":[ui],"glAlphaFunc":[ui,fl],"glMatrixMode":[ui],"glLoadIdentity":[],
            "glOrtho":[C.c_double]*6,"glEnableClientState":[ui],"glDisableClientState":[ui],
            "glVertexPointer":[integer,ui,integer,ptr],"glColorPointer":[integer,ui,integer,ptr],
            "glTexCoordPointer":[integer,ui,integer,ptr],"glDrawElements":[ui,integer,ui,ptr],
            "glGenTextures":[integer,C.POINTER(ui)],"glBindTexture":[ui,ui],"glTexParameteri":[ui,ui,integer],
            "glTexImage2D":[ui,integer,integer,integer,integer,integer,ui,ui,ptr],
            "glReadPixels":[integer,integer,integer,integer,ui,ui,ptr],"glPixelStorei":[ui,integer],"glFinish":[],
            "glCullFace":[ui],"glFrontFace":[ui],"glGetError":[],"glGetString":[ui]}
        for name, args in specs.items():
            api(self.gl,name,C.c_uint if name=="glGetError" else C.c_char_p if name=="glGetString" else None,args)
        self.renderer = self.gl.glGetString(0x1F01).decode()
        self.gl.glViewport(0,0,size,size); self.gl.glEnable(0x0B71); self.gl.glDepthFunc(0x0201)
        self.gl.glEnable(0x0BC0); self.gl.glAlphaFunc(0x0206,.5); self.gl.glDisable(0x0BD0)
        self.gl.glFrontFace(0x0900)  # GX model display lists use clockwise fronts.
        self.gl.glEnableClientState(0x8074); self.gl.glEnableClientState(0x8076)
        self.gl.glMatrixMode(0x1701); self.gl.glLoadIdentity(); self.gl.glOrtho(-1,1,-1,1,-1000,1000)
        self.gl.glMatrixMode(0x1700); self.gl.glLoadIdentity(); self.gl.glPixelStorei(0x0CF5,1)

    def texture(self, key, pixels, desc):
        key = (key, desc.get("wrap_s",1), desc.get("wrap_t",1))
        if key in self.texture_ids:
            return self.texture_ids[key]
        if key[1]==2: pixels=np.concatenate((pixels,pixels[:,::-1]),axis=1)
        if key[2]==2: pixels=np.concatenate((pixels,pixels[::-1]),axis=0)
        h,w=pixels.shape[:2]; pw,ph=1<<(w-1).bit_length(),1<<(h-1).bit_length()
        if (pw,ph)!=(w,h): pixels=np.asarray(Image.fromarray(pixels).resize((pw,ph),Image.Resampling.NEAREST))
        pixels=np.ascontiguousarray(pixels,dtype=np.uint8); tex=C.c_uint(); self.gl.glGenTextures(1,C.byref(tex))
        self.gl.glBindTexture(0x0DE1,tex.value)
        for axis,mode in ((0x2802,key[1]),(0x2803,key[2])):
            self.gl.glTexParameteri(0x0DE1,axis,0x2900 if mode==0 else 0x2901)
        for filt in (0x2800,0x2801):self.gl.glTexParameteri(0x0DE1,filt,0x2600)
        self.gl.glTexImage2D(0x0DE1,0,0x1908,pw,ph,0,0x1908,0x1401,pixels.ctypes.data)
        self.texture_ids[key]=tex.value
        return tex.value

    def render(self,model,posed,textures,view,width,height,center,pixels_per_unit,background):
        self.gl.glClearColor(*(v/255 for v in background)); self.gl.glClear(0x4100)
        light=np.array([-.35,.6,.72]); light/=np.linalg.norm(light)
        for mesh,(positions,normals) in zip(model["meshes"],posed):
            if positions is None:
                continue
            mat=model["materials"][mesh["material_index"]]
            candidates=[t for t in mat["textures"] if t.get("coordinate_type",0)==0 and t.get("image_file") in textures]
            base=next((t for t in candidates if ((t.get("flags",0)>>16)&15) in (4,5)),candidates[0] if candidates else None)
            verts=np.ascontiguousarray((positions-center)@view,dtype=np.float32)
            verts[:,:2]*=pixels_per_unit*2/width
            rgba=np.array(mat.get("diffuse_rgba") or [255]*4,dtype=np.float32)/255
            shade=np.ones(len(verts)) if mat.get("unlit") else .6+.4*np.maximum(0,normals@light)
            colors=np.tile(rgba,(len(verts),1)); colors[:,:3]*=shade[:,None]
            colors[:,3]*=mat.get("alpha",1)
            if base:
                uvset=str(max(0,base.get("source",4)-4)); uv=np.asarray(mesh.get("uv_sets",{}).get(uvset,mesh["uvs"]))
                coords=np.column_stack((uv,np.ones((len(uv),2))))
                uv=(coords@np.asarray(base["texture_matrix"]).T)[:,:2]
                for i,mode in enumerate((base.get("wrap_s",1),base.get("wrap_t",1))):
                    if mode==2:uv[:,i]/=2
                uv=np.ascontiguousarray(uv,dtype=np.float32)
                if ((base.get("flags",0)>>16)&15)==5:colors[:,:3]=shade[:,None]
                self.gl.glEnable(0x0DE1);self.gl.glEnableClientState(0x8078)
                self.gl.glBindTexture(0x0DE1,self.texture(base["image_file"],textures[base["image_file"]],base))
                self.gl.glTexCoordPointer(2,0x1406,0,uv.ctypes.data)
            else:self.gl.glDisable(0x0DE1);self.gl.glDisableClientState(0x8078)
            flags=mesh.get("cull_flags",0)&0xC000
            if flags:self.gl.glEnable(0x0B44);self.gl.glCullFace(0x0405 if flags==0x8000 else 0x0404 if flags==0x4000 else 0x0408)
            else:self.gl.glDisable(0x0B44)
            indices=np.ascontiguousarray(mesh["triangles"],dtype=np.uint32)
            self.gl.glVertexPointer(3,0x1406,0,verts.ctypes.data);self.gl.glColorPointer(4,0x1406,0,colors.ctypes.data)
            self.gl.glDrawElements(4,indices.size,0x1405,indices.ctypes.data)
        pixels=np.empty((height,width,4),dtype=np.uint8)
        self.gl.glFinish();self.gl.glReadPixels(0,0,width,height,0x1908,0x1401,pixels.ctypes.data)
        error=self.gl.glGetError()
        if error:raise RuntimeError(f"Native raster OpenGL error {error:#x}")
        pixels=np.flipud(pixels).copy()
        if model.get('outline_rgba'):
            depth=np.empty((height,width),dtype=np.float32)
            self.gl.glReadPixels(0,0,width,height,0x1902,0x1406,depth.ctypes.data)
            mask=np.flipud(depth)<.999999
            expanded=np.asarray(Image.fromarray((mask*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)))>0
            border=expanded&~mask;outline=np.array(model['outline_rgba'])
            pixels[border,:3]=(outline[:3]*(outline[3]/255)+np.array(background[:3])*(1-outline[3]/255)).astype(np.uint8)
        return Image.fromarray(pixels)

    def close(self):
        self.make_current(None,None);self.delete_context(self.context)
        self.select(self.dc,self.previous);self.delete_object(self.bitmap);self.delete_dc(self.dc)
