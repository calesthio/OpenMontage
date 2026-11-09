"""motion_score.py: noise-robust motion gate (legacy 16:9 profile only).
Usage: python3 motion_score.py clip.mp4 [--cuts 12.0,31.5] [--scene-start S --scene-dur D]
Exit 0 = PASS, 1 = FAIL, 2 = NOT_CALIBRATED / INSUFFICIENT_DATA / ERROR (never PASS)."""
import json, subprocess, sys, argparse
import numpy as np
W, H, FPS = 320, 180, 2           # legacy calibration profile
STATIC_CUT, GATE_MEAN, MAX_STATIC_RUN_S = 1.0, 1.0, 4.0

def probe(path):
    o = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
        "stream=width,height","-of","json",path],capture_output=True,text=True)
    if o.returncode: raise RuntimeError("ffprobe failed: "+o.stderr[:200])
    s = json.loads(o.stdout)["streams"][0]; return int(s["width"]), int(s["height"])

def windows(path, ss=0.0, t=None):
    c = ["ffmpeg","-v","error","-ss",str(ss),"-i",path] + (["-t",str(t)] if t else [])
    c += ["-an","-vf",f"fps={FPS},scale={W}:{H},format=gray","-f","rawvideo","-"]
    p = subprocess.run(c, capture_output=True)
    if p.returncode: raise RuntimeError("ffmpeg failed: "+p.stderr.decode()[:200])
    n = len(p.stdout)//(W*H)
    if n < 3: return None, n
    f = np.frombuffer(p.stdout[:n*W*H], np.uint8).reshape(n,H,W).astype(np.float32)
    f = f.reshape(n, H//6, 6, W//8, 8).mean(axis=(2,4))          # 8x6 blocks kill grain/noise
    return np.abs(f[2:]-f[:-2]).mean(axis=(1,2)), n               # |frame - frame 1 s earlier|

def score(path, ss=0.0, dur=None, cuts=()):
    w, h = probe(path)
    if abs(w/h - 16/9) > 0.02:
        return {"verdict":"NOT_CALIBRATED","reason":f"aspect {w}x{h}"}
    if dur is not None and dur <= 4.0:
        return {"verdict":"NOT_APPLICABLE_SHORT","duration_s":dur}
    d, n = windows(path, ss, dur)
    if d is None: return {"verdict":"INSUFFICIENT_DATA","frames":n}
    t = ss + (np.arange(len(d))+2)/FPS                              # end time of each window
    keep = np.ones(len(d), bool)
    for c in cuts: keep &= ~((t-1.0-0.01 <= c) & (c <= t+0.01))     # drop windows that span a cut
    v = d[keep]
    if len(v) < 2: return {"verdict":"INSUFFICIENT_DATA","valid_windows":int(len(v))}
    run = best = 0
    for x in d[keep]:
        run = run+1 if x < STATIC_CUT else 0; best = max(best, run)
    st = {"mean":round(float(v.mean()),3),"p10":round(float(np.percentile(v,10)),3),
          "median":round(float(np.median(v)),3),"p90":round(float(np.percentile(v,90)),3),
          "share_below_0.35":round(float((v<0.35).mean()),3),
          "longest_static_run_s":best/FPS,"valid_windows":int(len(v)),
          "excluded_windows":int((~keep).sum()),"coverage":round(len(v)/len(d),3)}
    ok = st["mean"] >= GATE_MEAN and st["longest_static_run_s"] <= MAX_STATIC_RUN_S
    st["verdict"] = "PASS" if ok else "FAIL"; return st

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("path")
    a.add_argument("--cuts",default=""); a.add_argument("--scene-start",type=float,default=0.0)
    a.add_argument("--scene-dur",type=float,default=None); g = a.parse_args()
    cuts = [float(x) for x in g.cuts.split(",") if x]
    try: r = score(g.path, g.scene_start, g.scene_dur, cuts)
    except Exception as e: r = {"verdict":"ERROR","reason":str(e)}
    print(json.dumps(r)); sys.exit({"PASS":0,"FAIL":1}.get(r["verdict"],2))
