#!/usr/bin/env python3
"""Convert the CSC 4320 "Complete Exam Study Notes" PDF into a notes fragment
that uses the same markup vocabulary as the ITEC 4235 page (box def/ex/warn/exam,
plates, .tw tables, pre.code).

Usage:
  pdftohtml -xml -i -q OS_Study_Guide_1-11.pdf os      # produces os.xml
  python3 tools/pdf_notes_to_html.py os.xml courses/csc4320/notes.html

Layout rules were read off this specific PDF (font ids, left margins, gaps), so
treat this as a one-off importer, not a general PDF converter.
"""
import copy
import html
import re
import sys
from xml.etree import ElementTree as ET

CONSOLAS = {"32", "36", "37", "40"}
TABLE_HEAD = {"28", "41"}
TABLE_BODY = {"29", "33", "45", "46", "48"}
H2_FONTS = {"13", "23"}          # chapter titles
H3_FONTS = {"24", "34"}          # "1.1  Section"
H4_FONTS = {"35", "38", "15", "30"}
LABEL_FONTS = {"16", "17", "19", "44", "20", "21", "43"}


def esc(s):
    return html.escape(s, quote=False)


class Chunk:
    def __init__(self, e):
        self.top = int(e.get("top"))
        self.left = int(e.get("left"))
        self.width = int(e.get("width"))
        self.font = e.get("font")
        self.text = "".join(e.itertext())
        self.bold = e.find(".//b") is not None
        self.italic = e.find(".//i") is not None
        self.code = self.font in CONSOLAS


class Line:
    def __init__(self, page, chunks):
        self.page = page
        self.chunks = sorted(chunks, key=lambda c: c.left)
        self.top = min(c.top for c in chunks if c.font not in CONSOLAS) if any(
            c.font not in CONSOLAS for c in chunks) else min(c.top for c in chunks) - 4
        real = [c for c in self.chunks if c.text.strip()]
        self.real = real
        self.left = real[0].left if real else self.chunks[0].left
        self.fonts = {c.font for c in real}
        self.text = "".join(c.text for c in self.chunks)

    def only(self, fonts):
        return bool(self.real) and all(c.font in fonts for c in self.real)


def load_lines(path):
    root = ET.parse(path).getroot()
    lines = []
    for page in root.iter("page"):
        n = int(page.get("number"))
        if n < 4:
            continue
        chunks = [Chunk(e) for e in page.iter("text")]
        chunks = [c for c in chunks if 75 <= c.top <= 1105]
        chunks.sort(key=lambda c: (c.top, c.left))
        groups = []
        for c in chunks:
            # inline code sits ~4px lower than the surrounding text
            for g in groups:
                if abs(g[0].top - c.top) <= 6 or (c.font in CONSOLAS and 0 < c.top - g[0].top <= 6):
                    g.append(c)
                    break
            else:
                groups.append([c])
        for g in groups:
            ln = Line(n, g)
            if ln.real:
                lines.append(ln)
    lines.sort(key=lambda l: (l.page, l.top))
    return lines


def inline(chunks):
    """Render chunks with <strong>/<em>/<code>, merging runs of the same style."""
    out, cur, buf = [], None, ""
    for c in chunks:
        style = ("code" if c.code else "") + ("b" if c.bold and not c.code else "") + ("i" if c.italic and not c.code else "")
        if style != cur:
            out.append((cur, buf))
            cur, buf = style, ""
        buf += c.text
    out.append((cur, buf))
    html_parts = []
    for style, text in out:
        if not text:
            continue
        if not style or not text.strip():
            html_parts.append(esc(text))
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        core = esc(text.strip())
        if "code" in style:
            core = "<code>" + core + "</code>"
        else:
            if "i" in style:
                core = "<em>" + core + "</em>"
            if "b" in style:
                core = "<strong>" + core + "</strong>"
        html_parts.append(esc(lead) + core + esc(trail))
    return "".join(html_parts)


