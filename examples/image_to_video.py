"""First frame -> video. The frame sets the aspect ratio, so send "adaptive"."""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")
from seedance25 import Seedance25

client = Seedance25()
frame = client.upload("first-frame.png", "image", "image/png")  # or any public HTTPS image URL
job = client.generate(
    "The camera pushes in slowly while leaves drift across the frame",
    "first-frame.mp4",
    duration=5,
    resolution="720p",
    aspect_ratio="adaptive",
    start_image={"url": frame},
)
print(job["usage"])
