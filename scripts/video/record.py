"""Records the FreshGuard demo segments with a real (headless) browser. Usage: record.py <segment> [...]

Every clip also gets clips/<name>.events.json: wall-clock times of key presses and clicks plus the
page-open / close times, so soundtrack.py can place keyboard sounds exactly on the typing.
"""
import asyncio, html, json, pathlib, random, sys, time, os
from playwright.async_api import async_playwright

S = pathlib.Path(__file__).parent
CLIPS = S / "clips"; CLIPS.mkdir(exist_ok=True)
VIEW = {"width": 1280, "height": 720}
CAP_SAFE = 720 - 120          # content we want readable must end above the caption
random.seed(7)

CAPTION_JS = """([t, top]) => { let d = document.getElementById('fg-cap');
  if (!d) { d = document.createElement('div'); d.id = 'fg-cap';
    Object.assign(d.style, {position:'fixed', left:'50%', bottom:'22px', transform:'translateX(-50%)', background:'#0A1A1F',
      color:'#EEF5F4', font:'500 17px/1.4 Inter, Segoe UI, sans-serif', padding:'11px 22px 11px 18px', borderRadius:'14px',
      zIndex: 99999, boxShadow:'0 12px 32px rgba(0,0,0,.35)', maxWidth:'1100px', textAlign:'left', display:'flex', gap:'12px',
      alignItems:'center', border:'1px solid #2A4950', whiteSpace:'nowrap'});
    document.body.appendChild(d);
    if (top) Object.assign(d.style, {bottom:'auto', top:'10px'});
    else document.body.style.paddingBottom = '170px'; }   // lets the last card scroll clear of the caption
  d.innerHTML = '<span style="width:10px;height:10px;border-radius:50%;background:#2EE6A8;flex:none"></span><span>' + t + '</span>'; }"""

# Eased scroll driven by requestAnimationFrame: one smooth glide instead of stepped wheel events.
GLIDE_JS = """([to, ms]) => new Promise((done) => {
  const from = scrollY, max = document.documentElement.scrollHeight - innerHeight;
  to = Math.max(0, Math.min(max, to)); const t0 = performance.now();
  const ease = (x) => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const step = (now) => { const k = Math.min(1, (now - t0) / ms); scrollTo(0, from + (to - from) * ease(k));
    k < 1 ? requestAnimationFrame(step) : done(); };
  requestAnimationFrame(step); })"""


class Rec:
    def __init__(self, name):
        self.name, self.events = name, []

    def ev(self, kind):
        self.events.append([time.time(), kind])


async def caption(pg, text, top=False):
    await pg.evaluate(CAPTION_JS, [text, top])


async def glide(pg, to, ms=1800):
    await pg.evaluate(GLIDE_JS, [to, ms])


async def top_of(pg, sel, idx=0):
    return await pg.evaluate("([s,i]) => document.querySelectorAll(s)[i].getBoundingClientRect().top + scrollY", [sel, idx])


async def bottom_of(pg, sel, idx=0):
    return await pg.evaluate("([s,i]) => document.querySelectorAll(s)[i].getBoundingClientRect().bottom + scrollY", [sel, idx])


async def human_type(pg, rec, text):
    for ch in text:
        await pg.keyboard.type(ch)
        rec.ev("space" if ch == " " else "key")
        await pg.wait_for_timeout(random.randint(55, 125) + (90 if ch in " ,?" else 0))


async def click(pg, rec, sel):
    await pg.hover(sel); await pg.wait_for_timeout(250)
    rec.ev("click"); await pg.click(sel)


async def new_page(p, name, view=VIEW):
    b = await p.chromium.launch()
    ctx = await b.new_context(viewport=view, record_video_dir=str(CLIPS / name), record_video_size=VIEW)
    pg = await ctx.new_page()
    rec = Rec(name); rec.t_open = time.time()
    return b, ctx, pg, rec


async def finish(b, ctx, pg, rec):
    v = pg.video
    rec.t_close = time.time()
    await ctx.close(); await b.close()
    src = pathlib.Path(await v.path()); src.rename(CLIPS / f"{rec.name}.webm")
    (CLIPS / f"{rec.name}.events.json").write_text(json.dumps(
        {"t_open": rec.t_open, "t_close": rec.t_close, "events": rec.events}))
    print("saved", CLIPS / f"{rec.name}.webm", len(rec.events), "sound events")


