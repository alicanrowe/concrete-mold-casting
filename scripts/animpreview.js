#!/usr/bin/env node
// animpreview: render a moldanim GLB's clips to frames, an MP4 per clip and a contact sheet,
// in model-viewer on a white page (the same viewer and lighting the site uses).
//
//   node animpreview.js MODEL.glb OUT_DIR --mv path/to/model-viewer.min.js \
//        [--clips build,pour,demold] [--fps 24] [--size 1080x1080] [--orbit "30deg 66deg 3.2m"] [--sheet 12]
//
// Needs playwright (Chromium) and ffmpeg. model-viewer: the site's vendored copy, or
// https://cdn.jsdelivr.net/npm/@google/model-viewer@4.1.0/dist/model-viewer.min.js saved locally.
const fs = require('fs'), path = require('path'), http = require('http'), { execFileSync } = require('child_process');
const { chromium } = require('playwright');
if (process.platform === 'darwin' && !process.env.ALLOW_LOCAL_RENDER) {   // renders run on cloud machines, never the owner's Mac
  console.error('refusing to render on a Mac: run this on a cloud machine (ALLOW_LOCAL_RENDER=1 only if the owner asked).'); process.exit(3);
}

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const glb = path.resolve(args[0]), out = path.resolve(args[1]);
const mv = path.resolve(opt('mv', ''));
const clips = opt('clips', 'build,pour,demold').split(',');
const fps = +opt('fps', 24), [W, H] = opt('size', '1080x1080').split('x').map(Number);
const orbit = opt('orbit', '30deg 66deg auto'), sheetN = +opt('sheet', 12), still = opt('still', '');
fs.mkdirSync(out, { recursive: true });

const page = `<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;background:#fff}model-viewer{width:${W}px;height:${H}px;--poster-color:#fff;background:#fff}
</style><script type="module" src="/mv.js"></script></head><body>
<model-viewer id="m" src="/model.glb" camera-orbit="${orbit}" shadow-intensity="0.9" shadow-softness="1"
 exposure="1.05" environment-image="neutral" interaction-prompt="none" disable-zoom></model-viewer></body></html>`;

const srv = http.createServer((q, r) => {
  const f = q.url === '/' ? null : q.url === '/mv.js' ? mv : q.url === '/model.glb' ? glb : undefined;
  if (f === null) { r.writeHead(200, { 'content-type': 'text/html' }); return r.end(page); }
  if (!f) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { 'content-type': f.endsWith('.js') ? 'text/javascript' : 'model/gltf-binary' });
  fs.createReadStream(f).pipe(r);
});

(async () => {
  await new Promise(ok => srv.listen(0, ok));
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await p.goto(url);
  await p.waitForFunction(() => { const m = document.getElementById('m'); return m && m.loaded; }, null, { timeout: 120000 });
  const info = await p.evaluate(() => { const m = document.getElementById('m'); return { anims: m.availableAnimations }; });
  console.log('clips in model:', info.anims.join(', '));
  const summary = {};
  for (const c of clips) {
    if (!info.anims.includes(c)) { console.log('missing clip', c); continue; }
    const dur = await p.evaluate(async (c) => {
      const m = document.getElementById('m'); m.animationName = c; m.pause();
      await new Promise(r => setTimeout(r, 300)); return m.duration;
    }, c);
    const dir = path.join(out, c); fs.mkdirSync(dir, { recursive: true });
    const n = Math.max(2, Math.round(dur * fps));
    for (let i = 0; i <= n; i++) {
      const t = Math.min(dur - 0.02, i / fps);  // at exactly the end the clip wraps to 0
      await p.evaluate(async (t) => {
        const m = document.getElementById('m'); m.currentTime = t;
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      }, t);
      await p.screenshot({ path: path.join(dir, `f${String(i).padStart(5, '0')}.png`) });
    }
    const mp4 = path.join(out, `${c}.mp4`);
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, 'f%05d.png'),
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', mp4]);
    // contact sheet: sheetN frames spread over the clip
    const pick = [...Array(sheetN).keys()].map(k => Math.round(k * n / (sheetN - 1)));
    const inputs = pick.flatMap(k => ['-i', path.join(dir, `f${String(k).padStart(5, '0')}.png`)]);
    const cols = 4, rows = Math.ceil(sheetN / cols);
    const layout = pick.map((_, k) => `${(k % cols) ? (k % cols) + '*w0' : '0'}_${Math.floor(k / cols) ? Math.floor(k / cols) + '*h0' : '0'}`).join('|')
      .replace(/(\d)\*w0/g, (m, d) => Array(+d).fill('w0').join('+')).replace(/(\d)\*h0/g, (m, d) => Array(+d).fill('h0').join('+'));
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...inputs, '-filter_complex',
      pick.map((_, k) => `[${k}:v]scale=360:-1[s${k}]`).join(';') + ';' + pick.map((_, k) => `[s${k}]`).join('') +
      `xstack=inputs=${pick.length}:layout=${layout}:fill=white`, '-frames:v', '1', path.join(out, `${c}_sheet.png`)]);
    summary[c] = { duration_s: +dur.toFixed(2), frames: n + 1, mp4 };
    console.log(c, summary[c]);
    if (!args.includes('--keep-frames')) fs.rmSync(dir, { recursive: true });
  }
  fs.writeFileSync(path.join(out, 'preview.json'), JSON.stringify(summary, null, 1));
  await b.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
