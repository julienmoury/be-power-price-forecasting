"""Errors of the live forecasts since the first live day, computed in SQL (DuckDB), and the
live page as HTML.

The forecast and realised-price files (one row per day, columns h0..h23) are loaded into
two long tables, ``forecasts`` and ``realised``; the queries are in ``sql/``.
"""

from __future__ import annotations

import html
import posixpath
import re
from importlib.resources import files
from pathlib import Path

import duckdb
import pandas as pd

from be_power_forecast.backtest import HOURS

SQL = files("be_power_forecast") / "sql"


def long_format(path: Path) -> pd.DataFrame:
    """A daily file (Date, h0..h23) as rows of (day, hour, price)."""
    wide = pd.read_csv(path, index_col=0, parse_dates=True)[HOURS]
    out = wide.rename_axis("day").reset_index().melt("day", var_name="hour", value_name="price")
    out["day"] = out["day"].dt.date
    out["hour"] = out["hour"].str[1:].astype(int)
    return out.dropna()


def live_errors(forecast_files: dict[str, Path], realised_file: Path, start: str) -> dict:
    """Daily, summary and by-hour errors of the models of ``forecast_files``."""
    forecasts = pd.concat(
        [long_format(path).assign(model=model) for model, path in forecast_files.items()]
    )
    con = duckdb.connect()
    con.register("forecasts", forecasts[["model", "day", "hour", "price"]])
    con.register("realised", long_format(realised_file))
    con.execute((SQL / "errors.sql").read_text().format(start=start))
    queries = ("daily", "summary", "by_hour")
    return {name: con.sql((SQL / f"{name}.sql").read_text()).df() for name in queries}


# The live page as one static HTML file (the public page on AWS, docs/aws.md): the
# Markdown written by scripts/live_forecast.py, converted line by line. Only what that page
# uses is supported: headings, paragraphs, tables, images, links, inline code and the
# <details> blocks, which are kept as they are.
PAGE_STYLE = """
:root { color-scheme: light dark; --ink: #1f1e1c; --muted: #52514e; --line: #e4e3df;
  --bg: #ffffff; --link: #2a78d6; }
@media (prefers-color-scheme: dark) {
  :root { --ink: #ecebe8; --muted: #b5b4b0; --line: #3a3936; --bg: #161615; --link: #6aa6ec; }
}
body { margin: 0 auto; max-width: 46rem; padding: 1.5rem 1rem 3rem; background: var(--bg);
  color: var(--ink); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 1.6rem; margin: 0 0 1rem; }
h2 { font-size: 1.2rem; margin: 2rem 0 0.75rem; }
a { color: var(--link); }
img { max-width: 100%; height: auto; background: #fff; border-radius: 4px; }
table { border-collapse: collapse; margin: 0.5rem 0 1rem; font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid var(--line); padding: 0.3rem 0.75rem; text-align: right; }
th:first-child, td:first-child { text-align: left; }
summary { cursor: pointer; margin: 0.5rem 0; color: var(--muted); }
footer { margin-top: 2rem; color: var(--muted); font-size: 0.85rem; }
"""


def _inline(text: str, repo_url: str) -> str:
    """Escaped text with its links, images and inline code; relative links outside the page
    (``../src/...``) point to the repository on GitHub."""

    def href(url: str) -> str:
        if url.startswith("../"):
            path = posixpath.normpath(posixpath.join("live", url))
            return f"{repo_url}/tree/main/{path}"
        return url

    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: f'<img src="{m[2]}" alt="{m[1]}">', text)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{href(m[2])}">{m[1]}</a>', text)


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def page_html(markdown: str, repo_url: str) -> str:
    """The live page (``live/README.md``) as a standalone HTML document."""
    out, para, lines = [], [], markdown.splitlines()
    title = next((line[2:] for line in lines if line.startswith("# ")), "Live")

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(para), repo_url)}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            head = "".join(f"<th>{_inline(c, repo_url)}</th>" for c in rows[0])
            body = "".join(
                "<tr>" + "".join(f"<td>{_inline(c, repo_url)}</td>" for c in r) + "</tr>"
                for r in rows[2:]
            )
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
            continue
        if not line:
            flush()
        elif line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{_inline(line[level:].strip(), repo_url)}</h{level}>")
        elif line.startswith(("<details", "</details", "<summary")):
            flush()
            out.append(line)
        else:
            para.append(line)
        i += 1
    flush()
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html.escape(title)}</title>",
            f"<style>{PAGE_STYLE}</style>",
            "</head>",
            "<body>",
            *out,
            f'<footer>Code: <a href="{repo_url}">{repo_url}</a></footer>',
            "</body>",
            "</html>",
            "",
        ]
    )
