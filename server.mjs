import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
const files = { '/': ['index.html', 'text/html'], '/index.html': ['index.html', 'text/html'], '/style.css': ['style.css', 'text/css'], '/app.js': ['app.js', 'text/javascript'], '/search.js': ['search.js', 'text/javascript'], '/geo.js': ['geo.js', 'text/javascript'] };
createServer(async (req, res) => {
  const file = files[new URL(req.url, 'http://localhost').pathname];
  if (!file || !['GET', 'HEAD'].includes(req.method)) { res.writeHead(404).end(); return; }
  try {
    const content = await readFile(new URL(`./web/${file[0]}`, import.meta.url));
    res.writeHead(200, { 'Content-Type': `${file[1]}; charset=utf-8`, 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : content);
  } catch { res.writeHead(500).end('Kan bestand niet lezen.'); }
}).listen(Number(process.env.PORT) || 4173, '127.0.0.1', function () { console.log(`Demo: http://127.0.0.1:${this.address().port}`); });
