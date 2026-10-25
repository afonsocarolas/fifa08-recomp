# Run inside RenderDoc's Python: qrenderdoc.exe --python tools/rdoc_vs_bindings.py
# Job file tools/rdoc_job.json: {"capture": ..., "out": ..., "shader": <vs resource id number>}
# At the first draw that uses the vertex shader, lists the textures and samplers the
# vertex stage actually accessed (format, size, filter, addressing), and dumps the
# first rows of each small texture as half floats. With "save": <path>, also writes
# the raw texels of each texture up to 256x256 to that file.
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
textures = {t.resourceId: t for t in ctl.GetTextures()}
want = int(job["shader"])
for d in draws:
    ctl.SetFrameEvent(d.eventId, False)
    pipe = ctl.GetPipelineState()
    if int(pipe.GetShader(rd.ShaderStage.Vertex)) != want:
        continue
    log(f"== draw eid {d.eventId} indices {d.numIndices}")
    for used in pipe.GetReadOnlyResources(rd.ShaderStage.Vertex, True):
        desc = used.descriptor
        t = textures.get(desc.resource)
        if not t:
            log(f"  srv {used.access.index} buffer/other {int(desc.resource)}")
            continue
        log(f"  srv {used.access.index} tex {int(desc.resource)} fmt {desc.format.Name()} "
            f"{t.width}x{t.height}x{t.depth} mips {t.mips} type {t.type}")
        if job.get("save") and t.width * t.height <= 65536:
            data = ctl.GetTextureData(desc.resource, rd.Subresource(0, 0, 0))
            open(job["save"], "wb").write(bytes(data))
            log(f"    saved {len(data)} bytes to {job['save']}")
        if t.width * t.height <= 4096:
            sub = rd.Subresource(0, 0, 0)
            data = ctl.GetTextureData(desc.resource, sub)
            log(f"    {len(data)} bytes; first texels as u16 hex / half:")
            n = min(len(data) // 2, 96)
            vals = struct.unpack_from(f"<{n}H", data)
            halves = struct.unpack_from(f"<{n}e", data)
            for row in range(0, n, 8):
                log("    " + " ".join(f"{v:04x}" for v in vals[row:row + 8]) + "   " +
                    " ".join(f"{h:8.4f}" for h in halves[row:row + 8]))
    for used in pipe.GetSamplers(rd.ShaderStage.Vertex, True):
        s = used.sampler
        log(f"  sampler {used.access.index} filter {s.filter.minify}/{s.filter.magnify}/{s.filter.mip} "
            f"func {s.filter.filter} address {s.addressU}/{s.addressV}")
    break

ctl.Shutdown()
cap.Shutdown()
out.close()
os._exit(0)
