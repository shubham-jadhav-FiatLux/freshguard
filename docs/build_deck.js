const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fi = require("react-icons/fi");
const SKILL = "/home/shubh/.claude/skills/synced/f36f543f-45cc-42c9-b04c-d0773730641c_69dafcfb-a736-4d6c-af46-a78c7feaf184/pptx";
const { applyTheme } = require(SKILL + "/scripts/apply_theme.js");
const OUT = process.argv[2];

// ---------- palette: "facts have expiry dates" ----------
const K = {
  bg: "0A1A1F", surf: "11262C", surf2: "173239", line: "2A4950", text: "EEF5F4", muted: "93AAAE", dim: "5F7A7F",
  mint: "2EE6A8", coral: "FF5D6C", amber: "FFC24B", violet: "9B8CFF", cyan: "4CC9F0", gray: "B9C6C8",
  mintD: "123D33", coralD: "3D1A20", amberD: "3B3016", violetD: "25224A", cyanD: "12354A",
};
const THEME = { name: "FreshGuard Dark", headFontFace: "Arial", bodyFontFace: "Calibri",
  colors: { dk1: K.bg, lt1: K.text, dk2: K.surf, lt2: K.muted, accent1: K.mint, accent2: K.coral, accent3: K.amber,
    accent4: K.violet, accent5: K.cyan, accent6: K.gray, hlink: K.cyan, folHlink: K.muted } };

