#!/usr/bin/env python3
"""Render a course's notes as a dense open-book exam reference.

Same source as make_study_guide.py, but reorganised for lookup under time
pressure instead of reading: the course's one-breath summaries up front, then
every definition, procedure, table, formula, code block, misconception and
worked example in lecture order, then one merged A-Z glossary, then every exam
checklist. Teaching prose and the "what you already know" recaps are dropped,
because in an open-book exam you are looking things up, not learning them.

Usage:
  python3 tools/make_exam_sheet.py itec4235 ~/Downloads/ITEC4235_Exam_Reference.pdf

Needs Google Chrome and poppler (pdftotext). Two passes, like the study guide:
the first finds which page each section lands on, the second fills the contents.
"""
import html
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WORD_FONTS = pathlib.Path("/Applications/Microsoft Word.app/Contents/Resources/DFonts")

CSS = r"""
@font-face{font-family:"GCambria";src:url("FONTS/Cambria.ttc");font-weight:400;font-style:normal}
@font-face{font-family:"GCambria";src:url("FONTS/Cambriab.ttf");font-weight:700;font-style:normal}
@font-face{font-family:"GCambria";src:url("FONTS/Cambriai.ttf");font-weight:400;font-style:italic}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibri.ttf");font-weight:400;font-style:normal}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibrib.ttf");font-weight:700;font-style:normal}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibrii.ttf");font-weight:400;font-style:italic}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibriz.ttf");font-weight:700;font-style:italic}
@font-face{font-family:"GConsolas";src:url("FONTS/Consola.ttf");font-weight:400}
@font-face{font-family:"GConsolas";src:url("FONTS/Consolab.ttf");font-weight:700}
:root{
  --navy:#16233F; --blue:#1F6FC5; --ink:#17171F; --muted:#4A4A5A;
  --def-bg:#E6EEF8; --def:#1F5FA8; --ex-bg:#E7F0E9; --ex:#2C6D48;
  --warn-bg:#FCF3DC; --warn:#A8780A; --exam-bg:#F8E3E3; --exam:#9B2125;
  --key-bg:#EDF0F5; --key:#16233F; --code-bg:#F2F4F6; --rule:#C6CFDB;
  --serif:"GCambria", Cambria, Caladea, Georgia, serif;
  --sans:"GCalibri", Calibri, Carlito, "Helvetica Neue", Arial, sans-serif;
  --mono:"GConsolas", Consolas, Menlo, monospace;
}
@page{
  size:Letter; margin:0.52in 0.55in 0.5in 0.55in;
  @top-right{content:"HEADER"; font-family:var(--serif); font-style:italic; font-size:7pt; color:#4A4A5A;
    vertical-align:bottom; padding-bottom:4pt; border-bottom:0.5pt solid #D4D8DE}
  @bottom-center{content:"Open-book exam reference  ·  " counter(page); font-family:var(--serif);
    font-size:7pt; color:#4A4A5A; vertical-align:top; padding-top:4pt; border-top:0.5pt solid #D4D8DE}
}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact; print-color-adjust:exact}
body{margin:0; font-family:var(--sans); font-size:8.4pt; line-height:1.28; color:var(--ink)}
#content{columns:2; column-gap:16pt}
#content h3.chap,#content .span{column-span:all}
#content h4.sec,#content h5,#content .box,#content .tw,#content pre.code,#content .formula,
#content figure.fig,#content .quad,#content .gantt{break-inside:avoid}
p{margin:0 0 4pt} ul,ol{margin:0 0 4pt; padding-left:13pt} li{margin:0 0 1.5pt}
a{color:inherit; text-decoration:none}
a.xref{font-weight:700}
a.xref .pg{font-weight:400; color:var(--blue); font-size:.9em; white-space:nowrap; font-variant-numeric:tabular-nums}
strong,b{font-weight:700}
code,kbd{font-family:var(--mono); font-size:.86em}
sub,sup{line-height:0}
em,i{font-style:italic}

/* ---- cover ---- */
.cover{height:9.4in; display:flex; flex-direction:column; justify-content:center; page-break-after:always; text-align:center}
.cover .t{font-family:var(--serif); font-size:34pt; font-weight:700; color:var(--navy); margin:0 0 4pt; letter-spacing:.01em}
.cover .s{font-family:var(--sans); font-size:13pt; color:var(--blue); letter-spacing:.22em; text-transform:uppercase; margin:0 0 26pt}
.cover .c{font-size:12pt; color:var(--ink); margin:0 0 3pt}
.cover .r{font-size:11pt; color:var(--muted); margin:0 0 22pt}
.cover .how{max-width:5.2in; margin:0 auto; text-align:left; font-size:9pt; color:var(--muted);
  border:0.75pt solid var(--rule); border-left:3pt solid var(--blue); padding:10pt 14pt; line-height:1.4}
.cover .how b{color:var(--navy)}

/* ---- structure ---- */
h2.part{font-family:var(--serif); font-size:17pt; font-weight:700; color:#FFF; background:var(--navy);
  margin:0 0 10pt; padding:7pt 12pt; page-break-before:always; page-break-after:avoid; letter-spacing:.01em}
h2.part span{font-weight:400; font-size:11pt; color:#B9C6DC; margin-left:10pt}
h3.chap{font-family:var(--serif); font-size:12pt; font-weight:700; color:var(--navy); margin:13pt 0 5pt;
  padding:0 0 2.5pt; border-bottom:1.25pt solid var(--navy); page-break-after:avoid}
h3.chap .lec{color:var(--blue); font-family:var(--sans); font-size:9pt; font-weight:700;
  letter-spacing:.08em; text-transform:uppercase; margin-right:7pt}
h4.sec{font-family:var(--sans); font-size:9.6pt; font-weight:700; color:var(--navy); margin:9pt 0 3pt;
  page-break-after:avoid}
h4.sec .n{color:var(--blue); margin-right:5pt}
h5{font-family:var(--sans); font-size:8.9pt; font-weight:700; color:var(--muted); margin:6pt 0 2pt;
  page-break-after:avoid}
section{page-break-before:auto}

/* ---- panels ---- */
.box{border:0.6pt solid var(--rule); border-left:2.5pt solid var(--rule); background:#FBFCFD;
  padding:5pt 8pt 2pt; margin:5pt 0 6pt; page-break-inside:avoid}
.box > .lbl{display:block; font-weight:700; font-size:8.4pt; margin:0 0 2.5pt; letter-spacing:.01em}
.box.def{background:var(--def-bg); border-left-color:var(--def)} .box.def > .lbl{color:var(--def)}
.box.ex{background:var(--ex-bg); border-left-color:var(--ex)} .box.ex > .lbl{color:var(--ex)}
.box.warn{background:var(--warn-bg); border-left-color:var(--warn)} .box.warn > .lbl{color:var(--warn)}
.box.exam{background:var(--exam-bg); border-left-color:var(--exam)} .box.exam > .lbl{color:var(--exam)}
.box.proc{background:var(--key-bg); border-left-color:var(--key)} .box.proc > .lbl{color:var(--key)}
.box .dl p{margin:0 0 2.5pt}
.breath{background:var(--key-bg); border:0.6pt solid var(--rule); border-left:2.5pt solid var(--blue);
  padding:6pt 9pt; margin:0 0 7pt; page-break-inside:avoid; text-align:justify}
.breath .lbl{display:block; font-weight:700; color:var(--navy); font-size:8.6pt; margin-bottom:2pt}

/* ---- tables ---- */
.tw{margin:4pt 0 6pt; page-break-inside:avoid}
table{border-collapse:collapse; width:100%; font-size:7.2pt; line-height:1.22}
th,td{text-align:left; vertical-align:top; padding:2pt 4pt; border-bottom:0.5pt solid var(--rule)}
th{font-weight:700; color:#FFF; background:var(--navy); border-bottom:none; font-size:7.4pt}
tbody tr:nth-child(even){background:#F4F6F9}
table.gloss td:first-child{font-weight:700; width:12%}
.az td:nth-child(2){white-space:nowrap; color:var(--blue); font-weight:700; width:5%; font-size:7pt}

/* ---- code & formulas ---- */
pre.code{font-family:var(--mono); font-size:7.3pt; line-height:1.28; background:var(--code-bg);
  border:0.5pt solid var(--rule); padding:4pt 6pt; margin:4pt 0 5pt; white-space:pre-wrap;
  page-break-inside:avoid; overflow-wrap:break-word}
pre.code code{font-size:inherit}
.formula{background:#FFF; border:0.75pt solid var(--blue); padding:5pt 8pt 2pt; margin:5pt 0 6pt; page-break-inside:avoid}
.formula .lbl{display:block; font-weight:700; color:var(--blue); font-size:8.4pt; margin-bottom:2pt}
.formula .eq{font-family:var(--mono); font-size:9pt; text-align:center; background:var(--code-bg);
  padding:4pt; margin:0 0 4pt}
figure.fig{margin:5pt 0; page-break-inside:avoid; text-align:center}
figure.fig figcaption{font-size:7.6pt; color:var(--muted); margin-top:3pt}
figure.fig svg{max-width:100%; height:auto}
.quad{display:grid; grid-template-columns:auto 1fr 1fr; gap:2pt; font-size:7.6pt; max-width:3.6in; margin:4pt 0}
.quad div{padding:4pt 3pt; text-align:center}
.q-lo{background:#CFE3D6}.q-md{background:#F1E6C8}.q-hi{background:#EFCACA}
.gantt{display:flex; border:0.6pt solid var(--blue); font-size:7.6pt; margin:4pt 0}
.gantt span{flex:1 0 auto; padding:3pt 6pt; border-right:0.6pt solid var(--blue); text-align:center}
.gantt span:last-child{border-right:0}
.legend{display:grid; grid-template-columns:1fr 1fr; gap:0 9pt}

/* ---- contents ---- */
.toc ol{list-style:none; padding:0; margin:0; font-size:8.4pt}
.toc > ol{columns:2; column-gap:22pt}
.toc li{margin:0; break-inside:avoid}
.toc .row{display:flex; align-items:baseline; gap:3pt}
.toc .row .t{white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.toc .row .dots{flex:1; border-bottom:0.5pt dotted #9AA6B6; transform:translateY(-2pt)}
.toc .row .p{font-variant-numeric:tabular-nums; color:var(--muted)}
.toc > ol > li > .row{font-weight:700; color:var(--navy); margin-top:5pt}
.toc ol ol .row{padding-left:9pt; color:var(--ink)}

/* ---- checklists ---- */
.checks{columns:2; column-gap:20pt; font-size:8.1pt}
.checks h3.chap{column-span:all; margin-top:10pt}
.checks ul{list-style:none; padding-left:11pt; margin:0 0 6pt}
.checks li{margin:0 0 2pt; break-inside:avoid; position:relative}
.checks li::before{content:"\25A1"; position:absolute; left:-11pt; color:var(--blue)}
"""

