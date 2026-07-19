import sys, os
sys.path.insert(0, os.getcwd())
from tools.audio.pixabay_music import PixabayMusic
t = PixabayMusic()
out = "projects/home-concepts/assets/music/warm_uplifting.mp3"
res = t.execute({"query":"warm uplifting acoustic corporate","min_duration":15,"max_duration":60,"output_path":out})
print("success:", res.success)
print("error:", getattr(res,"error",None))
print("data:", getattr(res,"data",None))
