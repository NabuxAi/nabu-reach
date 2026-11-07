"""Build a public static demo: in-browser sample records only, no backend."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
out=root/"dist"/"demo"
out.mkdir(parents=True,exist_ok=True)
source=root/"reach"/"web"
for asset in ("app.css","app.js"):
    shutil.copy2(source/asset,out/asset)
shutil.copy2(root/"demo"/"mock.js",out/"mock.js")
html=(source/"index.html").read_text(encoding="utf-8")
html=html.replace('href="/app.css"','href="app.css"').replace('src="/app.js"','src="app.js"')
html=html.replace('<script src="app.js" defer></script>',
                  '<script src="mock.js" defer></script><script src="app.js" defer></script>')
html=html.replace('Local workspace','Interactive public demo')
html=html.replace('Local-first MVP · No live WhatsApp sending',
                  'Public demo · Browser-only sample data · No real sending')
html=html.replace('<div class="content">',
                  '<div class="content"><div class="demo-alert" role="note">PUBLIC INTERACTIVE DEMO · All records are fictional and reset when you refresh. No WhatsApp messages can be sent. Do not import real contacts.</div>')
(out/"index.html").write_text(html,encoding="utf-8")
css=(out/"app.css").read_text()
css+='\n.demo-alert{padding:13px 17px;border:1px solid #2875a1;border-radius:12px;background:#0b3045;color:#a3e7ff;margin-bottom:25px;font-size:13px}\n'
(out/"app.css").write_text(css)
print("Built safe public demo:",out)