def join_inline(parts):
    s = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # a word hyphenated across a line break keeps its hyphen but loses the space
        s += p if (not s or re.search(r"[A-Za-z0-9]-(</strong>|</em>)*$", s)) else " " + p
    s = re.sub(r"\s+", " ", s)
    s = s.replace("</strong> <strong>", " ").replace("</em> <em>", " ").replace("</code> <code>", " ")
    return s.strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def label_kind(text):
    t = text.strip()
    u = t.upper()
    if u.startswith("DEFINITION"):
        return "def", "Definition" + t[len("DEFINITION"):].replace(" — ", ": ", 1).replace(" —", ":", 1)
    if u.startswith("WORKED EXAMPLE"):
        rest = t[len("WORKED EXAMPLE"):].strip(" —")
        return "ex", "Worked example" + (": " + rest if rest else "")
    if u.startswith("COMMON MISCONCEPTION"):
        return "warn", "Misconception"
    if u.startswith("EXAM WATCH"):
        rest = t[len("EXAM WATCH"):].strip(" —")
        return "exam", "Exam watch" + (": " + rest if rest else "")
    if "IN ONE BREATH" in u:
        return "proc", t.title().replace("In One Breath", "in one breath")
    if u.startswith("KEY IDEA"):
        return "proc", "Key idea"
    if "IN ONE LINE" in u:
        return "proc", t.capitalize()
    if "REVIEW" in u:
        return "bg", t[0] + t[1:].lower().replace("—", "—")
    return None, t


def is_label(ln):
    if ln.left not in range(120, 131):
        return False
    first = ln.real[0]
    if first.font not in LABEL_FONTS:
        return False
    kind, _ = label_kind(ln.text)
    return kind is not None


def code_text(block):
    base = min(c.left for ln in block for c in ln.real)
    rows = []
    for ln in block:
        row = ""
        for c in ln.chunks:
            if not c.text:
                continue
            cw = c.width / max(len(c.text), 1)
            col = max(0, round((c.left - base) / (cw or 7.8)))
            if len(row) < col:
                row += " " * (col - len(row))
            row += c.text
        rows.append(row.rstrip())
    return "\n".join(rows)