JS = r"""
(function(){
  var main = document.getElementById('content');
  var PAGES = PAGEMAP;

  function moveTo(host, node){ host.appendChild(node); }

  var chapters = [], breaths = [], glossRows = [], checklists = [], formulaSection = null;

  main.querySelectorAll(':scope > section').forEach(function(sec){
    if (sec.id === 'how') { sec.remove(); return; }
    var plate = sec.querySelector(':scope > .plate');
    var code = '', title = sec.id;
    if (plate) {
      var n = plate.querySelector('.num'), t = plate.querySelector('.ttl');
      code = n ? n.textContent.trim() : '';
      if (t) title = t.textContent.replace(/\s+/g, ' ').trim();
      plate.remove();
    }
    if (sec.id === 'formulas') { formulaSection = { sec: sec, title: title }; return; }

    var ch = { id: sec.id, code: code, label: code + ' — ' + title, key: title, sections: [] };

    // The lecture header replaces the big plate.
    var h = document.createElement('h3');
    h.className = 'chap';
    h.id = sec.id;
    h.innerHTML = '<span class="lec"></span>';
    h.querySelector('.lec').textContent = code;
    h.appendChild(document.createTextNode(title));
    sec.insertBefore(h, sec.firstChild);

    // Recaps of earlier chapters are the one thing a reference does not need.
    sec.querySelectorAll('.box.bg').forEach(function(b){ b.remove(); });

    // Keep each chapter's checklist, but file it at the back; drop practice Q&A.
    sec.querySelectorAll('.box.exam').forEach(function(b){
      b.querySelectorAll('details').forEach(function(d){ d.remove(); });
      var list = b.querySelector('ul.checklist');
      if (list) checklists.push({ code: code, title: title, list: list });
      b.remove();
    });

    // The one-breath summary becomes Part I.
    sec.querySelectorAll('.box.proc').forEach(function(b){
      var l = b.querySelector(':scope > .lbl');
      if (l && /in one breath/i.test(l.textContent)) {
        breaths.push({ code: code, title: title, html: b.innerHTML.replace(/<span class="lbl">[\s\S]*?<\/span>/, '') });
        b.remove();
      }
    });

    // Glossaries merge into one A-Z table at the back.
    sec.querySelectorAll('table.gloss').forEach(function(t){
      t.querySelectorAll('tbody tr').forEach(function(tr){
        var c = tr.children;
        if (c.length < 2) return;
        glossRows.push({ term: c[0].textContent.trim(), code: code,
          def: c[1] ? c[1].innerHTML : '', ex: c[2] ? c[2].innerHTML : '',
          sim: c[4] ? c[4].textContent.trim() : '', opp: c[5] ? c[5].textContent.trim() : '' });
      });
      var wrap = t.closest('.tw') || t;
      var head = wrap.previousElementSibling;
      if (head && /^H3$/i.test(head.tagName) && /glossary/i.test(head.textContent)) head.remove();
      wrap.remove();
    });

    // Headings: number them and record for the contents page.
    var n = chapters.length + 1, m = 0;
    sec.querySelectorAll(':scope > h3').forEach(function(h3){
      if (h3.classList.contains('chap')) return;
      var t = h3.textContent.replace(/\s+/g, ' ').trim();
      var h4 = document.createElement('h4');
      h4.className = 'sec';
      h4.id = h3.id || (sec.id + '-s' + (m + 1));
      h4.innerHTML = '<span class="n">' + n + '.' + (++m) + '</span>';
      h4.appendChild(document.createTextNode(t));
      h3.replaceWith(h4);
      ch.sections.push({ id: h4.id, label: n + '.' + m + '  ' + t, key: t });
    });
    sec.querySelectorAll('h4:not(.sec)').forEach(function(h){
      var h5 = document.createElement('h5');
      h5.innerHTML = h.innerHTML;
      h.replaceWith(h5);
    });
    chapters.push(ch);
  });

  // Panel labels and definition lists, same conventions as the study guide.
  main.querySelectorAll('.box').forEach(function(b){
    var l = b.querySelector(':scope > .lbl');
    if (l) {
      var f = l.firstChild;
      if (f && f.nodeType === 3) f.textContent = f.textContent.replace(/^(Definition|Process|Worked examples?|Background)\s*:\s*/i, function(_, w){ return w + ' — '; });
      if (b.classList.contains('warn') && /^misconceptions?\s*:?$/i.test(l.textContent.trim())) l.textContent = 'Watch out';
      l.innerHTML = l.innerHTML.replace(/^Misconception\s*:\s*/i, 'Watch out — ');
    }
    var dl = b.querySelector(':scope > dl');
    if (dl) {
      var wrap = document.createElement('div'); wrap.className = 'dl';
      var names = { 'plain english': 'Plain English:', 'technical': 'Technical:', 'why it matters': 'Why it matters:' };
      dl.querySelectorAll('dt').forEach(function(dt){
        var dd = dt.nextElementSibling, p = document.createElement('p');
        var key = dt.textContent.trim().toLowerCase();
        p.innerHTML = '<b>' + (names[key] || dt.textContent.trim() + ':') + '</b> ' + (dd ? dd.innerHTML : '');
        wrap.appendChild(p);
      });
      dl.replaceWith(wrap);
    }
    b.querySelectorAll('details').forEach(function(d){ d.open = true; });
  });
  main.querySelectorAll('.tool').forEach(function(t){ t.remove(); });
  // Anything too wide for a 3.4in column gets the full measure back.
  main.querySelectorAll('.tw').forEach(function(w){
    var r = w.querySelector('tr');
    if (r && r.children.length > 3) w.classList.add('span');
  });
  main.querySelectorAll('figure.fig').forEach(function(f){ f.classList.add('span'); });
  main.querySelectorAll('pre.code').forEach(function(c){
    var longest = 0;
    c.textContent.split('\n').forEach(function(l){ if (l.length > longest) longest = l.length; });
    if (longest > 62) c.classList.add('span');
  });
  main.querySelectorAll('.formula > .lbl').forEach(function(l){
    l.removeAttribute('style');
    l.textContent = l.textContent.replace(/^Formula:\s*/, 'Formula — ');
  });

  // ---- Part I: the one-breath summaries ----
  var p1 = document.getElementById('part-breath');
  breaths.forEach(function(b){
    var d = document.createElement('div');
    d.className = 'breath';
    d.innerHTML = '<span class="lbl"></span>' + b.html;
    d.querySelector('.lbl').textContent = b.code + ' — ' + b.title;
    p1.appendChild(d);
  });

  // ---- Part II: formulas ----
  var p2 = document.getElementById('part-formula');
  if (formulaSection) { while (formulaSection.sec.firstChild) moveTo(p2, formulaSection.sec.firstChild); formulaSection.sec.remove(); }

  // ---- Part IV: merged A-Z glossary ----
  var seen = {}, rows = [];
  glossRows.forEach(function(r){
    var k = r.term.toLowerCase() + '|' + r.code;
    if (seen[k]) return;
    seen[k] = 1; rows.push(r);
  });
  rows.sort(function(a, b){ return a.term.toLowerCase().localeCompare(b.term.toLowerCase()); });
  var body = document.getElementById('az-body');
  rows.forEach(function(r){
    var tr = document.createElement('tr');
    var rel = [r.sim, r.opp].filter(function(x){ return x && x !== '—'; }).join(' / ');
    tr.innerHTML = '<td></td><td></td><td>' + r.def + '</td><td>' + r.ex + '</td><td>' + rel + '</td>';
    tr.children[0].textContent = r.term;
    tr.children[1].textContent = r.code;
    body.appendChild(tr);
  });
  document.getElementById('az-count').textContent = rows.length;

  // ---- Part V: checklists ----
  var p5 = document.getElementById('part-checks');
  checklists.forEach(function(c){
    var h = document.createElement('h3');
    h.className = 'chap';
    h.innerHTML = '<span class="lec"></span>';
    h.querySelector('.lec').textContent = c.code;
    h.appendChild(document.createTextNode(c.title));
    p5.appendChild(h);
    p5.appendChild(c.list);
  });

  // ---- contents ----
  var toc = document.getElementById('toc-list');
  chapters.forEach(function(ch){
    var li = document.createElement('li');
    li.innerHTML = '<div class="row" data-for="' + ch.id + '"><span class="t"></span><span class="dots"></span><span class="p">00</span></div><ol></ol>';
    li.querySelector('.t').textContent = ch.label;
    var ol = li.querySelector('ol');
    ch.sections.forEach(function(s){
      var sl = document.createElement('li');
      sl.innerHTML = '<div class="row" data-for="' + s.id + '"><span class="t"></span><span class="dots"></span><span class="p">00</span></div>';
      sl.querySelector('.t').textContent = s.label;
      ol.appendChild(sl);
    });
    toc.appendChild(li);
  });
  toc.querySelectorAll('.row').forEach(function(r){ var p = PAGES[r.getAttribute('data-for')]; if (p) r.querySelector('.p').textContent = p; });

  // Cross-references get a page number; the placeholder keeps both passes the same width.
  document.querySelectorAll('#content a[href^="#"], #part-breath a[href^="#"]').forEach(function(a){
    var p = PAGES[a.getAttribute('href').slice(1)];
    a.className = 'xref';
    var tag = document.createElement('span');
    tag.className = 'pg';
    tag.textContent = ' (p. ' + (p || '000') + ')';
    a.appendChild(tag);
  });

  window.__headings = [].concat.apply([], chapters.map(function(c){ return [{id:c.id,label:c.label,key:c.key}].concat(c.sections); }));
  document.getElementById('heading-data').textContent = JSON.stringify(window.__headings);

  if (window.mermaid) {
    mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' });
    mermaid.run({ querySelector: 'pre.mermaid' });
  }
})();
"""


