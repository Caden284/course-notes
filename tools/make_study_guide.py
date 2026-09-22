#!/usr/bin/env python3
"""Render a course's notes as a printable "Complete Exam Study Notes" PDF in the
style of the CSC 4320 guide: cover, how-to-use page, table of contents with page
numbers, colored panels, running header and footer.

Usage:
  python3 tools/make_study_guide.py itec4235 ~/Downloads/ITEC4235_Study_Guide.pdf

Reads courses/<id>/notes.html and courses/<id>/guide.json (cover text and study
order). Needs Google Chrome and poppler (pdftotext). Two passes: the first
finds which page each heading lands on, the second fills in the contents page.
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
@font-face{font-family:"GCambria";src:url("FONTS/Cambriaz.ttf");font-weight:700;font-style:italic}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibri.ttf");font-weight:400;font-style:normal}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibrib.ttf");font-weight:700;font-style:normal}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibrii.ttf");font-weight:400;font-style:italic}
@font-face{font-family:"GCalibri";src:url("FONTS/Calibriz.ttf");font-weight:700;font-style:italic}
@font-face{font-family:"GConsolas";src:url("FONTS/Consola.ttf");font-weight:400}
@font-face{font-family:"GConsolas";src:url("FONTS/Consolab.ttf");font-weight:700}
:root{
  --navy:#16233F; --blue:#1F6FC5; --ink:#1A1A2D; --muted:#49495A;
  --def-bg:#E2ECF7; --def:#1F5FA8; --ex-bg:#E4EFE7; --ex:#2C6D48;
  --warn-bg:#FBF1DA; --warn:#B8850A; --exam-bg:#F7E1E1; --exam:#9B2125;
  --key-bg:#ECEFF5; --key:#16233F; --code-bg:#F1F3F5; --rule:#C9D2DE;
  --serif:"GCambria", Cambria, Caladea, Georgia, serif;
  --sans:"GCalibri", Calibri, Carlito, "Helvetica Neue", Arial, sans-serif;
  --mono:"GConsolas", Consolas, Menlo, monospace;
}
@page{
  size:Letter; margin:0.9in 1in 0.85in 1in;
  @top-right{content:"HEADER"; font-family:var(--serif); font-style:italic; font-size:8pt; color:#49495A;
    vertical-align:bottom; padding-bottom:6pt; border-bottom:0.5pt solid #D4D8DE}
  @bottom-center{content:"改善  ·  Complete Exam Study Notes  ·  " counter(page); font-family:var(--serif);
    font-size:8pt; color:#49495A; vertical-align:top; padding-top:6pt; border-top:0.5pt solid #D4D8DE}
}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact; print-color-adjust:exact}
body{margin:0; font-family:var(--sans); font-size:11pt; line-height:1.48; color:var(--ink)}
p{margin:0 0 8pt} ul,ol{margin:0 0 8pt; padding-left:18pt} li{margin:0 0 3pt}
a{color:inherit; text-decoration:none}
strong{font-weight:700}
code,kbd{font-family:var(--mono); font-size:.86em; color:var(--ink)}
sub,sup{line-height:0}

/* cover */
.cover{text-align:center; padding-top:1.3in; page-break-after:always}
.cover .kanji{font-family:"Hiragino Mincho ProN", "MS Mincho", serif; font-size:54pt; color:var(--blue); margin:0 0 6pt}
.cover .t{font-family:var(--serif); font-weight:700; font-size:28pt; color:var(--ink); margin:0; letter-spacing:.5pt}
.cover .s{font-family:var(--serif); font-size:15pt; color:var(--def); margin:10pt 0 2pt}
.cover .c{font-size:11pt; color:var(--muted); margin:0}
.cover .r{font-weight:700; font-size:12pt; color:var(--blue); margin:26pt 0 6pt}
.cover .l{font-style:italic; font-size:9.5pt; color:var(--muted); margin:0 auto; max-width:6in}

/* chapter and section headings */
.chap{page-break-before:always; background:var(--navy); color:#fff; font-family:var(--serif); font-weight:700;
  font-size:19pt; line-height:1.2; margin:0 0 12pt; padding:5pt 6pt 4pt; border-bottom:3pt solid var(--blue)}
.chap .code{font-weight:400; font-size:12pt; color:#C9D6EA; margin-left:4pt}
h3{font-family:var(--serif); font-weight:700; font-size:14.5pt; color:var(--navy); margin:16pt 0 7pt;
  padding-bottom:2pt; border-bottom:0.75pt solid var(--def); break-after:avoid}
h3 .n{margin-right:8pt}
h4{font-family:var(--serif); font-weight:700; font-size:12pt; color:var(--blue); margin:12pt 0 4pt; break-after:avoid}
h5{font-family:var(--serif); font-weight:700; font-size:11pt; color:var(--ink); margin:10pt 0 3pt; break-after:avoid}

/* panels */
.box{border-left:3.5pt solid var(--def); background:var(--def-bg); padding:8pt 11pt 4pt; margin:8pt 0 12pt; break-inside:avoid-page}
.box > .lbl{display:block; font-family:var(--serif); font-weight:700; font-size:10.5pt; text-transform:uppercase;
  letter-spacing:.2pt; margin:0 0 4pt; color:var(--def)}
.box > .lbl .lvl{text-transform:none; font-weight:400; font-style:italic; color:var(--muted); margin-left:4pt}
.box.def > .lbl{color:var(--key)}
.box.ex{border-color:var(--ex); background:var(--ex-bg)} .box.ex > .lbl{color:var(--ex)}
.box.warn{border-color:var(--warn); background:var(--warn-bg)} .box.warn > .lbl{color:var(--warn)}
.box.exam{border-color:var(--exam); background:var(--exam-bg)} .box.exam > .lbl{color:var(--exam)}
.box.proc,.box.bg,.box.tool{border-color:var(--key); background:var(--key-bg)} .box.proc > .lbl,.box.bg > .lbl,.box.tool > .lbl{color:var(--key)}
.box .dl p{margin:0 0 5pt} .box .dl b{color:var(--key)}
.box details{margin:0 0 7pt} .box summary{font-weight:700; list-style:none; margin:0 0 2pt} .box summary::-webkit-details-marker{display:none}
.box summary::before{content:"Q. "; color:var(--exam)}
.box details > div{padding:0 0 0 12pt; border-left:1.5pt solid #E3B7B8}
.box details > div::before{content:"A."; font-weight:700; color:var(--exam); display:block; margin-left:-12pt; float:left; width:12pt}
.legend{display:block} .legend .box{margin:0 0 10pt}
.checklist{list-style:none; padding-left:14pt} .checklist li{position:relative}
.checklist li::before{content:"☐"; position:absolute; left:-14pt; color:var(--exam)}

/* formulas */
.formula{border:0.75pt solid var(--rule); background:#F7F9FC; padding:8pt 11pt 4pt; margin:8pt 0 12pt; break-inside:avoid-page}
.formula > .lbl{display:block; font-family:var(--serif); font-weight:700; font-size:10.5pt; color:var(--navy) !important; text-transform:uppercase; margin:0 0 4pt}
.formula .eq{font-family:var(--mono); font-size:11pt; text-align:center; background:#fff; border:0.5pt solid var(--rule); padding:6pt; margin:0 0 7pt}

/* tables */
.tw{margin:6pt 0 12pt}
table{border-collapse:collapse; width:100%; font-size:9pt; line-height:1.35}
thead{display:table-header-group}
tr{break-inside:avoid}
th{background:var(--navy); color:#fff; font-family:var(--serif); font-weight:700; text-align:left; padding:4pt 6pt; border:0.5pt solid var(--navy)}
td{padding:3.5pt 6pt; border:0.5pt solid #D5DBE3; vertical-align:top}
tbody tr:nth-child(even) td{background:#F4F7FB}
td.num,th.num{text-align:right}
table.gloss{font-size:7.6pt} table.gloss td:first-child{font-weight:700}

/* code and figures */
pre.code{font-family:var(--mono); font-size:8.6pt; line-height:1.35; background:var(--code-bg); border:0.5pt solid #DDE2E8;
  padding:6pt 8pt; margin:6pt 0 10pt; white-space:pre-wrap; break-inside:avoid-page}
pre.code code{font-size:inherit}
figure.fig{margin:8pt 0 12pt; text-align:center; break-inside:avoid-page}
figure.fig pre.mermaid{margin:0; background:none}
figure.fig svg{max-width:100%; max-height:3.1in}
figure.fig figcaption{font-style:italic; font-size:9pt; color:var(--muted); margin-top:4pt}
.quad{display:grid; grid-template-columns:auto 1fr 1fr; gap:3pt; max-width:4.2in; font-size:9.5pt}
.quad div{padding:8pt 6pt; text-align:center}
.q-lo{background:#CFE3D6}.q-md{background:#F1E6C8}.q-hi{background:#EFCACA}

/* contents page */
.toc{page-break-after:always}
.toc ol{list-style:none; margin:0; padding:0}
.toc > ol > li{margin:0 0 5pt; break-inside:avoid}
.toc .row{display:flex; align-items:baseline; gap:4pt}
.toc .row .t{flex:0 1 auto}
.toc .row .dots{flex:1 1 auto; border-bottom:1pt dotted #9AA5B5; transform:translateY(-3pt); min-width:12pt}
.toc .row .p{flex:0 0 22pt; text-align:right; font-variant-numeric:tabular-nums}
.toc > ol > li > .row{font-family:var(--serif); font-weight:700; font-size:11.5pt; color:var(--navy); margin-top:6pt}
.toc ol ol{padding-left:16pt; font-size:10pt}
.toc ol ol li{margin:1pt 0}
"""

