import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
const types = { html: 'text/html', css: 'text/css', js: 'text/javascript', svg: 'image/svg+xml', png: 'image/png', webp: 'image/webp', ico: 'image/x-icon' };
const files = new Set(['index.html', 'style.css', 'app.js', 'search.js', 'geo.js', '404.html', 'kaart-404.webp', 'favicon.svg', 'favicon.ico', 'favicon-32.png', 'favicon-180.png', 'favicon-512.png']);
// Dezelfde headers als online (web/_headers, blok "/*"), zodat CSP-fouten ook lokaal zichtbaar zijn.
const headers = Object.fromEntries((await readFile(new URL('./web/_headers', import.meta.url), 'utf-8')).split('\n').filter(line => /^\s+[\w-]+:/.test(line)).map(line => { const [key, ...rest] = line.trim().split(':'); return [key, rest.join(':').trim()]; }));
const read = name => readFile(new URL(`./web/${name}`, import.meta.url));
createServer(async (req, res) => {
  const path = new URL(req.url.replace(/^\/+/, '/'), 'http://localhost').pathname;
  const name = path === '/' ? 'index.html' : path.slice(1);
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405, headers).end(); return; }
  try {
    // Zoals online: /index.html verwijst naar /, een onbekend pad geeft de 404-pagina.
    if (path === '/index.html') { res.writeHead(307, { ...headers, Location: '/' }).end(); return; }
    const found = files.has(name);
    const content = await read(found ? name : '404.html');
    res.writeHead(found ? 200 : 404, { ...headers, 'Content-Type': `${types[(found ? name : '404.html').split('.').pop()]}; charset=utf-8`, 'Cache-Control': 'no-store' });
    res.end(req.method === 'HEAD' ? undefined : content);
  } catch { res.writeHead(500, headers).end('Kan bestand niet lezen.'); }
}).listen(Number(process.env.PORT) || 4173, '127.0.0.1', function () { console.log(`Demo: http://127.0.0.1:${this.address().port}`); });