def build_html(course, guide, notes_main, pagemap, fonts_url):
    esc = html.escape
    css = CSS.replace("FONTS", fonts_url).replace('"HEADER"', json.dumps(guide["header"], ensure_ascii=False))
    js = JS.replace("PAGEMAP", json.dumps(pagemap))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(course['code'])} Exam Reference</title>
<style>{css}</style></head><body>
<div class="cover">
  <p class="t">{esc(guide['cover_title'])}</p>
  <p class="s">Open-Book Exam Reference</p>
  <p class="c">{esc(guide['cover_course'])}</p>
  <p class="r">{esc(guide['cover_range'])}</p>
  <div class="how">
    <p><b>How to use this under time pressure.</b></p>
    <p><b>Part I</b> is the whole course in one paragraph per lecture. Read it first; it will usually tell you
    which lecture a question belongs to.</p>
    <p><b>Part II</b> is every formula on one spread.</p>
    <p><b>Part III</b> is the reference proper, in lecture order: every definition, procedure, table, code
    listing, figure walkthrough, worked example and trap. Blue&nbsp;= definitions, gray&nbsp;= procedures and
    figures, green&nbsp;= worked examples, amber&nbsp;= the mistake to avoid.</p>
    <p><b>Part IV</b> is one A–Z glossary merged from all lectures, tagged with the lecture each term came
    from. <b>Start here when you meet a term you don't recognise.</b></p>
    <p><b>Part V</b> is every exam checklist, so you can confirm you can actually do the thing.</p>
  </div>