JS = r"""
(function(){
  var main = document.getElementById('content');
  var how = main.querySelector('section#how'); if (how) how.remove();
  var chapters = [];
  var n = 0;
  main.querySelectorAll('section.lecture').forEach(function(sec){
    var plate = sec.querySelector('.plate');
    var code = plate ? plate.querySelector('.num').textContent.trim() : '';
    var title = plate ? plate.querySelector('.ttl').textContent.trim() : sec.id;
    var appendix = sec.id === 'formulas';
    var label = appendix ? 'Appendix — ' + title : 'Chapter ' + (++n) + ' — ' + title;
    var h = document.createElement('h2'); h.className = 'chap'; h.id = 'chap-' + sec.id;
    h.textContent = label;
    if (!appendix && code) { var c = document.createElement('span'); c.className = 'code'; c.textContent = '(' + code + ')'; h.appendChild(c); }
    if (plate) plate.replaceWith(h); else sec.prepend(h);
    var ch = { id: h.id, label: label, sections: [] };
    var m = 0;
    sec.querySelectorAll('h3').forEach(function(h3){
      var t = h3.textContent.replace(/\s+/g, ' ').trim();
      var num = appendix ? '' : n + '.' + (++m);
      h3.innerHTML = (num ? '<span class="n">' + num + '</span>' : '') + h3.innerHTML;
      if (!h3.id) h3.id = sec.id + '-s' + m;
      ch.sections.push({ id: h3.id, label: (num ? num + '  ' : '') + t });
    });
    chapters.push(ch);
  });

  // panels
  main.querySelectorAll('.box').forEach(function(b){
    var l = b.querySelector(':scope > .lbl'); if (!l) return;
    var first = l.firstChild;
    if (first && first.nodeType === 3) first.textContent = first.textContent.replace(/^(Definition|Process|Worked examples?|Background|Exam practice)\s*:\s*/i, function(_, w){ return w + ' — '; });
    if (b.classList.contains('warn') && /^misconceptions?$/i.test(l.textContent.trim())) l.textContent = 'Common misconception';
    if (b.classList.contains('warn') && /^misconception\s*:/i.test(l.textContent.trim())) l.textContent = l.textContent.replace(/^misconception\s*:\s*/i, 'Common misconception — ');
    var dl = b.querySelector(':scope > dl');
    if (dl) {
      var wrap = document.createElement('div'); wrap.className = 'dl';
      var names = { 'plain english': 'In plain English:', 'technical': 'Technical definition:', 'why it matters': 'Why it matters:' };
      dl.querySelectorAll('dt').forEach(function(dt){
        var dd = dt.nextElementSibling; var p = document.createElement('p');
        var key = dt.textContent.trim().toLowerCase();
        p.innerHTML = '<b>' + (names[key] || dt.textContent.trim() + ':') + '</b> ' + (dd ? dd.innerHTML : '');
        wrap.appendChild(p);
      });
      dl.replaceWith(wrap);
    }
    b.querySelectorAll('details').forEach(function(d){ d.open = true; });
  });
  main.querySelectorAll('.tool').forEach(function(t){
    var name = (t.querySelector('.lbl') || {}).textContent || 'Interactive tool';
    var d = document.createElement('div'); d.className = 'box tool';
    d.innerHTML = '<span class="lbl"></span><p>TOOLNOTE</p>'; d.querySelector('.lbl').textContent = name.replace(/^Tool:\s*/, 'Tool — ');
    t.replaceWith(d);
  });
  main.querySelectorAll('.formula > .lbl').forEach(function(l){ l.removeAttribute('style'); l.textContent = l.textContent.replace(/^Formula:\s*/, 'Formula — '); });

  // contents
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
  var PAGES = PAGEMAP;
  toc.querySelectorAll('.row').forEach(function(r){ var p = PAGES[r.getAttribute('data-for')]; if (p) r.querySelector('.p').textContent = p; });
  window.__headings = [].concat.apply([], chapters.map(function(c){ return [{id:c.id,label:c.label}].concat(c.sections); }));
  document.getElementById('heading-data').textContent = JSON.stringify(window.__headings);

  if (window.mermaid) {
    mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict' });
    mermaid.run({ querySelector: 'pre.mermaid' });
  }
})();
"""


