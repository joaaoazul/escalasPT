import re, sys
sys.path.insert(0, '.')
from md2html import convert

base = '/home/user/escalasPT/docs/caderno-servico/'
plano = open(base+'PLANO.md').read()
ident = open(base+'MODULO-IDENTIFICACOES.md').read()

# drop the H1 lines (page has its own masthead) but keep the intro blockquote
plano = plano.split('\n', 1)[1]
ident = ident.split('\n', 1)[1]
ident = ident.replace('](./PLANO.md)', '](#p-0-o-que-mudou-face-a-v1)')
plano = plano.replace('](./MODULO-IDENTIFICACOES.md)', '](#i-1-enquadramento-o-que-tem-de-estar-resolvido-antes-de-ligar)')

h1, h2 = [], []
body1 = convert(plano, 'p', h1)
body2 = convert(ident, 'i', h2)

def nav(items):
    out = []
    for sid, text in items:
        m = re.match(r"^(\d+(?:\.\d+)*)\.\s+(.*)$", text)
        num, label = (m.group(1), m.group(2)) if m else ('', text)
        out.append(f'<li><a href="#{sid}"><span class="n">{num}</span><span>{label}</span></a></li>')
    return '\n'.join(out)

CSS = """
:root{
  --bg:#F3F4F0; --surface:#FBFBF9; --surface-2:#EDEFE9;
  --text:#151C19; --muted:#5A6862; --faint:#8A968F;
  --rule:#DBDED6; --rule-strong:#C5C9BF;
  --accent:#0B6B4F; --accent-soft:rgba(11,107,79,.10);
  --amber:#8F5D00; --amber-soft:rgba(143,93,0,.10);
  --danger:#A2352C; --danger-soft:rgba(162,53,44,.09);
  --shadow:0 1px 2px rgba(21,28,25,.05), 0 8px 24px -18px rgba(21,28,25,.35);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0A1013; --surface:#111A1D; --surface-2:#162126;
    --text:#E4EAE6; --muted:#93A49D; --faint:#6E7F79;
    --rule:rgba(147,164,157,.18); --rule-strong:rgba(147,164,157,.30);
    --accent:#43C295; --accent-soft:rgba(67,194,149,.12);
    --amber:#DFA644; --amber-soft:rgba(223,166,68,.13);
    --danger:#E2796E; --danger-soft:rgba(226,121,110,.13);
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -20px rgba(0,0,0,.9);
  }
}
:root[data-theme="dark"]{
  --bg:#0A1013; --surface:#111A1D; --surface-2:#162126;
  --text:#E4EAE6; --muted:#93A49D; --faint:#6E7F79;
  --rule:rgba(147,164,157,.18); --rule-strong:rgba(147,164,157,.30);
  --accent:#43C295; --accent-soft:rgba(67,194,149,.12);
  --amber:#DFA644; --amber-soft:rgba(223,166,68,.13);
  --danger:#E2796E; --danger-soft:rgba(226,121,110,.13);
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -20px rgba(0,0,0,.9);
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--text);
  font-family:"Source Sans 3","Segoe UI",system-ui,sans-serif;
  font-size:17px; line-height:1.62; -webkit-text-size-adjust:100%;
}
a{color:var(--accent); text-decoration:none; border-bottom:1px solid var(--accent-soft)}
a:hover{border-bottom-color:var(--accent)}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent); outline-offset:3px; border-radius:2px}

/* ── masthead ─────────────────────────────── */
.masthead{border-bottom:1px solid var(--rule-strong); background:var(--surface)}
.masthead .in{max-width:1180px; margin:0 auto; padding:44px 24px 30px;
  display:flex; flex-direction:column; gap:20px}
.kicker{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:11px;
  letter-spacing:.18em; text-transform:uppercase; color:var(--faint)}
h1.title{font-family:"Zilla Slab",Georgia,serif; font-weight:600; font-size:clamp(2.3rem,6vw,3.4rem);
  line-height:1.06; margin:0; letter-spacing:-.015em; text-wrap:balance}
h1.title em{font-style:normal; color:var(--accent)}
.standfirst{max-width:60ch; color:var(--muted); font-size:1.06rem; margin:0}
.meta{display:flex; flex-wrap:wrap; gap:0 28px; row-gap:10px;
  font-family:"JetBrains Mono",ui-monospace,monospace; font-size:12px; color:var(--muted)}
.meta b{color:var(--text); font-weight:500}

/* ── shell ────────────────────────────────── */
.shell{max-width:1180px; margin:0 auto; padding:0 24px 96px;
  display:grid; grid-template-columns:236px minmax(0,1fr); gap:56px; align-items:start}
nav.index{position:sticky; top:0; max-height:100vh; overflow-y:auto;
  padding:40px 0 40px; font-size:14px}
nav.index h2{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:10.5px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--faint);
  margin:0 0 10px; padding-bottom:8px; border-bottom:1px solid var(--rule)}
nav.index h2+h2{margin-top:26px}
nav.index ul{list-style:none; margin:0 0 4px; padding:0; display:flex; flex-direction:column}
nav.index a{display:flex; gap:9px; padding:4px 0; color:var(--muted); border:0; line-height:1.35}
nav.index a:hover{color:var(--text)}
nav.index .n{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:11px;
  color:var(--faint); min-width:2.1em; padding-top:2px; font-variant-numeric:tabular-nums}
main{padding:40px 0 0; max-width:70ch; min-width:0}

/* ── prose ────────────────────────────────── */
main h2{font-family:"Zilla Slab",Georgia,serif; font-weight:600; font-size:1.72rem;
  line-height:1.2; margin:64px 0 4px; letter-spacing:-.01em; text-wrap:balance;
  padding-top:22px; border-top:2px solid var(--rule-strong)}
main h2 a,main h3 a{color:inherit; border:0}
main h3{font-family:"Zilla Slab",Georgia,serif; font-weight:600; font-size:1.2rem;
  margin:38px 0 2px; text-wrap:balance}
main p{margin:14px 0}
main ul,main ol{margin:14px 0; padding-left:1.25em; display:flex; flex-direction:column; gap:8px}
main li::marker{color:var(--faint)}
main ol li::marker{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:.85em}
hr{border:0; border-top:1px solid var(--rule); margin:52px 0 0}
strong{font-weight:600}
code{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:.85em;
  background:var(--surface-2); border:1px solid var(--rule);
  padding:.08em .34em; border-radius:3px; word-break:break-word}
.code{margin:20px 0; background:var(--surface); border:1px solid var(--rule);
  border-left:3px solid var(--accent); border-radius:4px; overflow-x:auto; box-shadow:var(--shadow)}
.code pre{margin:0; padding:16px 18px}
.code code{background:none; border:0; padding:0; font-size:13px; line-height:1.6; white-space:pre}
blockquote{margin:24px 0; padding:16px 20px; background:var(--amber-soft);
  border:1px solid var(--rule); border-left:3px solid var(--amber); border-radius:4px}
blockquote p{margin:8px 0; font-size:.97rem}
blockquote p:first-child{margin-top:0} blockquote p:last-child{margin-bottom:0}
.tablewrap{margin:24px 0; overflow-x:auto; border:1px solid var(--rule);
  border-radius:4px; background:var(--surface); box-shadow:var(--shadow)}
table{border-collapse:collapse; width:100%; font-size:14.5px}
th,td{text-align:left; padding:10px 14px; border-bottom:1px solid var(--rule); vertical-align:top}
th{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:10.5px; font-weight:500;
  letter-spacing:.1em; text-transform:uppercase; color:var(--faint);
  background:var(--surface-2); white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td:first-child{font-variant-numeric:tabular-nums}
main h2:first-of-type{margin-top:8px; border-top:0; padding-top:0}

/* ── part divider ─────────────────────────── */
.part{margin:96px 0 0; padding:26px 0 0; border-top:2px solid var(--accent)}
.part .lbl{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:11px;
  letter-spacing:.18em; text-transform:uppercase; color:var(--accent)}
.part h2.parttitle{font-size:2.05rem; border:0; padding:0; margin:6px 0 0}

@media (max-width:900px){
  .shell{grid-template-columns:1fr; gap:0; padding-bottom:64px}
  nav.index{position:static; max-height:none; padding:26px 0 0;
    border-bottom:1px solid var(--rule); margin-bottom:8px}
  main{padding-top:26px}
  body{font-size:16.5px}
  .masthead .in{padding:32px 20px 24px}
  .shell{padding-left:20px; padding-right:20px}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important; transition:none!important}}
"""