def convert(lines):
    out = []          # html strings for main
    toc = []          # (chapter_id, number, title, [(id, title)])
    i = 0
    n = len(lines)
    chapter_open = False
    box = None        # dict(kind, label, items, lastline)
    last_table_header = None
    last_table = None

    def gap(a, b):
        if a is None:
            return 999
        if a.page != b.page:
            return -1  # page break: undetermined
        return b.top - a.top

    def close_box():
        nonlocal box
        if box:
            out.append(render_box(box))
            box = None

    def emit(htmlstr):
        if box is not None:
            box["items"].append(htmlstr)
        else:
            out.append(htmlstr)

    prev = None
    para = []           # accumulating inline parts
    para_last = None
    listbuf = None      # dict(type, items)

    def flush_para():
        nonlocal para, para_last
        if para:
            emit("<p>" + join_inline(para) + "</p>")
        para, para_last = [], None

    def flush_list():
        nonlocal listbuf
        if listbuf:
            tag = listbuf["type"]
            emit("<%s>%s</%s>" % (tag, "".join("<li>" + join_inline(it) + "</li>" for it in listbuf["items"]), tag))
        listbuf = None

    def flush_all():
        flush_para()
        flush_list()

    while i < n:
        ln = lines[i]
        # ---------- chapter title
        if ln.fonts & H2_FONTS:
            flush_all(); close_box()
            if chapter_open:
                out.append("</section>")
            m = re.match(r"Chapter\s+(\d+)\s*—\s*(.*)", ln.text.strip())
            num, title = m.group(1), m.group(2).strip()
            cid = "ch%s" % num
            toc.append([cid, num, title, []])
            out.append('<section class="lecture prose" id="%s">' % cid)
            out.append('<div class="plate"><span class="num" aria-hidden="true">%s</span><p class="ttl">%s</p><p class="src">Chapter %s</p></div>' % (num.zfill(2), esc(title), num))
            chapter_open = True
            prev = ln; i += 1; continue
        # ---------- section heading
        if ln.fonts & H3_FONTS and ln.left < 115:
            flush_all(); close_box()
            t = re.sub(r"\s+", " ", ln.text).strip()
            m = re.match(r"(\d+\.\d+)\s+(.*)", t)
            sid = "s" + m.group(1).replace(".", "-") if m else slug(t)
            title = m.group(2) if m else t
            toc[-1][3].append((sid, (m.group(1) + " " if m else "") + title))
            out.append('<h3 id="%s"><span class="secnum">%s</span> %s</h3>' % (sid, m.group(1) if m else "", esc(title)))
            prev = ln; i += 1; continue
        # ---------- panel label
        if is_label(ln):
            flush_all(); close_box()
            kind, label = label_kind(re.sub(r"\s+", " ", ln.text))
            box = {"kind": kind, "label": label, "items": []}
            prev = ln; i += 1; continue
        # ---------- decide whether a box ends
        if box is not None:
            g = gap(prev, ln)
            ends = False
            if g > 45:
                ends = True
            if ln.left < 116 and not (ln.fonts & TABLE_HEAD or ln.fonts & TABLE_BODY):
                ends = True
            if g == -1 and ln.left >= 117 and not (ln.fonts & TABLE_HEAD):
                ends = False
            if ends:
                flush_all(); close_box()
        # ---------- h4 (only outside boxes)
        if box is None and ln.left < 115 and ln.only(H4_FONTS | {"2"}) and ln.real[0].font in H4_FONTS:
            flush_all()
            t = re.sub(r"\s+", " ", ln.text).strip()
            out.append("<h4>%s</h4>" % esc(t))
            prev = ln; i += 1; continue
        # ---------- table header
        if ln.only(TABLE_HEAD):
            header = [c for c in ln.real if c.text.strip()]
            # merge header fragments split by en dashes etc. into columns by gap
            cols = []
            for c in header:
                if cols and c.left - (cols[-1]["right"]) < 12:
                    cols[-1]["text"] += c.text
                    cols[-1]["right"] = c.left + c.width
                else:
                    cols.append({"left": c.left, "right": c.left + c.width, "text": c.text})
            htexts = [re.sub(r"\s+", " ", c["text"]).strip() for c in cols]
            j = i + 1
            if j >= n or not lines[j].only(TABLE_BODY):
                if last_table_header == htexts and ln.top < 130:
                    i += 1; continue   # header repeated on a new page; keep prev so paragraphs continue
                flush_all()
                # a Gantt chart: header-only strip
                emit('<div class="gantt">%s</div>' % "".join('<span>%s</span>' % esc(t) for t in htexts))
                prev = ln; i += 1; continue
            flush_all()
            starts = [c["left"] for c in cols]
            body_min = min((c.left for bl in lines[i + 1:i + 4] if bl.only(TABLE_BODY) for c in bl.real), default=starts[0])
            if body_min < starts[0] - 10:
                starts.insert(0, body_min)
                htexts.insert(0, "")
            continuing = last_table_header == htexts and ln.top < 130 and last_table is not None
            rows = last_table["rows"] if continuing else []
            j = i + 1
            ptop = None
            while j < n and lines[j].only(TABLE_BODY):
                bl = lines[j]
                if ptop is None or bl.top - ptop > 21:
                    rows.append([[] for _ in starts])
                for c in bl.chunks:
                    if not c.text:
                        continue
                    k = max([idx for idx, s in enumerate(starts) if c.left + 4 >= s] or [0])
                    rows[-1][k].append(c)
                ptop = bl.top
                j += 1
            if not continuing:
                last_table = {"header": htexts, "rows": rows}
                token = "@@TABLE%d@@" % len(TABLES)
                last_table["token"] = token
                TABLES.append(last_table)
                emit(token)
            last_table_header = htexts
            prev = lines[j - 1]; i = j; continue
        # ---------- code block
        if ln.only(CONSOLAS) and ln.real[0].left in (121, 138, 125) and (ln.fonts & {"37", "40"} or (ln.fonts == {"32"}) or len(ln.real) == 1 and ln.left in (121, 138) ):
            flush_all()
            block = [ln]
            j = i + 1
            while j < n and lines[j].only(CONSOLAS) and lines[j].left >= ln.left - 2 and (lines[j].page != block[-1].page or lines[j].top - block[-1].top <= 40):
                block.append(lines[j]); j += 1
            # a code block that runs across a page break
            while j < n and lines[j].page != block[-1].page and lines[j].only(CONSOLAS) and lines[j].left in (121, 138):
                block.append(lines[j]); j += 1
                while j < n and lines[j].only(CONSOLAS) and lines[j].page == block[-1].page and lines[j].top - block[-1].top <= 22:
                    block.append(lines[j]); j += 1
            emit('<pre class="code"><code>%s</code></pre>' % esc(code_text(block)))
            prev = block[-1]; i = j; continue
        # ---------- bullets
        first = ln.real[0]
        bullet_text = first.text.lstrip()
        if first.text.strip() == "•" or bullet_text.startswith("• "):
            flush_para()
            if listbuf is None or listbuf["type"] != "ul":
                flush_list(); listbuf = {"type": "ul", "items": []}
            chunks = list(ln.chunks)
            if first.text.strip() == "•":
                chunks = [c for c in chunks if c is not first]
            else:
                idx = chunks.index(first)
                c2 = copy.copy(first); c2.text = bullet_text[2:]
                chunks[idx] = c2
            listbuf["items"].append([inline(chunks)])
            prev = ln; i += 1; continue
        if re.fullmatch(r"\d+\.", first.text.strip()) and ln.left < 125:
            flush_para()
            if listbuf is None or listbuf["type"] != "ol":
                flush_list(); listbuf = {"type": "ol", "items": []}
            listbuf["items"].append([inline([c for c in ln.chunks if c is not first])])
            prev = ln; i += 1; continue
        # continuation of a list item (indented, small gap)
        if listbuf is not None:
            g = gap(prev, ln)
            if (ln.left in range(133, 170) and (0 < g <= 25 or g == -1)) or (
                    box is not None and ln.left in range(120, 131) and 0 < g <= 25):
                listbuf["items"][-1].append(inline(ln.chunks))
                prev = ln; i += 1; continue
            flush_list()
        # ---------- definition sub-labels
        if box is not None and box["kind"] == "def" and first.font == "18" and first.text.strip().endswith(":"):
            flush_para()
            box["items"].append(("dt", first.text.strip().rstrip(":")))
            para = [inline([c for c in ln.chunks if c is not first])]
            para_last = ln
            prev = ln; i += 1; continue
        # ---------- paragraphs
        g = gap(prev, ln)
        if para:
            cont = 0 < g <= 26
            if g == -1:
                last = re.sub(r"<[^>]+>", "", para[-1]).rstrip()
                cont = bool(last) and (last[-1] not in ".:!?)" or ln.text.strip()[:1].islower())
            if not cont:
                flush_para()
        para.append(inline(ln.chunks))
        para_last = ln
        prev = ln; i += 1
    flush_all(); close_box()
    if chapter_open:
        out.append("</section>")
    body = "\n".join(x if isinstance(x, str) else "" for x in out)
    return body, toc


