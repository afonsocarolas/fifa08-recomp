# Run inside RenderDoc's Python: qrenderdoc.exe --python tools/rdoc_shader.py
# Job file tools/rdoc_job.json: {"capture": ..., "out": ..., "shader": <vs resource id number>}
# Writes the vertex shader's disassembly and the float constants (256 x float4)
# bound at its first draw.
import json
import os
import struct
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

draws = []


def walk(actions):
    for a in actions:
        if a.flags & rd.ActionFlags.Drawcall:
            draws.append(a)
        walk(a.children)


walk(ctl.GetRootActions())
want = int(job["shader"])
for d in draws:
    ctl.SetFrameEvent(d.eventId, False)
    pipe = ctl.GetPipelineState()
    if int(pipe.GetShader(rd.ShaderStage.Vertex)) != want:
        continue
    refl = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
    log(f"== draw eid {d.eventId} indices {d.numIndices}")
    targets = ctl.GetDisassemblyTargets(True)
    log(f"== disassembly targets: {list(targets)}")
    log(ctl.DisassembleShader(pipe.GetGraphicsPipelineObject(), refl, targets[0]))
    for i, cb in enumerate(refl.constantBlocks):
        if cb.name != "xe_float_cbuffer":
            continue
        bound = pipe.GetConstantBlock(rd.ShaderStage.Vertex, i, 0).descriptor
        data = ctl.GetBufferData(bound.resource, bound.byteOffset, 256 * 16)
        log("== float constants (c0..c255)")
        for c in range(len(data) // 16):
            x, y, z, w = struct.unpack_from("<4f", data, c * 16)
            log(f"c{c:3d} {x:12.5f} {y:12.5f} {z:12.5f} {w:12.5f}")
    break

ctl.Shutdown()
cap.Shutdown()
out.close()
os._exit(0)