async def read_report(pg, rec, first_cap, claim_caps):
    """Glide through the answer and each claim, parking every card fully above the caption."""
    await pg.wait_for_selector("#reportCard:not(.hidden)", timeout=180000)
    await pg.wait_for_timeout(900)
    start = await top_of(pg, "#answerCard:not(.hidden), #reportCard") - 20
    await caption(pg, first_cap)
    await glide(pg, start, 1600); await pg.wait_for_timeout(3800)
    n = await pg.evaluate("document.querySelectorAll('#claims .claim').length")
    for i in range(n):
        t, btm = await top_of(pg, "#claims .claim", i), await bottom_of(pg, "#claims .claim", i)
        target = max(start, min(t - 20, btm - CAP_SAFE))   # whole card visible, above the caption
        if i < len(claim_caps) and claim_caps[i]:
            await caption(pg, claim_caps[i])
        await glide(pg, target, 1700); await pg.wait_for_timeout(5200)


async def ui_ask(p):
    b, ctx, pg, rec = await new_page(p, "ui_ask")
    await pg.goto("http://localhost:8000/"); await pg.wait_for_timeout(1200)
    await caption(pg, "Live demo · ask an LLM a time-sensitive question")
    await pg.wait_for_timeout(1200)
    rec.ev("click"); await pg.click("#input"); await pg.wait_for_timeout(500)
    await human_type(pg, rec, "Who is the CEO of NVIDIA?")
    await pg.wait_for_timeout(700)
    await click(pg, rec, "#go")
    await caption(pg, "The LLM answers via <b>Bifrost</b> → FreshGuard extracts claims, searches news + web with <b>Tavily</b>, judges the evidence")
    await read_report(pg, rec,
        "The model still says Jensen Huang: its training data predates the change",
        ["FreshGuard flags it <b style='color:#FF5D6C'>expired</b> and shows who leads NVIDIA now, with dated sources"])
    await finish(b, ctx, pg, rec)


PASTE = ("Netflix's Standard ad-free plan costs $17.99 per month in the US, "
         "and Spotify Premium Individual costs $11.99 per month.")


async def ui_paste(p):
    b, ctx, pg, rec = await new_page(p, "ui_paste")
    await pg.goto("http://localhost:8000/"); await pg.wait_for_timeout(1200)
    await caption(pg, "Or check an answer you got from any AI chatbot")
    await pg.wait_for_timeout(800)
    await click(pg, rec, ".tab[data-mode=check]"); await pg.wait_for_timeout(900)
    rec.ev("click"); await pg.click("#input"); await pg.wait_for_timeout(700)
    await caption(pg, "Paste it in (<b>Ctrl+V</b>). Here, streaming prices a model learned before 2026")
    await pg.wait_for_timeout(500)
    rec.ev("key"); await pg.wait_for_timeout(110); rec.ev("key")          # Ctrl, V
    await pg.keyboard.insert_text(PASTE)
    await pg.wait_for_timeout(2600)
    await click(pg, rec, "#go")
    await caption(pg, "Checking each price against this year's news…")
    await read_report(pg, rec,
        "Netflix and Spotify both raised prices in 2026",
        ["Each stale price is flagged with today's price and its source", None])
    await caption(pg, "Every model call goes through <b>Bifrost</b>: the report header shows the model and tokens used")
    await glide(pg, await top_of(pg, "#reportCard") - 20, 1500); await pg.wait_for_timeout(4200)
    await finish(b, ctx, pg, rec)


TERM_HTML = """<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@500&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>body{margin:0;background:#EAF1EF;height:100vh;display:flex;justify-content:center;align-items:flex-start;font-family:Inter,sans-serif}
.t{margin-top:26px;width:1160px;height:560px;background:#071216;border-radius:14px;border:1px solid #2A4950;box-shadow:0 30px 60px -30px rgba(10,26,31,.6);overflow:hidden}
.bar{height:38px;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid #173239}
.dot{width:12px;height:12px;border-radius:50%}.title{margin-left:14px;color:#5F7A7F;font:12px 'JetBrains Mono',monospace}
pre{margin:0;padding:16px 22px;color:#EEF5F4;font:14px/1.5 'JetBrains Mono',monospace;white-space:pre-wrap;word-break:break-word}
.p{color:#2EE6A8}.c{color:#9B8CFF}.bad{color:#FF5D6C}.good{color:#2EE6A8}.dim{color:#93AAAE}.hdr{color:#FFC24B}</style></head>
<body><div class="t"><div class="bar"><span class="dot" style="background:#FF5D6C"></span><span class="dot" style="background:#FFC24B"></span><span class="dot" style="background:#2EE6A8"></span><span class="title">__TITLE__</span></div><pre id="o"></pre></div>
<script>const CMD=__CMD__, OUT=__OUT__; const o=document.getElementById('o');
function cls(l){ if(/✗|❌/.test(l)) return 'bad'; if(/✓|✅/.test(l)) return 'good'; if(/^\\s+(now|src):/.test(l)) return 'dim';
  if(/^x-freshguard/i.test(l)) return 'hdr'; if(/^━━/.test(l)) return 'c'; return ''; }
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const wait=(ms)=>new Promise(r=>setTimeout(r,ms));
window.play=async()=>{ const keys=[]; o.innerHTML='<span class="p">$ </span>';
  for(const ch of CMD){ o.innerHTML+=esc(ch); if(ch!=='\\n') keys.push([Date.now(), ch===' '?'space':'key']);
    await wait(30+Math.random()*38+(ch===' '?40:0)); }
  await wait(450); keys.push([Date.now(),'enter']); o.innerHTML+='\\n'; await wait(900);
  for(const l of OUT){ o.innerHTML+='<span class="'+cls(l)+'">'+esc(l)+'</span>\\n'; await wait(110); } return keys; };</script></body></html>"""


