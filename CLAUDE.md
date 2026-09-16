# Course Notes site

Caden's study site: one page per class with rewritten notes, section search, and practice exams.

- Vercel (public, main URL): https://course-notes-pi.vercel.app (project caden284s-projects/course-notes, auto-deploys every push to `main`)
- GitHub Pages (public, backup): https://caden284.github.io/course-notes/
- Claude artifact (private, can generate new exams with Claude): https://claude.ai/artifact/61ZEo2PKHvYyGk7MT1Lda6

## After every change: rebuild, commit, push, republish

Caden wants every update pushed automatically, so do all four steps without asking:

1. `python3 build.py` (fails loudly if a question points at a missing section)
2. `git add -A && git commit -m "…"`
3. `git push` (Vercel and GitHub Pages both redeploy from `main` automatically within a minute; confirm with `npx vercel ls`)
4. Republish the artifact: Artifact tool with `file_path` = `index.html` and `url` = the artifact URL above. Read it first if this conversation hasn't published it. Omit `favicon` and `capabilities` so the stored ones (📚, `sample`) are kept.

## Layout

```
courses/courses.json        course list: id, code, title, term ("Fall 2026"), status, instructor, headline, lead, unitWord, examExclude
courses/<id>/notes.html     <template data-part="toc"><ol>…</ol></template> + <template data-part="main">…</template>
courses/<id>/questions.json [{unit, type: mc|tf|short, q, choices?, answer, explain}]
courses/<id>/tools.js       optional interactive widgets; defines initTools(), run after the notes render
site/shell.html             all CSS, the hash router, home page, and exam engine
index.html                  BUILD OUTPUT; never edit by hand
tools/pdf_notes_to_html.py  one-off importer used for the CSC 4320 PDF; don't re-run it (notes.html has hand edits since)
```

## Adding a class

Caden brings slides (PowerPoints/PDFs) or an existing notes document.

1. Add an entry to `courses/courses.json`. Use the next free id like `itec4400`; `term` must read `Spring|Summer|Fall YYYY`; status `In progress` or `Completed`.
2. Write `courses/<id>/notes.html` in the house style used by `courses/itec4235/notes.html`:
   - one `<section class="lecture prose" id="…">` per lecture or chapter, opening with `<div class="plate"><span class="num">L01</span><p class="ttl">Title</p><p class="src">Source: file.pdf</p></div>`
   - `h3` sections with ids, `h4` subsections
   - callouts: `.box.def` (with a `dl` of Plain English / Technical / Why it matters), `.box.ex`, `.box.warn`, `.box.exam` (with `details` Q&A), `.box.proc`, `.box.bg`; `.formula`, `.tw > table`, `pre.code`, `figure.fig > pre.mermaid`
   - teach, don't summarize: expand every bullet, describe every diagram, work every formula
   - the toc template lists each section and its h3 anchors
3. Write `courses/<id>/questions.json`: aim for about 10 questions per lecture/chapter, mixing mc, tf, and short, with numbers checked. `unit` must be a section id.
4. Rebuild, commit, push, republish (above).

When adding lectures to an in-progress class, append sections to its notes and questions the same way.

## Constraints

- The page must stay one self-contained file: the artifact CSP only allows scripts from cdnjs/jsdelivr and fonts from Google Fonts. Mermaid loads from jsdelivr.
- No progress tracking. Caden chose exams that aren't saved.
- The repo is public. Don't commit original course slides or PDFs, just the rewritten notes.
