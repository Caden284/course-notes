#!/usr/bin/env python3
"""Assemble the single-file site (index.html) from site/shell.html and courses/*.

Each course folder holds:
  notes.html      <template data-part="toc">…</template><template data-part="main">…</template>
  questions.json  list of {unit, type: mc|tf|short, q, choices?, answer, explain}
  tools.js        optional; defines function initTools() run after the notes render

courses/courses.json lists the courses (order does not matter; the home page groups by term).
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
TYPES = {"mc", "tf", "short"}


def fail(msg):
    sys.exit("build failed: " + msg)


def main():
    courses = json.loads((ROOT / "courses/courses.json").read_text())
    templates, tools, questions = [], [], []
    for c in courses:
        cid = c["id"]
        folder = ROOT / "courses" / cid
        notes = (folder / "notes.html").read_text()
        parts = dict(re.findall(r'<template data-part="(toc|main)">(.*?)</template>', notes, re.S))
        if set(parts) != {"toc", "main"}:
            fail(f"{cid}/notes.html needs a toc and a main template")
        unit_ids = set(re.findall(r'<section[^>]*\bid="([^"]+)"', parts["main"]))
        for part, body in parts.items():
            templates.append(f'<template id="course-{cid}-{part}">{body}</template>')

        qfile = folder / "questions.json"
        for n, q in enumerate(json.loads(qfile.read_text()) if qfile.exists() else []):
            where = f"{cid}/questions.json item {n}"
            if q.get("type") not in TYPES:
                fail(f"{where}: type must be mc, tf, or short")
            if q.get("unit") not in unit_ids:
                fail(f"{where}: unit {q.get('unit')!r} is not a section id in the notes")
            if q["type"] == "mc" and not (isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(q.get("choices", []))):
                fail(f"{where}: mc answer must index into choices")
            if q["type"] == "tf" and not isinstance(q.get("answer"), bool):
                fail(f"{where}: tf answer must be true or false")
            if q["type"] == "short" and not str(q.get("answer", "")).strip():
                fail(f"{where}: short answer needs a model answer")
            questions.append(dict(q, course=cid, id=f"{cid}-{n + 1}"))

        tjs = folder / "tools.js"
        if tjs.exists():
            tools.append(f"COURSE_TOOLS[{json.dumps(cid)}] = (function(){{\n{tjs.read_text()}\nreturn initTools;\n}})();")

    def embed(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    shell = (ROOT / "site/shell.html").read_text()
    out = (shell.replace("{{COURSES_JSON}}", embed(courses))
                .replace("{{QUESTIONS_JSON}}", embed(questions))
                .replace("{{COURSE_TEMPLATES}}", "\n".join(templates))
                .replace("{{COURSE_TOOLS}}", "\n".join(tools)))
    (ROOT / "index.html").write_text(out)
    print(f"index.html: {len(out) / 1024:.0f} KB, {len(courses)} courses, {len(questions)} questions")


if __name__ == "__main__":
    main()
