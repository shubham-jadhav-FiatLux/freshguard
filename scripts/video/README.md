# Demo video tooling

`record.py` films live segments with headless Chromium (Playwright): the web UI (the question is typed into an empty box; an answer is pasted into an empty box), terminal replays of output captured from live runs (`t1_out.json`, `t2b.txt`), and the Bifrost dashboard (it logs in with `BIFROST_ADMIN_USER` / `BIFROST_ADMIN_PASSWORD` from `.env`). Scrolling is an eased `requestAnimationFrame` glide that parks each card above the caption. Every clip also logs its key presses and clicks.

`assemble.sh` joins deck slides (`slides/s-NN.png`, rendered from `docs/FreshGuard_Pitch.pdf` with `pdftoppm -png -scale-to-x 1280 -scale-to-y 720`) and clips into one 1280x720 MP4 at 25 fps (the capture rate). `calibrate.py` lines the logged key presses up with the frames where the text appears. `soundtrack.py` synthesises an instrumental bed plus keyboard and mouse clicks at those times; nothing is sampled. The mix is loudness-normalised to -16 LUFS.

```bash
python -m venv venv && venv/bin/pip install playwright numpy && venv/bin/python -m playwright install chromium
venv/bin/python record.py ui_ask term1 term2 ui_paste dash   # live segments need FreshGuard + Bifrost running
PY=venv/bin/python bash assemble.sh FreshGuard_demo.mp4
```
