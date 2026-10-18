# GPT three-shot delivery (G4/R4.4)

One command processes an already downloaded, completed three-shot artifact:

```bash
python scripts/assemble_gpt_video_three.py /path/to/completed-clips --output-dir /path/to/new-delivery
```

No credentials, provider imports, API requests or generation. Input is report.json plus s01.mp4/s02.mp4/s03.mp4. Require completed status, three attempts, exact ordered shot IDs, receipt hashes, matching H264/AAC360x640 stream signatures and duration receipts. Missing/altered/incomplete input is rejected before creating output. Existing delivery folders are not overwritten. If assembly fails, rerun this offline command with a new output directory; never rerun generation.

Copies verified originals into a temporary concat folder, stream-copies video and native audio without cutting, time stretching, dubbing, music or subtitle fabrication. Runs ffprobe duration/stream checks and full FFmpeg decode. Output gpt-three-shot-preview.mp4 and delivery.json retain source report/clip hashes and run ID. Future successful three-shot workflow automatically runs this step and uploads the delivery subfolder. Existing successful generation is NOT rerun to test the change.

Actual existing Run39047208593/artifact12106182855 was assembled locally:15.060333s,360x640,H264/AAC, full decode passed; MP4 SHA256 f75251d60f49a1061b9384cca5f303057c57fed23b58a7a6cd91020320cbc101. New model calls0/new API feesUSD0. Original generation actual fee remains unknown.

This is a three-shot technical preview, not a60s completed episode, visual/Chinese-dialogue/subtitle acceptance or publication approval. Source receipt+hash checks do not authenticate supplier provenance. Appearance/animation quality is intentionally deferred per owner direction.

134 related local tests passed. Five new cases exercise real FFmpeg on synthetic media, including unchanged sources, no-overwrite, incomplete/reordered/missing/tampered input. The new workflow runs them after installing pinned FFmpeg. Real generated output was additionally checked separately as above. G4/R4.4 remains partial; remaining nine shots and full60–90s evaluation are not complete.
