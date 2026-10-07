// Image + video + audio references in one request. Name them in the prompt as @Image 1, @Video 1, @Audio 1.
import { Seedance25 } from "../seedance25.mjs";

const client = new Seedance25();
const job = await client.generate(
  "The girl in @Image 1 dances to the beat of @Audio 1, moving like the dancer in @Video 1",
  {
    duration: 10,
    resolution: "720p",
    reference_images: [{ url: "https://example.com/girl.png" }],
    reference_videos: [{ url: "https://example.com/dance.mp4" }],
    reference_audios: [{ url: "https://example.com/beat.mp3" }],
  },
  "dance.mp4",
);
console.log(job.usage); // billed_seconds = output seconds + reference video seconds