HTML = f"""<title>Caderno de Serviço</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@500;600&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style>

<header class="masthead">
  <div class="in">
    <div class="kicker">Plano de execução · versão 2 · app nova</div>
    <h1 class="title">Caderno de <em>Serviço</em></h1>
    <p class="standfirst">Registar o serviço no terreno — ocorrências, fiscalizações, notas — no telemóvel,
    sem rede, dentro da tailnet. Três módulos: caderno, redacção e painel. Mais o módulo de
    identificações, agora planeado, com portão de activação próprio.</p>
    <div class="meta">
      <span>Base: <b>escalasPT @556e3f9</b></span>
      <span>Repo novo: <b>C:\\Users\\joaoa\\caderno</b></span>
      <span>Acesso: <b>tailscale serve · https://…ts.net</b></span>
      <span>Fases: <b>0–4 autónomas · 5 com portão</b></span>
    </div>
  </div>
</header>

<div class="shell">
  <nav class="index">
    <h2>Parte I · Plano</h2>
    <ul>{nav(h1)}</ul>
    <h2>Parte II · Identificações</h2>
    <ul>{nav(h2)}</ul>
  </nav>
  <main>
    {body1}
    <div class="part">
      <div class="lbl">Parte II</div>
      <h2 class="parttitle">Módulo de identificações — pessoas e veículos</h2>
    </div>
    {body2}
  </main>
</div>
"""
open('/home/user/escalasPT/docs/caderno-servico/plano.html','w').write(HTML)
print('written', len(HTML))