async def term(p, name, title, cmd, out, cap1, cap2, hold=7000):
    page_html = (TERM_HTML.replace("__TITLE__", html.escape(title)).replace("__CMD__", json.dumps(cmd))
                 .replace("__OUT__", json.dumps(out)))
    f = S / f"{name}.html"; f.write_text(page_html)
    b, ctx, pg, rec = await new_page(p, name)
    await pg.goto(f.as_uri()); await pg.wait_for_timeout(1200)
    await caption(pg, cap1)
    keys = await pg.evaluate("window.play()")
    rec.events += [[t / 1000, k] for t, k in keys]
    await caption(pg, cap2)
    await pg.wait_for_timeout(hold)
    await finish(b, ctx, pg, rec)


async def term1(p):
    out = json.loads((S / "t1_out.json").read_text())
    cmd = ('curl -i localhost:8000/v1/chat/completions \\\n    -d \'{"model": "groq/qwen/qwen3.8-27b", "messages": [{"role": "user",\n'
           '         "content": "What is the newest Ubuntu LTS and the latest Java version?"}]}\'')
    await term(p, "term1", "drop-in endpoint · output captured from a live run", cmd, out,
               "Drop-in for any OpenAI-compatible app: just change the base URL",
               "Same completion back, plus a freshness report and an <b>X-FreshGuard-Score</b> header")


async def term2(p):
    lines = (S / "t2b.txt").read_text().rstrip("\n").split("\n")
    cmd = './scripts/demo_agent_mode.sh "Who won the most recent FIFA World Cup, and who is the current CEO of Apple?"'
    await term(p, "term2", "Bifrost MCP gateway · output captured from a live run", cmd, lines,
               "FreshGuard is also an <b>MCP tool</b> inside the Bifrost gateway",
               "Any model or agent behind Bifrost can call <b>freshguard-verify_freshness</b>", hold=8000)


async def dismiss_checklist(pg):
    btn = pg.get_by_text("Remind me later")
    if await btn.count():
        await btn.first.click(); await pg.wait_for_timeout(500)
        week = pg.get_by_text("In a week")
        if await week.count(): await week.first.click(); await pg.wait_for_timeout(800)


async def dash(p):
    # Larger viewport scaled into the 720p video, so the log tables fit; caption sits in the empty top bar.
    b, ctx, pg, rec = await new_page(p, "dash", {"width": 1600, "height": 900})
    await pg.goto("http://localhost:8080/login", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
    await pg.fill("input[type=text]", os.environ["BIFROST_ADMIN_USER"])
    await pg.fill("input[type=password]", os.environ["BIFROST_ADMIN_PASSWORD"])
    await pg.keyboard.press("Enter"); await pg.wait_for_timeout(2500)
    await pg.goto("http://localhost:8080/workspace/logs", wait_until="domcontentloaded")
    try:
        await pg.get_by_text("Remind me later").first.wait_for(timeout=15000)
        await dismiss_checklist(pg)
    except Exception as e:
        print("checklist not dismissed:", e)
    for path, cap in (("/workspace/mcp-logs", "Bifrost MCP logs: every <b>verify_freshness</b> call FreshGuard served"),
                      ("/workspace/logs", "Bifrost LLM logs: every model call routed and logged, with tokens, latency and cost")):
        await pg.goto("http://localhost:8080" + path, wait_until="domcontentloaded")
        try:
            await pg.get_by_text("verify_freshness" if "mcp" in path else "Total").first.wait_for(timeout=20000)
        except Exception:
            pass
        await pg.wait_for_timeout(1200)
        await dismiss_checklist(pg)
        await caption(pg, cap, top=True)
        if "mcp" in path:   # everything before this point (login, popups) is trimmed from the final video
            (S / "dash_trim.txt").write_text(str(round(time.time() - rec.t_open - 0.4, 1)))
        await pg.wait_for_timeout(6500)
    await finish(b, ctx, pg, rec)


async def main(names):
    async with async_playwright() as p:
        for n in names:
            await globals()[n](p)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
