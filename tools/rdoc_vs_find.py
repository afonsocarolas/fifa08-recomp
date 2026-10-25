# Run inside RenderDoc's Python: qrenderdoc.exe --python tools/rdoc_vs_find.py
# Job file tools/rdoc_job.json: {"capture": ..., "out": <summary path>, "dir": <folder for disassemblies>}
# Lists every vertex shader in the capture with how many draws use it and how many
# half-float unpacks (f16tof32) and raw fetches it does; shaders that unpack half
# floats or write memory (memexport, store_raw) are written to "dir" as vs<id>.txt.
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

draws = []


def walk(actions):
    for a in actions:
        if a.flags & rd.ActionFlags.Drawcall:
            draws.append(a)
        walk(a.children)


walk(ctl.GetRootActions())
shaders = {}
for d in draws:
    ctl.SetFrameEvent(d.eventId, False)
    pipe = ctl.GetPipelineState()
    vs = int(pipe.GetShader(rd.ShaderStage.Vertex))
    if vs not in shaders:
        refl = pipe.GetShaderReflection(rd.ShaderStage.Vertex)
        if not refl:
            continue
        targets = ctl.GetDisassemblyTargets(True)
        text = ctl.DisassembleShader(pipe.GetGraphicsPipelineObject(), refl, targets[0])
        shaders[vs] = {"draws": [], "indices": 0, "f16": text.count("f16tof32"), "ld_raw": text.count("ld_raw"),
                       "lines": text.count("\n"), "store": text.count("store_raw")}
        if shaders[vs]["f16"] or shaders[vs]["store"]:
            os.makedirs(job["dir"], exist_ok=True)
            open(os.path.join(job["dir"], f"vs{vs}.txt"), "w").write(f"first draw eid {d.eventId}\n" + text)
    shaders[vs]["draws"].append(d.eventId)
    shaders[vs]["indices"] += d.numIndices

log(f"{len(draws)} draws, {len(shaders)} vertex shaders")
for vs, s in sorted(shaders.items(), key=lambda kv: (-kv[1]["store"], -kv[1]["f16"])):
    log(f"vs {vs:5d}  draws {len(s['draws']):4d}  indices {s['indices']:7d}  f16tof32 {s['f16']:3d}  "
        f"ld_raw {s['ld_raw']:3d}  store_raw {s['store']:3d}  lines {s['lines']:5d}  first eid {s['draws'][0]}")

ctl.Shutdown()
cap.Shutdown()
out.close()
os._exit(0)
