# Run inside RenderDoc's Python: qrenderdoc.exe --python tools/rdoc_scan.py
# Settings come from rdoc_job.json next to this script: {"capture": ..., "out": ...}
# (qrenderdoc passes no arguments to the script).
# Lists the draws in a capture with their vertex counts and bound resources,
# so the skinned player meshes can be picked out.
import json
import os
import sys
import traceback

import renderdoc as rd

# qrenderdoc exec()s the script, so __file__ may be missing.
HERE = (os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals()
        else os.path.join(os.path.expanduser("~"), "Documents", "fifa08-recomp", "tools"))
try:
    job = json.load(open(os.path.join(HERE, "rdoc_job.json"), encoding="utf-8-sig"))
except Exception:
    open(os.path.join(HERE, "rdoc_job_error.txt"), "w").write(traceback.format_exc())
    os._exit(1)
cap_path = job["capture"]
out = open(job["out"], "w")


def log(*a):
    print(*a, file=out)
    out.flush()


def excepthook(kind, value, tb):
    log("".join(traceback.format_exception(kind, value, tb)))
    os._exit(1)


sys.excepthook = excepthook


cap = rd.OpenCaptureFile()
status = cap.OpenFile(cap_path, "", None)
if status != rd.ResultCode.Succeeded:
    log("open failed", status)
    sys.exit(0)
status, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
if status != rd.ResultCode.Succeeded:
    log("replay failed", status)
    sys.exit(0)

draws = []


def walk(actions):
    for a in actions:
        if a.flags & rd.ActionFlags.Drawcall:
            draws.append(a)
        walk(a.children)


walk(ctl.GetRootActions())
log(f"{len(draws)} draws")
def dump(actions, depth=0):
    for a in actions:
        log("  " * depth + f"eid {a.eventId} flags {int(a.flags):#x} {a.GetName(ctl.GetStructuredFile())}")
        dump(a.children, depth + 1)
res = ctl.GetResources()
log(f"{len(res)} resources")

for d in draws:
    ctl.SetFrameEvent(d.eventId, False)
    pipe = ctl.GetPipelineState()
    vs = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
    if not vs:
        continue
    floats = 0
    for cb in vs.constantBlocks:
        if cb.name == "xe_float_cbuffer":
            floats = cb.byteSize // 16
    log(f"eid {d.eventId:6d} idx {d.numIndices:6d} vs {int(pipe.GetShader(rd.ShaderStage.Vertex))} float_consts {floats}")

ctl.Shutdown()
cap.Shutdown()
out.close()
os._exit(0)