def build_html(course, guide, notes_main, pagemap, fonts_url):
    esc = html.escape
    lectures = re.findall(r'<p class="ttl">(.*?)</p>', notes_main)
    topics = " · ".join(html.unescape(t) for t in lectures)
    css = CSS.replace("FONTS", fonts_url).replace('"HEADER"', json.dumps(guide["header"], ensure_ascii=False))
    js = JS.replace("PAGEMAP", json.dumps(pagemap)).replace("TOOLNOTE", guide.get("tool_note", ""))
    legend = """
      <div class="box def"><span class="lbl">Definition — Term</span><div class="dl">
        <p><b>In plain English:</b> A one-sentence, jargon-free meaning you could say out loud.</p>
        <p><b>Technical definition:</b> The precise wording you would write on an exam.</p>
        <p><b>Why it matters:</b> Why the concept exists and where it shows up.</p></div></div>
      <div class="box ex"><span class="lbl">Worked example</span><p>Worked examples appear in green. They walk through a concrete problem step by step, usually from easy to hard.</p></div>
      <div class="box warn"><span class="lbl">Common misconception</span><p>Amber panels flag the wrong-but-tempting idea most students fall for, then correct it.</p></div>
      <div class="box exam"><span class="lbl">Exam watch</span><p>Red panels hold exam practice and each chapter's checklist: questions marked <b>Q.</b> with the answer under <b>A.</b></p></div>
      <div class="box proc"><span class="lbl">Process · Background · In one breath</span><p>Gray panels hold step-by-step procedures, prerequisite background, and each chapter's one-paragraph summary.</p></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(course['code'])} Study Guide</title>
<style>{css}</style></head><body>
<div class="cover">
  <p class="kanji">改善</p>
  <p class="t">{esc(guide['cover_title'])}</p>
  <p class="s">Complete Exam Study Notes</p>
  <p class="c">{esc(guide['cover_course'])}</p>
  <p class="r">{esc(guide['cover_range'])}</p>
  <p class="l">{esc(topics)}</p>
</div>
<div style="page-break-after:always">
  <h2 class="chap" style="page-break-before:auto">How to Use These Notes</h2>
  <p><strong>These notes teach the material; they do not just summarize the slides.</strong> Every bullet from lecture has been expanded into full explanation, every diagram described, and every formula worked through. Background your professor assumed you already knew is filled in. Read them like a textbook chapter, not a slide dump.</p>
  <h4>The colored panels</h4>
  <div class="legend">{legend}</div>
  <p>{guide['study_order']}</p>
</div>
<div class="toc"><h2 class="chap" style="page-break-before:auto">Table of Contents</h2><ol id="toc-list"></ol></div>
<main id="content">{notes_main}</main>
<script type="application/json" id="heading-data"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>{js}</script>
</body></html>"""


def render(html_text, out_pdf, workdir):
    src = pathlib.Path(workdir) / "guide.html"
    src.write_text(html_text)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--allow-file-access-from-files", "--virtual-time-budget=20000",
                    f"--print-to-pdf={out_pdf}", src.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def dump_headings(html_text, workdir):
    """Run the page's JS once and read back the heading list it computes."""
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
    # skip the cover, how-to, and contents pages: start after the last page mentioning "tableofcontents"
    start = max(i for i, p in enumerate(pages) if "tableofcontents" in p) + 1
    while start < len(pages) and norm(headings[0]["label"])[:30] not in pages[start]:
        start += 1
    result, cur = {}, start
    for h in headings:
        key = norm(h["label"])[:36]
        for i in range(cur, len(pages)):
            if key in pages[i]:
                result[h["id"]] = i + 1
                cur = i
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
