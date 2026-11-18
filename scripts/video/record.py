"""Records the FreshGuard demo segments with a real (headless) browser. Usage: record.py <segment> [...]"""
import asyncio, html, json, os, pathlib, sys
from playwright.async_api import async_playwright

S = pathlib.Path(__file__).parent
CLIPS = S / "clips"; CLIPS.mkdir(exist_ok=True)
VIEW = {"width": 1280, "height": 720}

CAPTION_JS = """(t) => { let d = document.getElementById('fg-cap');
  if (!d) { d = document.createElement('div'); d.id = 'fg-cap';
    Object.assign(d.style, {position:'fixed', left:'50%', bottom:'26px', transform:'translateX(-50%)', background:'#0A1A1F',
      color:'#EEF5F4', font:'500 18px/1.4 Inter, Segoe UI, sans-serif', padding:'12px 22px 12px 18px', borderRadius:'14px',
      zIndex: 99999, boxShadow:'0 12px 32px rgba(0,0,0,.35)', maxWidth:'1080px', textAlign:'left', display:'flex', gap:'12px',
      alignItems:'center', border:'1px solid #2A4950', transition:'opacity .3s'});
    document.body.appendChild(d); }
  d.innerHTML = '<span style="width:10px;height:10px;border-radius:50%;background:#2EE6A8;flex:none"></span><span>' + t + '</span>';
  d.querySelectorAll('b').forEach((x) => x.style.whiteSpace = 'nowrap'); }"""


async def caption(pg, text):
    await pg.evaluate(CAPTION_JS, text)


async def scroll(pg, total, steps=40, pause=45):
    for _ in range(steps):
        await pg.mouse.wheel(0, total / steps)
        await pg.wait_for_timeout(pause)


async def new_page(p, name):
    b = await p.chromium.launch()
    ctx = await b.new_context(viewport=VIEW, record_video_dir=str(CLIPS / name), record_video_size=VIEW)
    return b, ctx, await ctx.new_page()


async def finish(b, ctx, pg, name):
    v = pg.video
    await ctx.close(); await b.close()
    src = pathlib.Path(await v.path()); src.rename(CLIPS / f"{name}.webm")
    print("saved", CLIPS / f"{name}.webm")


async def ui_ask(p):
    b, ctx, pg = await new_page(p, "ui_ask")
    await pg.goto("http://localhost:8000/"); await pg.wait_for_timeout(1500)
    await caption(pg, "Live demo · ask an LLM a time-sensitive question")
    await pg.wait_for_timeout(3000)
    await pg.click("#go")
    await caption(pg, "The LLM answers via <b>Bifrost</b> → FreshGuard extracts claims, searches news + web with <b>Tavily</b>, judges the evidence")
    await pg.wait_for_selector("#reportCard:not(.hidden)", timeout=180000)
    await pg.wait_for_timeout(800)
    await caption(pg, "The model said Jensen Huang and Tim Cook. Both <b style='color:#FF5D6C'>expired</b>, so FreshGuard shows who leads now")
    await scroll(pg, 560, steps=50, pause=40)
    await pg.wait_for_timeout(4500)
    await caption(pg, "Every verdict cites dated sources, including NVIDIA's own newsroom")
    await scroll(pg, 420, steps=40, pause=40)
    await pg.wait_for_timeout(4500)
    await finish(b, ctx, pg, "ui_ask")


async def ui_paste(p):
    b, ctx, pg = await new_page(p, "ui_paste")
    await pg.goto("http://localhost:8000/"); await pg.wait_for_timeout(1200)
    await pg.click(".tab[data-mode=check]"); await pg.wait_for_timeout(500)
    await pg.click("#examples .chip:nth-child(2)")
    await caption(pg, "Or paste an answer from any AI. Here, streaming prices it learned before 2026")
    await pg.wait_for_timeout(3500)
    await pg.click("#go")
    await caption(pg, "Checking each price against this year's news…")
    await pg.wait_for_selector("#reportCard:not(.hidden)", timeout=180000)
    await pg.wait_for_timeout(800)
    await caption(pg, "Netflix and Spotify raised prices in 2026, so both claims are flagged with today's price")
    await scroll(pg, 520, steps=50, pause=40)
    await pg.wait_for_timeout(5000)
    await caption(pg, "Rate-limited model? Bifrost fails over to another model automatically (shown in the report header)")
    await pg.evaluate("window.scrollTo({top: document.getElementById('reportCard').offsetTop - 40, behavior: 'smooth'})")
    await pg.wait_for_timeout(4500)
    await finish(b, ctx, pg, "ui_paste")