</div>

<div class="toc"><h2 class="part" style="page-break-before:avoid">Contents</h2><ol id="toc-list"></ol></div>

<h2 class="part">Part I <span>The whole course, one paragraph per lecture</span></h2>
<div id="part-breath"></div>

<h2 class="part">Part II <span>Formula sheet</span></h2>
<div id="part-formula"></div>

<h2 class="part">Part III <span>A&#8211;Z glossary, all lectures merged (<span id="az-count">0</span> terms)</span></h2>
<div class="tw"><table class="az">
  <thead><tr><th style="width:11%">Term</th><th style="width:5%">Lec.</th><th style="width:34%">Definition</th><th style="width:25%">Example</th><th style="width:25%">Similar / opposite</th></tr></thead>
  <tbody id="az-body"></tbody>
</table></div>

<h2 class="part">Part IV <span>Exam checklists</span></h2>
<div class="checks" id="part-checks"></div>

<h2 class="part">Part V <span>Full reference, in lecture order</span></h2>
<main id="content">{notes_main}</main>

<script type="application/json" id="heading-data"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>{js}</script>
</body></html>"""


def render(html_text, out_pdf, workdir):
    src = pathlib.Path(workdir) / "sheet.html"
    src.write_text(html_text)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--allow-file-access-from-files", "--virtual-time-budget=20000",
                    f"--print-to-pdf={out_pdf}", src.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def dump_headings(html_text, workdir):
    src = pathlib.Path(workdir) / "probe.html"
    src.write_text(html_text)
    out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                          "--virtual-time-budget=5000", "--dump-dom", src.as_uri()],
                         check=True, capture_output=True, text=True).stdout
    data = re.search(r'<script type="application/json" id="heading-data">(.*?)</script>', out, re.S).group(1)
    return json.loads(html.unescape(data))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_pages(pdf, headings):
    count = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    pages = [norm(subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True).stdout)
             for i in range(1, count + 1)]
    # The numbered sections live in Part V. Search only there: the glossary and the
    # checklists repeat section wording, and one late match would strand every
    # heading after it.
    start = min(i for i, p in enumerate(pages) if "fullreferenceinlectureorder" in p)
    result, cur = {}, start
    for h in headings:
        # The lecture code and section number are separate text runs, so the full
        # label may not survive extraction; fall back to the bare title.
        keys = [norm(h["label"])[:36]]
        if h.get("key"):
            keys.append(norm(h["key"])[:36])
        for key in keys:
            hit = next((i for i in range(cur, len(pages)) if key in pages[i]), None)
            if hit is not None:
                result[h["id"]] = hit + 1
                cur = hit
                break
    return result, count


def main():
    cid, out = sys.argv[1], pathlib.Path(sys.argv[2]).expanduser()
    course = next(c for c in json.loads((ROOT / "courses/courses.json").read_text()) if c["id"] == cid)
    guide = json.loads((ROOT / "courses" / cid / "guide.json").read_text())
    notes = (ROOT / "courses" / cid / "notes.html").read_text()
    main_html = re.search(r'<template data-part="main">(.*?)</template>', notes, re.S).group(1)
    fonts = WORD_FONTS.as_uri() if WORD_FONTS.exists() else ""
    with tempfile.TemporaryDirectory() as tmp:
        first = build_html(course, guide, main_html, {}, fonts)
        headings = dump_headings(first, tmp)
        draft = pathlib.Path(tmp) / "draft.pdf"
        render(first, draft, tmp)
        pagemap, count = find_pages(str(draft), headings)
        missing = [h["label"] for h in headings if h["id"] not in pagemap]
        render(build_html(course, guide, main_html, pagemap, fonts), out, tmp)
    print(f"{out}: {count} pages, {len(headings)} headings, {len(missing)} without a page number")
    for m in missing:
        print("  missing:", m)


if __name__ == "__main__":
    main()
