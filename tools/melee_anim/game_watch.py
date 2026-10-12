"""Game & Watch's source class-4 color/depth passes (ftdrawcommon/ftmaterial)."""
import numpy as np


def outline_color(body, overlay):
    """TEV interpolates RGB by overlay alpha; material alpha stays opaque."""
    weight = overlay[3]
    return [(body[i] * (255-weight) + overlay[i] * weight + 127)//255
            for i in range(3)] + [body[3]]


def draw_passes(model, posed, center, view):
    pairs = list(zip(model['meshes'], posed))
    outlines = [pair for pair in pairs if pair[0].get('outline_pass')]
    ordinary = [pair for pair in pairs if not pair[0].get('outline_pass')]
    translucent = lambda pair: bool(model['materials'][pair[0]['material_index']].get('item_alpha_blend'))
    opaque = [pair for pair in ordinary if not translucent(pair)]
    alpha = [pair for pair in ordinary if translucent(pair)]
    alpha.sort(key=lambda pair: np.mean((pair[1][0]-center)@view,axis=0)[2]
               if pair[1][0] is not None else 0)
    # First outline draw does not update depth. The final source pass writes
    # only depth (PE flags 0x38), before later translucent attachments.
    return [(m,p,'outline-color') for m,p in outlines] + [(m,p,'body') for m,p in opaque] + \
        [(m,p,'outline-depth') for m,p in outlines] + [(m,p,'body') for m,p in alpha]
