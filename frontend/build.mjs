import esbuild from 'esbuild';
import fs from 'fs';
const prod = process.argv.includes('--prod');
const res = await esbuild.build({ entryPoints: ['src/main.js'], bundle: true, minify: true, format: 'iife', loader: { '.glb': 'binary' }, write: false, legalComments: 'none', target: 'es2020', logLevel: 'error' });
let js = res.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const css = fs.readFileSync('src/style.css', 'utf8');
const body = fs.readFileSync('src/body.html', 'utf8');
const fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&family=Instrument+Sans:wdth,wght@75..100,400..700&family=JetBrains+Mono:wght@400;500&display=swap">';
const head = `<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<title>ReForm3D</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n`;
const early = `<script>document.documentElement.classList.add('js')</script>`;
const art = `${head}${fonts}\n<style>\n${css}\n</style>\n${early}\n${body}\n<script>\n${js}\n</script>\n`;
fs.mkdirSync('dist', { recursive: true });
fs.writeFileSync('dist/reform3d.html', art);
const localFonts = `<style>@font-face{font-family:'Archivo';font-weight:100 900;font-stretch:62% 125%;src:url(fonts/archivo.woff2) format('woff2')}
@font-face{font-family:'Instrument Sans';font-weight:400 700;font-stretch:75% 100%;src:url(fonts/instrument.woff2) format('woff2')}
@font-face{font-family:'JetBrains Mono';font-weight:400;src:url(fonts/jbm400.woff2) format('woff2')}
@font-face{font-family:'JetBrains Mono';font-weight:500;src:url(fonts/jbm500.woff2) format('woff2')}</style>`;
const test = `<!doctype html><html lang="en"><head>${head}${localFonts}<style>\n${css}\n</style>${early}</head><body>${body}\n<script>\n${js}\n</script></body></html>`;
fs.mkdirSync('www', { recursive: true });
fs.writeFileSync('www/index.html', test);
for (const d of ['dist', 'www']) fs.copyFileSync('assets/printer.html', d + '/printer.html');   // the printer in the request panel
console.log('built', (art.length / 1024 / 1024).toFixed(2), 'MB');
