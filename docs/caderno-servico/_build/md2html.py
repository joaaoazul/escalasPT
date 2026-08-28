import html, re, unicodedata, sys

def slug(t):
    t = unicodedata.normalize('NFKD', t).encode('ascii','ignore').decode()
    t = re.sub(r'[^a-zA-Z0-9]+','-',t).strip('-').lower()
    return t or 'sec'

def inline(s):
    s = html.escape(s, quote=False)
    codes = []
    def keep(m):
        codes.append(m.group(1)); return f'\x00{len(codes)-1}\x00'
    s = re.sub(r'`([^`]+)`', keep, s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'\x00(\d+)\x00', lambda m: '<code>'+codes[int(m.group(1))]+'</code>', s)
    return s

def split_row(row):
    row = row.strip().strip('|')
    cells, cur, i = [], '', 0
    while i < len(row):
        c = row[i]
        if c == '\\' and i+1 < len(row) and row[i+1] == '|':
            cur += '|'; i += 2; continue
        if c == '|':
            cells.append(cur); cur = ''; i += 1; continue
        cur += c; i += 1
    cells.append(cur)
    return [c.strip() for c in cells]

def convert(md, prefix, headings):
    lines = md.split('\n')
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```'):
            lang = ln[3:].strip(); i += 1; buf = []
            while i < len(lines) and not lines[i].startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            out.append(f'<div class="code"><pre><code class="lang-{lang}">'
                       + html.escape('\n'.join(buf)) + '</code></pre></div>')
            continue
        if re.match(r'^#{1,3} ', ln):
            level = len(ln) - len(ln.lstrip('#'))
            text = ln[level+1:].strip()
            sid = prefix + '-' + slug(text)
            if level == 2:
                headings.append((sid, text))
            if level == 1:
                out.append(f'<h1 id="{sid}">{inline(text)}</h1>')
            else:
                out.append(f'<h{level} id="{sid}"><a class="anchor" href="#{sid}">{inline(text)}</a></h{level}>')
            i += 1; continue
        if ln.startswith('> '):
            buf = []
            while i < len(lines) and (lines[i].startswith('>')):
                buf.append(lines[i].lstrip('>').lstrip()); i += 1
            sub = []
            convert_para(buf, sub)
            out.append('<blockquote>' + ''.join(sub) + '</blockquote>')
            continue
        if ln.startswith('|') and i+1 < len(lines) and re.match(r'^\|[\s:\-|]+\|$', lines[i+1].strip()):
            head = split_row(ln); i += 2; rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append(split_row(lines[i])); i += 1
            t = ['<div class="tablewrap"><table><thead><tr>']
            t += [f'<th>{inline(c)}</th>' for c in head]
            t.append('</tr></thead><tbody>')
            for r in rows:
                t.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>')
            t.append('</tbody></table></div>')
            out.append(''.join(t)); continue
        m = re.match(r'^(\d+)\. ', ln)
        if m or re.match(r'^[-*] ', ln):
            ordered = bool(m)
            items, start = [], (m.group(1) if m else None)
            while i < len(lines):
                mm = re.match(r'^(\d+)\. (.*)$', lines[i]) if ordered else re.match(r'^[-*] (.*)$', lines[i])
                if not mm: break
                txt = mm.group(2) if ordered else mm.group(1)
                i += 1
                while i < len(lines) and lines[i].startswith('  ') and lines[i].strip():
                    txt += ' ' + lines[i].strip(); i += 1
                items.append(txt)
            tag = 'ol' if ordered else 'ul'
            attr = f' start="{start}"' if ordered and start != '1' else ''
            out.append(f'<{tag}{attr}>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + f'</{tag}>')
            continue
        if ln.strip() == '---':
            out.append('<hr />'); i += 1; continue
        if not ln.strip():
            i += 1; continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,3} |> |\||```|[-*] |\d+\. |---$)', lines[i]):
            buf.append(lines[i].strip()); i += 1
        out.append('<p>' + inline(' '.join(buf)) + '</p>')
    return '\n'.join(out)

def convert_para(buf, out):
    text, cur = [], []
    for b in buf:
        if not b.strip():
            if cur: text.append(' '.join(cur)); cur = []
        else:
            cur.append(b)
    if cur: text.append(' '.join(cur))
    for t in text:
        out.append('<p>' + inline(t) + '</p>')