const W = 13.333, H = 7.5;

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
async function glowBg(spots) { // dark background with soft radial glows (gradients aren't native in pptxgenjs)
  const g = spots.map((s, i) => `<radialGradient id="g${i}" cx="${s.x}" cy="${s.y}" r="${s.r}"><stop offset="0" stop-color="#${s.c}" stop-opacity="${s.o}"/><stop offset="1" stop-color="#${s.c}" stop-opacity="0"/></radialGradient>`).join("");
  const rects = spots.map((_, i) => `<rect width="1600" height="900" fill="url(#g${i})"/>`).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><defs>${g}</defs><rect width="1600" height="900" fill="#${K.bg}"/>${rects}</svg>`;
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "FreshGuard: facts expire";
  const C = pres.SchemeColor;

  const BG_HERO = await glowBg([{ x: 0.85, y: 0.2, r: 0.55, c: K.mint, o: 0.22 }, { x: 0.1, y: 1.0, r: 0.6, c: K.violet, o: 0.16 }]);
  const BG_CONTENT = await glowBg([{ x: 1.0, y: 0.0, r: 0.45, c: K.mint, o: 0.08 }]);

  pres.defineSlideMaster({ title: "HERO", background: { data: BG_HERO },
    objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 8.6, h: 2.0, fontSize: 60, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } }] });
  pres.defineSlideMaster({ title: "CONTENT", background: { data: BG_CONTENT },
    objects: [
      { placeholder: { options: { name: "kicker", type: "body", x: 0.7, y: 0.45, w: 9, h: 0.35, fontSize: 13, bold: true, color: C.accent1, charSpacing: 3, margin: 0, valign: "middle" }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 0.82, w: 11.9, h: 0.85, fontSize: 34, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: "FreshGuard  ·  Shubham Jadhav, IIT Madras  ·  Geek Room Global AI Hackathon 2026", options: { x: 0.7, y: 7.0, w: 10, h: 0.3, fontSize: 10, color: K.dim, margin: 0 } } },
    ],
    slideNumber: { x: 12.1, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: K.dim, align: "right" } });

  const I = {};
  for (const [k, comp, col] of [["shield", fi.FiShield, K.mint], ["shieldDark", fi.FiShield, K.bg], ["search", fi.FiSearch, K.bg], ["globe", fi.FiGlobe, K.bg],
    ["scale", fi.FiCheckCircle, K.bg], ["gauge", fi.FiActivity, K.bg], ["cpu", fi.FiCpu, K.bg], ["plug", fi.FiZap, K.bg],
    ["code", fi.FiCode, K.bg], ["git", fi.FiGitBranch, K.bg], ["alert", fi.FiAlertTriangle, K.coral], ["clock", fi.FiClock, K.coral],
    ["users", fi.FiUsers, K.bg], ["trend", fi.FiTrendingUp, K.bg], ["layers", fi.FiLayers, K.bg], ["refresh", fi.FiRefreshCw, K.bg],
    ["lock", fi.FiLock, K.bg], ["terminal", fi.FiTerminal, K.mint]]) I[k] = await icon(comp, col);

  let n = 0; const id = (p) => `${p}-${++n}`;
  const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, color: K.text, fontSize: 15, valign: "top", objectName: id("text"), ...o });
  const box = (s, x, y, w, h, fill, o = {}) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r ?? 0.14,
    fill: { color: fill, transparency: o.t ?? 0 }, line: { color: o.line ?? fill, width: o.lw ?? 1, dashType: o.dash }, objectName: id("box") });
  const pill = (s, x, y, label, fg, bg, w) => { const ww = w ?? (0.22 + label.length * 0.098);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: ww, h: 0.32, rectRadius: 0.16, fill: { color: bg }, line: { color: fg, width: 1 }, objectName: id("pill") });
    T(s, label, { x, y, w: ww, h: 0.32, fontSize: 11, bold: true, color: fg, align: "center", valign: "middle", charSpacing: 1 }); return ww; };
  const disc = (s, img, x, y, d, fill) => { s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: id("disc") });
    s.addImage({ data: img, x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, objectName: id("icon"), altText: "icon" }); };
  const arrow = (s, x1, y1, x2, y2, color, o = {}) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipH: x2 < x1, flipV: y2 < y1, line: { color, width: o.w ?? 1.5, dashType: o.dash, endArrowType: o.noHead ? undefined : "triangle", beginArrowType: o.both ? "triangle" : undefined }, objectName: id("arrow") });
  const stamp = (s, x, y, text, color, rot = -8) => { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.75, h: 0.5, rectRadius: 0.06, rotate: rot, fill: { color: K.bg, transparency: 100 }, line: { color, width: 2.25 }, objectName: id("stamp") });
    s.addText(text, { isTextBox: true, x, y, w: 1.75, h: 0.5, rotate: rot, fontSize: 15, bold: true, color, align: "center", valign: "middle", charSpacing: 3, margin: 0, objectName: id("stamp text") }); };
  const content = (sec, kicker, title) => { const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec }); s.addText(kicker, { placeholder: "kicker" }); s.addText(title, { placeholder: "title" }); return s; };

  // ===== 1. HERO =====
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "HERO", sectionTitle: "Opening" });
  T(s, "FRESHGUARD", { x: 0.8, y: 1.55, w: 6, h: 0.45, fontSize: 18, bold: true, color: K.mint, charSpacing: 6 });
  s.addText("Facts expire.\nWe check the date.", { placeholder: "title" });
  T(s, "A live freshness check for every LLM answer: built into the Bifrost AI gateway, verified on the open web with Tavily.", { x: 0.8, y: 4.4, w: 7.4, h: 0.9, fontSize: 18, color: K.muted });
  T(s, [{ text: "Shubham Jadhav", options: { fontFace: "Cambria", fontSize: 24, bold: true, color: K.amber, breakLine: true } }, { text: "Department of Computer Science and Engineering, IIT Madras", options: { fontFace: "Calibri", fontSize: 14, color: K.muted } }], { x: 0.8, y: 6.2, w: 9, h: 0.85, valign: "middle" });
  let px = 0.8; px += pill(s, px, 5.65, "BIFROST · EXTEND THE GATEWAY", K.violet, K.violetD) + 0.15; pill(s, px, 5.65, "TAVILY · STALE-ANSWER DETECTOR", K.cyan, K.cyanD);
  // hero visual: a "fact label" card with expiry stamp
  box(s, 9.0, 1.7, 3.6, 3.9, K.surf, { line: K.line });
  T(s, "LLM ANSWER · CLAIM", { x: 9.3, y: 1.95, w: 3, h: 0.3, fontSize: 11, bold: true, color: K.dim, charSpacing: 2 });
  T(s, "“The latest stable Python is 3.12.”", { x: 9.3, y: 2.3, w: 3.05, h: 0.9, fontSize: 17, bold: true });
  T(s, "Best before: model training cutoff", { x: 9.3, y: 3.2, w: 3.1, h: 0.3, fontSize: 12, color: K.muted, italic: true });
  stamp(s, 10.55, 3.55, "EXPIRED", K.coral);
  s.addShape(pres.shapes.LINE, { x: 9.3, y: 4.35, w: 3.0, h: 0, line: { color: K.line, width: 1 }, objectName: id("rule") });
  T(s, [{ text: "NOW  ", options: { bold: true, color: K.mint } }, { text: "Python 3.15.2 (Oct 2026)", options: { color: K.text } }], { x: 9.3, y: 4.5, w: 3.1, h: 0.35, fontSize: 14 });
  T(s, "↗ python.org · wikipedia.org", { x: 9.3, y: 4.9, w: 3.1, h: 0.3, fontSize: 11, color: K.cyan });
  s.addNotes("FreshGuard catches facts in AI answers that have quietly gone out of date, at the gateway, with live sources.");

  // ===== 2. PROBLEM =====
  pres.addSection({ title: "Problem" });
  s = content("Problem", "01 · THE PROBLEM", "LLMs serve expired facts, with full confidence");
  T(s, "A model's knowledge freezes at its training cutoff, but prices, versions, laws and leaders keep changing. The answer still sounds certain, and users can't tell which sentence went stale.", { x: 0.7, y: 1.85, w: 11.9, h: 0.75, fontSize: 17, color: K.muted });
  const probs = [["VERSION", "“Latest stable Python is 3.12”", "Python 3.15.2 · Oct 2026"], ["PRODUCT", "“Newest iPhone is the 15 Pro Max”", "iPhone 18 Pro lineup · Sep 2026"], ["LEADERSHIP", "“NVIDIA's CEO is Jensen Huang”", "Colette Kress (interim) · Nov 12"]];
  probs.forEach(([cat, claim, now], i) => {
    const x = 0.7 + i * 4.05;
    box(s, x, 2.95, 3.75, 3.45, K.surf, { line: K.line });
    pill(s, x + 0.3, 3.25, cat, K.amber, K.amberD);
    T(s, claim, { x: x + 0.3, y: 3.8, w: 3.15, h: 1.0, fontSize: 19, bold: true });
    stamp(s, x + 1.75, 4.75, "EXPIRED", K.coral, -6);
    T(s, [{ text: "NOW  ", options: { bold: true, color: K.mint } }, { text: now, options: { color: K.text } }], { x: x + 0.3, y: 5.65, w: 3.2, h: 0.4, fontSize: 14 });
  });
  s.addNotes("Real answers produced by current models in our testing (Groq-hosted Qwen / gpt-oss).");

  // ===== 3. SOLUTION statement =====
  pres.addSection({ title: "Solution" });
  s = content("Solution", "02 · THE IDEA", "Check freshness where every answer already flows");
  // left: raw answer, middle: freshguard, right: annotated answer
  box(s, 0.7, 2.2, 3.6, 3.9, K.surf, { line: K.line });
  T(s, "ANSWER IN", { x: 1.0, y: 2.45, w: 3, h: 0.3, fontSize: 11, bold: true, color: K.dim, charSpacing: 2 });
  ["Latest stable Python is 3.12", "Newest iPhone is 15 Pro Max", "15 Pro Max starts at $1,199"].forEach((t, i) => {
    const cy = 3.06 + i * 0.85;  // same row centres as the ANSWER OUT pills
    s.addShape(pres.shapes.OVAL, { x: 1.0, y: cy - 0.16, w: 0.32, h: 0.32, fill: { color: K.surf2 }, line: { color: K.line, width: 1 }, objectName: id("num") });
    T(s, String(i + 1), { x: 1.0, y: cy - 0.16, w: 0.32, h: 0.32, fontSize: 11, bold: true, color: K.muted, align: "center", valign: "middle" });
    T(s, `“${t}”`, { x: 1.45, y: cy - 0.3, w: 2.7, h: 0.6, fontSize: 15, valign: "middle" });
  });
  T(s, "3 time-sensitive claims in one answer", { x: 1.0, y: 5.45, w: 3.2, h: 0.35, fontSize: 12, color: K.violet });
  arrow(s, 4.4, 4.15, 5.15, 4.15, K.mint, { w: 2.5 });
  s.addShape(pres.shapes.OVAL, { x: 5.25, y: 2.95, w: 2.4, h: 2.4, fill: { color: K.mintD }, line: { color: K.mint, width: 2 }, objectName: id("core") });
  s.addImage({ data: I.shield, x: 6.05, y: 3.25, w: 0.8, h: 0.8, objectName: id("shield"), altText: "FreshGuard" });
  T(s, "FreshGuard", { x: 5.25, y: 4.1, w: 2.4, h: 0.4, fontSize: 18, bold: true, align: "center" });
  T(s, "extract · verify · score", { x: 5.25, y: 4.5, w: 2.4, h: 0.3, fontSize: 12, color: K.mint, align: "center" });
  arrow(s, 7.75, 4.15, 8.5, 4.15, K.mint, { w: 2.5 });
  box(s, 8.6, 2.2, 4.0, 3.9, K.surf, { line: K.line });
  T(s, "ANSWER OUT · FRESHNESS 34/100", { x: 8.9, y: 2.45, w: 3.6, h: 0.3, fontSize: 11, bold: true, color: K.dim, charSpacing: 2 });
  [["STALE", K.coral, K.coralD, "Python 3.12 → 3.15.2"], ["STALE", K.coral, K.coralD, "15 Pro Max → 18 Pro lineup"], ["FRESH", K.mint, K.mintD, "$1,199 starting price ✓"]].forEach(([l, fg, bg, t], i) => {
    const y = 2.9 + i * 0.85; pill(s, 8.9, y, l, fg, bg, 0.95); T(s, t, { x: 10.0, y: y - 0.02, w: 2.5, h: 0.4, fontSize: 15, valign: "middle" }); });
  T(s, "+ current fact and source URL for every claim", { x: 8.9, y: 5.45, w: 3.6, h: 0.35, fontSize: 12, color: K.cyan });
  T(s, "No app changes needed. Any model behind Bifrost gets the check.", { x: 0.7, y: 6.35, w: 11.9, h: 0.4, fontSize: 15, color: K.muted, align: "center" });

  // ===== 4. PIPELINE =====
  s = content("Solution", "03 · HOW IT WORKS", "Four steps, ~7 seconds, a source for every claim");
  const steps = [[I.search, K.violet, "Extract", "LLM via Bifrost · JSON mode", "Pulls only time-sensitive claims (prices, versions, laws, leaders, “latest”), each with a category, a volatility level and a search query. Timeless facts are skipped."],
    [I.globe, K.cyan, "Search", "Tavily · news (30 days) + web", "Per claim, in parallel: a news search for recent CHANGES plus a general web search. News is ranked first, so a resignation 3 days ago beats a stale profile page."],
    [I.scale, K.violet, "Judge", "LLM via Bifrost · evidence-only", "Rules current / outdated / unverified on the evidence only. Recent dated news of a change overrides older pages; weak evidence means unverified, not a guess."],
    [I.gauge, K.mint, "Score", "deterministic · 0–100", "Converts verdict + confidence + volatility into a freshness score and label, and attaches the current fact and the sources it relied on."]];
  steps.forEach(([img, col, h, sub, body], i) => {
    const x = 0.7 + i * 3.08;
    box(s, x, 2.0, 2.85, 4.6, K.surf, { line: K.line });
    disc(s, img, x + 0.3, 2.3, 0.85, col);
    T(s, `0${i + 1}`, { x: x + 1.95, y: 2.3, w: 0.65, h: 0.5, fontSize: 24, bold: true, color: K.line, align: "right" });
    T(s, h, { x: x + 0.3, y: 3.35, w: 2.4, h: 0.5, fontSize: 22, bold: true });
    T(s, sub, { x: x + 0.3, y: 3.85, w: 2.4, h: 0.35, fontSize: 12, bold: true, color: col });
    T(s, body, { x: x + 0.3, y: 4.3, w: 2.35, h: 2.2, fontSize: 13.5, color: K.muted });
    if (i < 3) arrow(s, x + 2.88, 4.3, x + 3.05, 4.3, K.mint, { w: 2 });
  });

  // ===== 5. SYSTEM ARCHITECTURE =====
  pres.addSection({ title: "Architecture" });
  s = content("Architecture", "04 · SYSTEM ARCHITECTURE", "Three layers: clients, Bifrost gateway, FreshGuard");
  const lane = (y, h, label, col) => { box(s, 0.7, y, 11.95, h, K.surf, { line: K.line, r: 0.1 });
    T(s, label, { x: 5.45, y: y + 0.1, w: 7, h: 0.3, fontSize: 10.5, bold: true, color: col, charSpacing: 2, align: "right" }); };
  const node = (x, y, w, h, title, sub, col, bg) => { box(s, x, y, w, h, bg, { line: col, lw: 1.25, r: 0.1 });
    T(s, [{ text: title, options: { bold: true, fontSize: 13.5, color: K.text, breakLine: true } }, { text: sub, options: { fontSize: 10.5, color: K.muted } }], { x: x + 0.12, y, w: w - 0.24, h, align: "center", valign: "middle" }); };
  lane(1.85, 1.05, "CLIENTS", K.gray);
  node(2.6, 2.05, 2.6, 0.7, "Your app / chatbot", "OpenAI-compatible SDK", K.gray, K.surf2);
  node(5.55, 2.05, 2.6, 0.7, "AI agents", "MCP tool consumers", K.gray, K.surf2);
  node(8.5, 2.05, 2.6, 0.7, "FreshGuard web UI", "calls FastAPI :8000 directly", K.gray, K.surf2);
  lane(3.1, 1.6, "BIFROST GATEWAY · :8080 · STOCK IMAGE", K.violet);
  node(1.05, 3.5, 2.55, 1.0, "OpenAI-compatible API", "/v1/chat/completions", K.violet, K.violetD);
  node(3.8, 3.5, 2.55, 1.0, "MCP gateway", "Agent Mode · /v1/mcp/tool/execute", K.violet, K.violetD);
  node(6.55, 3.5, 2.55, 1.0, "Go plugin hook", "HTTPTransportPostHook → X-FreshGuard-*", K.violet, K.violetD);
  node(9.3, 3.5, 3.1, 1.0, "Routing + fallbacks + logs", "provider/model · fallbacks[] · dashboard", K.violet, K.violetD);
  lane(4.9, 1.75, "FRESHGUARD SERVICE · PYTHON", K.mint);
  node(1.05, 5.3, 2.55, 1.15, "FastAPI :8000", "/api/check · /api/ask\ndrop-in /v1/chat/completions", K.mint, K.mintD);
  node(3.8, 5.3, 2.55, 1.15, "MCP server :8001", "verify_freshness\nverify_claim", K.mint, K.mintD);
  node(6.55, 5.3, 2.55, 1.15, "Pipeline", "extract → search → judge → score\nasyncio fan-out per claim", K.mint, K.mintD);
  node(9.3, 5.3, 1.45, 1.15, "Tavily", "live web search", K.cyan, K.cyanD);
  node(10.95, 5.3, 1.45, 1.15, "LLMs", "Groq · Gemini · OpenAI …", K.gray, K.surf2);
  // flows
  arrow(s, 3.9, 2.78, 2.6, 3.48, K.gray); arrow(s, 6.85, 2.78, 5.1, 3.48, K.gray);
  arrow(s, 5.1, 4.52, 5.1, 5.28, K.mint, { w: 2 }); arrow(s, 7.85, 4.52, 2.9, 5.28, K.mint, { w: 1.25, dash: "dash" });
  arrow(s, 9.1, 5.95, 9.28, 5.95, K.cyan, { w: 2 });
  arrow(s, 8.4, 5.28, 10.0, 4.52, K.violet, { w: 1.5 }); arrow(s, 11.6, 4.52, 11.6, 5.28, K.violet, { w: 1.5 });
  T(s, "Mint: verification calls · violet: every LLM call goes through Bifrost (routing, fallbacks, logs) · internal calls carry x-freshguard-skip and an empty MCP header, so there is no recursion.", { x: 0.7, y: 6.7, w: 11.95, h: 0.28, fontSize: 10.5, color: K.dim });
  s.addNotes("Clients reach Bifrost through three public extension points. All FreshGuard model calls loop back through Bifrost for routing, fallbacks and observability; Tavily supplies the evidence.");

  // ===== 6. REQUEST LIFECYCLE (sequence) =====
  s = content("Architecture", "05 · REQUEST LIFECYCLE", "One answer, end to end: who talks to whom, in order");
  const actors = [["Client", K.gray], ["Bifrost", K.violet], ["FreshGuard", K.mint], ["Tavily", K.cyan], ["LLM provider", K.gray]];
  const ax = (i) => 1.5 + i * 2.6;
  actors.forEach(([a, col], i) => { box(s, ax(i) - 0.85, 1.9, 1.7, 0.5, col === K.gray ? K.surf2 : (col === K.violet ? K.violetD : col === K.mint ? K.mintD : K.cyanD), { line: col, r: 0.08 });
    T(s, a, { x: ax(i) - 0.85, y: 1.9, w: 1.7, h: 0.5, fontSize: 13, bold: true, align: "center", valign: "middle" });
    s.addShape(pres.shapes.LINE, { x: ax(i), y: 2.42, w: 0, h: 3.95, line: { color: K.line, width: 1, dashType: "dash" }, objectName: id("lifeline") }); });
  T(s, [{ text: "≈7 s end to end  ", options: { bold: true, color: K.mint } }, { text: "for 3 claims: 1 extraction call, 3 parallel Tavily searches, 3 judge calls, all model calls logged in Bifrost", options: { color: K.muted } }], { x: 0.7, y: 6.55, w: 11.95, h: 0.32, fontSize: 13, align: "center" });
  const msg = (k, from, to, y, label, col, dash) => { arrow(s, ax(from) + (to > from ? 0.05 : -0.05), y, ax(to) + (to > from ? -0.05 : 0.05), y, col, { w: 1.5, dash });
    const lx = Math.min(ax(from), ax(to)); T(s, [{ text: `${k}  `, options: { bold: true, color: col } }, { text: label, options: { color: K.text } }], { x: lx + 0.1, y: y - 0.3, w: Math.abs(ax(to) - ax(from)) - 0.2, h: 0.28, fontSize: 11, align: "center" }); };
  msg("1", 0, 1, 2.85, "chat completion request", K.gray);
  msg("2", 1, 4, 3.3, "routed (fallback if down)", K.violet);
  msg("3", 1, 2, 3.75, "verify_freshness(answer)", K.mint);
  msg("4", 2, 1, 4.2, "extract claims (JSON)", K.mint, "dash");
  msg("5", 1, 4, 4.65, "LLM call, logged", K.violet, "dash");
  msg("6", 2, 3, 5.1, "N searches in parallel", K.cyan);
  msg("7", 2, 1, 5.55, "judge each claim on its evidence", K.mint, "dash");
  msg("8", 2, 0, 6.15, "report: score, verdicts, current facts, URLs", K.mint);

  // ===== 7. THREE INTEGRATIONS =====
  pres.addSection({ title: "Bifrost" });
  s = content("Bifrost", "06 · EXTENDING BIFROST", "Three ways into Bifrost, all public extension points");
  const ints = [[I.plug, "MCP tool server", "MCP gateway · Agent Mode", "Bifrost discovers verify_freshness and verify_claim and can auto-execute them in the model's tool loop, or run them via /v1/mcp/tool/execute.", "WORKS ON STOCK IMAGE", K.mint, K.mintD],
    [I.code, "Native Go plugin", "HTTPTransportPostHook", "Annotates every chat completion with X-FreshGuard-Score/Label/Stale-Count and an embedded report. Fails open; a skip header prevents recursion. 5 unit tests.", "NEEDS DYNAMIC BUILD", K.amber, K.amberD],
    [I.refresh, "Drop-in endpoint", "OpenAI-compatible API", "Point an existing SDK's base_url at FreshGuard: the same completion comes back with a freshguard report and X-FreshGuard-Score header.", "WORKS TODAY", K.mint, K.mintD]];
  ints.forEach(([img, h, ep, body, status, fg, bg], i) => {
    const x = 0.7 + i * 4.05;
    box(s, x, 2.0, 3.75, 4.6, K.surf, { line: K.line });
    disc(s, img, x + 0.3, 2.3, 0.8, K.violet);
    T(s, h, { x: x + 0.3, y: 3.3, w: 3.2, h: 0.45, fontSize: 21, bold: true });
    T(s, ep, { x: x + 0.3, y: 3.78, w: 3.2, h: 0.35, fontSize: 12.5, bold: true, color: K.violet });
    T(s, body, { x: x + 0.3, y: 4.25, w: 3.15, h: 1.7, fontSize: 13.5, color: K.muted });
    pill(s, x + 0.3, 6.05, status, fg, bg);
  });

  // ===== 8. SCORING =====
  s = content("Bifrost", "07 · FRESHNESS SCORE", "A score you can gate on: 0 expired, 100 verified");
  const segs = [[0, 35, K.coral, "STALE  0–34"], [35, 70, K.amber, "UNCERTAIN  35–69"], [70, 100, K.mint, "FRESH  70–100"]];
  segs.forEach(([a, b, col, lab]) => { const x = 0.7 + (a / 100) * 11.95, w = ((b - a) / 100) * 11.95;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.3, w, h: 0.42, fill: { color: col }, line: { color: col }, objectName: id("seg") });
    T(s, lab, { x, y: 2.85, w, h: 0.35, fontSize: 13, bold: true, color: col, align: "center" }); });
  [[1, "Python 3.12"], [34, "overall answer"], [99, "$1,199 price"]].forEach(([v, lab]) => { const x = 0.7 + (v / 100) * 11.95;
    s.addShape(pres.shapes.OVAL, { x: x - 0.13, y: 2.38, w: 0.26, h: 0.26, fill: { color: K.bg }, line: { color: K.text, width: 2 }, objectName: id("marker") });
    T(s, `${v} · ${lab}`, { x: Math.min(Math.max(x - 1.1, 0.7), 10.45), y: 1.88, w: 2.2, h: 0.3, fontSize: 11, color: K.text, align: "center" }); });
  const rules = [["current", K.mint, "60 + 40 × confidence", "Evidence confirms the claim today."], ["outdated", K.coral, "30 × (1 − confidence)", "Evidence contradicts it; the current fact is returned."], ["unverified", K.amber, "35 / 45 / 55 by volatility", "Weak or no evidence: fast-moving claims are penalised more."]];
  rules.forEach(([v, col, f, d], i) => { const y = 3.6 + i * 0.95;
    box(s, 0.7, y, 11.95, 0.8, K.surf, { line: K.line });
    pill(s, 1.0, y + 0.24, v.toUpperCase(), col, col === K.mint ? K.mintD : col === K.coral ? K.coralD : K.amberD, 1.35);
    T(s, f, { x: 2.65, y: y + 0.2, w: 3.6, h: 0.4, fontSize: 16, bold: true, fontFace: "Courier New", valign: "middle" });
    T(s, d, { x: 6.4, y: y + 0.2, w: 6.0, h: 0.4, fontSize: 14, color: K.muted, valign: "middle" }); });
  T(s, "Overall score = mean of claim scores. Exposed as X-FreshGuard-Score so apps can block, warn or auto-correct.", { x: 0.7, y: 6.5, w: 11.95, h: 0.35, fontSize: 13, color: K.dim });

  // ===== 9. LIVE DEMO =====
  pres.addSection({ title: "Demo" });
  s = content("Demo", "08 · LIVE THROUGH A STOCK BIFROST", "Real run: two of three claims had expired");
  box(s, 0.7, 1.95, 8.3, 4.75, "071216", { line: K.line, r: 0.1 });
  [K.coral, K.amber, K.mint].forEach((c, i) => s.addShape(pres.shapes.OVAL, { x: 0.95 + i * 0.25, y: 2.15, w: 0.14, h: 0.14, fill: { color: c }, line: { color: c }, objectName: id("dot") }));
  T(s, "scripts/demo_agent_mode.sh", { x: 1.85, y: 2.08, w: 5, h: 0.28, fontSize: 11, color: K.dim, fontFace: "Courier New" });
  const mono = { fontFace: "Courier New", fontSize: 12.5 };
  T(s, [
    { text: "━━ 1) LLM via Bifrost (qwen3.8-27b), no tools", options: { ...mono, color: K.violet, breakLine: true } },
    { text: "Latest stable Python is 3.12. Newest iPhone is the", options: { ...mono, color: K.text, breakLine: true } },
    { text: "iPhone 15 Pro Max, starting at $1,199.", options: { ...mono, color: K.text, breakLine: true } },
    { text: " ", options: { ...mono, breakLine: true } },
    { text: "━━ 2) Bifrost MCP → freshguard-verify_freshness", options: { ...mono, color: K.mint, breakLine: true } },
    { text: "Overall freshness: 34/100 (stale)", options: { ...mono, color: K.text, bold: true, breakLine: true } },
    { text: " ✗ [  1] Latest stable Python is 3.12", options: { ...mono, color: K.coral, breakLine: true } },
    { text: "        now: Python 3.15.2", options: { ...mono, color: K.muted, breakLine: true } },
    { text: " ✗ [  2] Newest iPhone is the 15 Pro Max", options: { ...mono, color: K.coral, breakLine: true } },
    { text: "        now: iPhone 18 Pro Max", options: { ...mono, color: K.muted, breakLine: true } },
    { text: " ✓ [ 99] iPhone 15 Pro Max starts at $1,199", options: { ...mono, color: K.mint } },
  ], { x: 1.0, y: 2.55, w: 7.8, h: 4.0 });
  box(s, 9.3, 1.95, 3.35, 2.3, K.surf, { line: K.line });
  T(s, [{ text: "34", options: { fontSize: 66, bold: true, color: K.coral, breakLine: true } }, { text: "freshness / 100", options: { fontSize: 13, color: K.muted } }], { x: 9.3, y: 2.0, w: 3.35, h: 2.2, align: "center", valign: "middle" });
  const kpis = [["≈7 s", "end-to-end"], ["3", "Tavily searches"], ["0 lines", "app code changed"]];
  kpis.forEach(([v, l], i) => { const y = 4.45 + i * 0.77; box(s, 9.3, y, 3.35, 0.65, K.surf, { line: K.line });
    T(s, [{ text: v + "  ", options: { bold: true, color: K.mint, fontSize: 17 } }, { text: l, options: { color: K.muted, fontSize: 13 } }], { x: 9.55, y, w: 3.0, h: 0.65, valign: "middle" }); });

  // ===== 10. RELIABILITY =====
  s = content("Demo", "09 · ENGINEERED FOR PRODUCTION", "Built to never break the request it's checking");
  const rel = [[I.shieldDark, "Fail open", "If verification errors or times out, the original response passes through untouched with X-FreshGuard-Status: error."],
    [I.refresh, "No recursion", "Internal calls send x-freshguard-skip and an empty MCP include header, so FreshGuard never checks itself."],
    [I.layers, "Provider failover", "All LLM calls use Bifrost fallbacks[]: when the primary model hits rate limits, a second model takes over."],
    [I.lock, "Evidence-only judge", "The judge may only use retrieved pages; with weak evidence it answers unverified instead of guessing."],
    [I.trend, "Parallel fan-out", "Claims are searched and judged concurrently, so latency stays flat as claims grow, and at most 6 are checked per answer."],
    [I.terminal, "Tested", "3 Python tests (pipeline mocked end to end) + 5 Go tests (path filter, skip header, annotate, fail-open)."]];
  rel.forEach(([img, h, b], i) => { const x = 0.7 + (i % 3) * 4.05, y = 1.95 + Math.floor(i / 3) * 2.45;
    box(s, x, y, 3.75, 2.2, K.surf, { line: K.line });
    disc(s, img === I.terminal ? I.code : img, x + 0.3, y + 0.3, 0.65, K.mint);
    T(s, h, { x: x + 1.15, y: y + 0.3, w: 2.4, h: 0.65, fontSize: 18, bold: true, valign: "middle" });
    T(s, b, { x: x + 0.3, y: y + 1.1, w: 3.2, h: 1.0, fontSize: 13, color: K.muted }); });

  // ===== 11. IMPACT =====
  pres.addSection({ title: "Impact" });
  s = content("Impact", "10 · IMPACT & ROADMAP", "Wherever an outdated fact costs trust or money");
  const who = [["Support bots", "pricing, plans, policies"], ["Coding assistants", "API and library versions"], ["Sales & research copilots", "leadership, funding, launches"], ["Compliance answers", "laws and regulations"]];
  T(s, "WHO NEEDS IT", { x: 0.7, y: 1.95, w: 5, h: 0.3, fontSize: 11, bold: true, color: K.dim, charSpacing: 2 });
  who.forEach(([a, b], i) => { const y = 2.35 + i * 1.05; box(s, 0.7, y, 5.6, 0.85, K.surf, { line: K.line });
    disc(s, I.users, 0.9, y + 0.14, 0.57, K.cyan);
    T(s, [{ text: a, options: { bold: true, fontSize: 16, color: K.text, breakLine: true } }, { text: b, options: { fontSize: 12.5, color: K.muted } }], { x: 1.65, y, w: 4.5, h: 0.85, valign: "middle" }); });
  T(s, "WHAT'S NEXT", { x: 6.9, y: 1.95, w: 5, h: 0.3, fontSize: 11, bold: true, color: K.dim, charSpacing: 2 });
  const road = [["NOW", K.mint, "MCP tool + Go plugin + drop-in endpoint, live through Bifrost"], ["NEXT", K.amber, "Verdict cache with TTL by volatility; streaming-aware checks"], ["THEN", K.violet, "Trusted-source lists per domain; Bifrost image with the plugin preloaded"], ["VISION", K.cyan, "Freshness as a standard gateway metric next to latency and cost"]];
  road.forEach(([t, col, d], i) => { const y = 2.35 + i * 1.05;
    s.addShape(pres.shapes.OVAL, { x: 6.95, y: y + 0.28, w: 0.28, h: 0.28, fill: { color: col }, line: { color: col }, objectName: id("node") });
    if (i < 3) s.addShape(pres.shapes.LINE, { x: 7.09, y: y + 0.58, w: 0, h: 0.75, line: { color: K.line, width: 1.5 }, objectName: id("spine") });
    T(s, t, { x: 7.45, y: y + 0.12, w: 1.2, h: 0.6, fontSize: 13, bold: true, color: col, valign: "middle", charSpacing: 2 });
    T(s, d, { x: 8.65, y: y + 0.07, w: 4.0, h: 0.7, fontSize: 14, valign: "middle" }); });

  // ===== 12. CLOSE =====
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "HERO", sectionTitle: "Close" });
  T(s, "FRESHGUARD", { x: 0.8, y: 1.55, w: 6, h: 0.45, fontSize: 18, bold: true, color: K.mint, charSpacing: 6 });
  s.addText("Trust, but verify.\nLive.", { placeholder: "title" });
  T(s, "github.com/shubham-jadhav-FiatLux/freshguard", { x: 0.8, y: 4.45, w: 8, h: 0.45, fontSize: 20, bold: true, color: K.cyan });
  T(s, "Open source · MIT · Python (FastAPI, MCP) · Go (Bifrost plugin) · Docker", { x: 0.8, y: 5.0, w: 8.5, h: 0.4, fontSize: 15, color: K.muted });
  px = 0.8; px += pill(s, px, 5.75, "BIFROST BY MAXIM AI", K.violet, K.violetD) + 0.15; px += pill(s, px, 5.75, "TAVILY", K.cyan, K.cyanD) + 0.15; pill(s, px, 5.75, "GROQ", K.gray, K.surf2);
  stamp(s, 10.0, 3.0, "VERIFIED", K.mint, -10);
  T(s, [{ text: "Shubham Jadhav", options: { fontFace: "Cambria", fontSize: 24, bold: true, color: K.amber, breakLine: true } }, { text: "Department of Computer Science and Engineering, IIT Madras", options: { fontFace: "Calibri", fontSize: 14, color: K.muted } }], { x: 0.8, y: 6.35, w: 9, h: 0.85, valign: "middle" });

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
