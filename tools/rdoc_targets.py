# Run inside RenderDoc's Python: qrenderdoc.exe --python tools/rdoc_targets.py
# Job file tools/rdoc_job.json: {"capture": ..., "out": ...}
# Lists every draw with its render targets (format, size), viewport and shaders,
# grouped into runs of consecutive draws with the same targets, so small offscreen
# passes (like building a bone-matrix texture) stand out.
import json
import os
import sys
import traceback

import renderdoc as rd

HERE = (os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals()
        else os.path.join(os.path.expanduser("~"), "Documents", "fifa08-recomp", "tools"))
try:
    job = json.load(open(os.path.join(HERE, "rdoc_job.json"), encoding="utf-8-sig"))
    out = open(job["out"], "w")
except Exception:
    open(os.path.join(HERE, "rdoc_job_error.txt"), "w").write(traceback.format_exc())
    os._exit(1)


def log(*a):
    print(*a, file=out)
    out.flush()


def excepthook(kind, value, tb):
    log("".join(traceback.format_exception(kind, value, tb)))
    os._exit(1)


sys.excepthook = excepthook

cap = rd.OpenCaptureFile()
cap.OpenFile(job["capture"], "", None)
status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
textures = {t.resourceId: t for t in ctl.GetTextures()}

actions = []


def walk(acts):
    for a in acts:
        if a.flags & (rd.ActionFlags.Drawcall | rd.ActionFlags.Dispatch | rd.ActionFlags.Copy |
                      rd.ActionFlags.Resolve | rd.ActionFlags.Clear):
            actions.append(a)
        walk(a.children)


walk(ctl.GetRootActions())
sf = ctl.GetStructuredFile()
prev = None
for a in actions:
    ctl.SetFrameEvent(a.eventId, False)
    pipe = ctl.GetPipelineState()
    name = a.GetName(sf)
    if a.flags & rd.ActionFlags.Drawcall:
        rts = []
        for o in pipe.GetOutputTargets():
            if o.resource == rd.ResourceId.Null():
                continue
            t = textures.get(o.resource)
            size = f"{t.width}x{t.height}" if t else "?"
            rts.append(f"{int(o.resource)}:{o.format.Name()}:{size}")
        vp = pipe.GetViewport(0)
        key = (tuple(rts), int(vp.width), int(vp.height))
        line = (f"eid {a.eventId:5d} draw idx {a.numIndices:6d} vs {int(pipe.GetShader(rd.ShaderStage.Vertex))} "
                f"ps {int(pipe.GetShader(rd.ShaderStage.Pixel))} vp {int(vp.x)},{int(vp.y)} {int(vp.width)}x{int(vp.height)} "
                f"rt {' '.join(rts)}")
        if key != prev:
            log(line)
        prev = key
    else:
        log(f"eid {a.eventId:5d} {name}")
        prev = None

ctl.Shutdown()
cap.Shutdown()
out.close()
os._exit(0)
