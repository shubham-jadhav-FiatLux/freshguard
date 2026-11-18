# Demo video tooling

`record.py` films live segments with headless Chromium (Playwright): the web UI (Ask and Paste), terminal replays of output captured from live runs (`t1_out.json`, `t2b.txt`), and the Bifrost dashboard (it logs in with `BIFROST_ADMIN_USER` / `BIFROST_ADMIN_PASSWORD` from `.env`). `assemble.sh` joins deck slides (`slides/*.png`, rendered from `docs/FreshGuard_Pitch.pdf`) and clips into one 1280x720 MP4.

```bash
python -m venv venv && venv/bin/pip install playwright && venv/bin/python -m playwright install chromium
venv/bin/python record.py ui_ask ui_paste term1 term2 dash   # wait ~60 s between live segments (Groq per-minute limit)
bash assemble.sh FreshGuard_demo.mp4
```