TABLES = []


def render_table(t):
    head = "".join("<th>%s</th>" % esc(h) for h in t["header"])
    body = []
    for r in t["rows"]:
        cells = []
        for cell in r:
            # keep chunk order: by top then left
            cell.sort(key=lambda c: (c.top, c.left))
            parts, ptop = [], None
            for c in cell:
                if ptop is not None and c.top - ptop > 4:
                    parts.append(" ")
                parts.append(c)
                ptop = c.top
            txt = ""
            buf = []
            for p in parts:
                if p == " ":
                    txt += inline(buf) + " "; buf = []
                else:
                    buf.append(p)
            txt += inline(buf)
            cells.append("<td>%s</td>" % re.sub(r"\s+", " ", txt).strip())
        body.append("<tr>%s</tr>" % "".join(cells))
    return '<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, "".join(body))


def render_box(box):
    parts = ['<div class="box %s"><span class="lbl">%s</span>' % (box["kind"], esc(box["label"]))]
    items = box["items"]
    if box["kind"] == "def":
        dl, rest = [], []
        k = 0
        while k < len(items):
            it = items[k]
            if isinstance(it, tuple) and it[0] == "dt":
                name = {"In plain English": "Plain English", "Technical definition": "Technical", "Why it matters": "Why it matters"}.get(it[1], it[1])
                dd = items[k + 1] if k + 1 < len(items) else ""
                dd = re.sub(r"^<p>|</p>$", "", dd)
                dl.append("<dt>%s</dt><dd>%s</dd>" % (esc(name), dd))
                k += 2
            else:
                rest.append(it); k += 1
        if dl:
            parts.append("<dl>%s</dl>" % "".join(dl))
        parts.extend(r for r in rest if isinstance(r, str))
    else:
        parts.extend(it for it in items if isinstance(it, str))
    parts.append("</div>")
    return "".join(parts)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    lines = load_lines(src)
    body, toc = convert(lines)
    tables = TABLES
    for t in tables:
        body = body.replace(t["token"], render_table(t))
    toc_html = "".join(
        '<li><a href="#%s"><span class="code">Ch%s</span>%s</a><ol>%s</ol></li>' % (
            cid, num, esc(title), "".join('<li><a href="#%s">%s</a></li>' % (sid, esc(st)) for sid, st in secs))
        for cid, num, title, secs in toc)
    with open(dst, "w") as f:
        f.write('<template data-part="toc"><ol>%s</ol></template>\n' % toc_html)
        f.write('<template data-part="main">\n%s\n</template>\n' % body)
    print("chapters:", len(toc), "sections:", sum(len(t[3]) for t in toc), "tables:", len(tables))


if __name__ == "__main__":
    main()