TERM_HTML = """<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@500&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>body{margin:0;background:#EAF1EF;height:100vh;display:grid;place-items:center;font-family:Inter,sans-serif}
.t{width:1140px;height:560px;background:#071216;border-radius:14px;border:1px solid #2A4950;box-shadow:0 30px 60px -30px rgba(10,26,31,.6);overflow:hidden}
.bar{height:38px;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid #173239}
.dot{width:12px;height:12px;border-radius:50%}.title{margin-left:14px;color:#5F7A7F;font:12px 'JetBrains Mono',monospace}
pre{margin:0;padding:18px 22px;color:#EEF5F4;font:14.5px/1.55 'JetBrains Mono',monospace;white-space:pre-wrap;word-break:break-word}
.p{color:#2EE6A8}.c{color:#9B8CFF}.bad{color:#FF5D6C}.good{color:#2EE6A8}.dim{color:#93AAAE}.hdr{color:#FFC24B}</style></head>
<body><div class="t"><div class="bar"><span class="dot" style="background:#FF5D6C"></span><span class="dot" style="background:#FFC24B"></span><span class="dot" style="background:#2EE6A8"></span><span class="title">__TITLE__</span></div><pre id="o"></pre></div>
<script>const CMD=__CMD__, OUT=__OUT__; const o=document.getElementById('o');
function cls(l){ if(/✗|❌/.test(l)) return 'bad'; if(/✓|✅/.test(l)) return 'good'; if(/^\\s+(now|src):/.test(l)) return 'dim';
  if(/^x-freshguard/i.test(l)) return 'hdr'; if(/^━━/.test(l)) return 'c'; return ''; }
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
window.play=async()=>{ o.innerHTML='<span class="p">$ </span>'; for(const ch of CMD){ o.innerHTML+=esc(ch); await new Promise(r=>setTimeout(r,16)); }
  o.innerHTML+='\\n'; await new Promise(r=>setTimeout(r,900));
  for(const l of OUT){ o.innerHTML+='<span class="'+cls(l)+'">'+esc(l)+'</span>\\n'; await new Promise(r=>setTimeout(r,110)); } return true; };</script></body></html>"""


async def term(p, name, title, cmd, out, cap1, cap2, hold=7000):
    page_html = (TERM_HTML.replace("__TITLE__", html.escape(title)).replace("__CMD__", json.dumps(cmd))
                 .replace("__OUT__", json.dumps(out)))
    f = S / f"{name}.html"; f.write_text(page_html)
    b, ctx, pg = await new_page(p, name)
    await pg.goto(f.as_uri()); await pg.wait_for_timeout(1200)
    await caption(pg, cap1)
    await pg.evaluate("window.play()")
    await caption(pg, cap2)
    await pg.wait_for_timeout(hold)
    await finish(b, ctx, pg, name)


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


async def dash(p):
    b, ctx, pg = await new_page(p, "dash")
    await pg.goto("http://localhost:8080/login", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
    await pg.fill("input[type=text]", os.environ["BIFROST_ADMIN_USER"])
    await pg.fill("input[type=password]", os.environ["BIFROST_ADMIN_PASSWORD"])
    await pg.keyboard.press("Enter"); await pg.wait_for_timeout(2500)
    import time; t0 = time.time()
    await pg.goto("http://localhost:8080/workspace/logs", wait_until="domcontentloaded")
    try:
        await pg.get_by_text("Remind me later").first.wait_for(timeout=15000)
        await pg.get_by_text("Remind me later").first.click(); await pg.wait_for_timeout(500)
        await pg.get_by_text("In a week").first.click(); await pg.wait_for_timeout(800)
    except Exception as e:
        print("checklist not dismissed:", e)
    for path, cap in (("/workspace/mcp-logs", "Bifrost MCP logs: every <b>verify_freshness</b> call FreshGuard served"),
                      ("/workspace/logs", "Bifrost LLM logs: every model call routed, logged and failed over, with tokens and cost")):
        await pg.goto("http://localhost:8080" + path, wait_until="domcontentloaded")
        want = "verify_freshness" if "mcp" in path else "Total"
        try:
            await pg.get_by_text(want).first.wait_for(timeout=20000)
        except Exception:
            pass
        await pg.wait_for_timeout(1200)
        btn = pg.get_by_text("Remind me later")
        if await btn.count():
            await btn.first.click(); await pg.wait_for_timeout(500)
            week = pg.get_by_text("In a week")
            if await week.count(): await week.first.click(); await pg.wait_for_timeout(800)
        await caption(pg, cap)
        if "mcp" in path: (S / "dash_trim.txt").write_text(str(round(time.time() - t0 + 2.5 + 1.0 - 0.4, 1)))
        await pg.wait_for_timeout(6500)
    await finish(b, ctx, pg, "dash")


async def main(names):
    async with async_playwright() as p:
        for n in names:
            await globals()[n](p)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
