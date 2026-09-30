#!/usr/bin/env python3
"""
tallkontroll_side.py — gjør tallkontroll-agentens rapport om til én fast side.

Den ukentlige rutinen («Ukentlig tallkontroll») starter en ny økt uten
GitHub-tilgang, så den kan ikke skrive et issue. Rapporten ble derfor
liggende i økten den kom fra (første kjøring 28.09.2026), der ingen fant den.
Rutinen publiserer nå rapporten til én privat Artifact-side på claude.ai i
stedet — samme adresse hver uke — og denne fila bygger HTML-en, så siden ser
lik ut uansett hvilken økt som skriver den.

    python scripts/tallkontroll_side.py rapport.md --dato 2026-10-05 > side.html

Markdown-støtten er bevisst liten: overskrifter, avsnitt, punktlister,
tabeller, **fet**, `kode` og [lenker](https://…). Det er det agenten skriver.
Alt escapes før formatering, så innhold fra børsmeldinger kan aldri bli HTML.
"""
import argparse
import datetime
import html
import re
import sys

MND = ["januar", "februar", "mars", "april", "mai", "juni", "juli",
       "august", "september", "oktober", "november", "desember"]


def norsk_dato(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{d.day}. {MND[d.month - 1]} {d.year}"


_CHIP = re.compile(r"\b(kritisk|advarsel|bekreftet|mistenkt)\b", re.I)


def inline(tekst):
    """Escaper først, formaterer etterpå — rekkefølgen er sikkerheten."""
    t = html.escape(tekst, quote=True)
    koder = []

    def _kode(m):
        koder.append(m.group(1))
        return f"\x00{len(koder) - 1}\x00"

    t = re.sub(r"`([^`]+)`", _kode, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https://[^)\s]+)\)",
               r'<a href="\2" rel="noopener noreferrer">\1</a>', t)
    t = _CHIP.sub(lambda m: f'<span class="chip chip-{m.group(1).lower()}">{m.group(1)}</span>', t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{koder[int(m.group(1))]}</code>", t)
    return t


def _er_tabellrad(linje):
    s = linje.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 1


def _celler(linje):
    return [c.strip() for c in linje.strip().strip("|").split("|")]


def markdown_til_html(md):
    linjer = md.replace("\r\n", "\n").split("\n")
    ut, i = [], 0
    while i < len(linjer):
        linje = linjer[i]
        s = linje.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            blokk = []
            while i < len(linjer) and not linjer[i].strip().startswith("```"):
                blokk.append(linjer[i])
                i += 1
            i += 1
            ut.append(f'<pre class="blokk"><code>{html.escape(chr(10).join(blokk))}</code></pre>')
            continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            # # og ## → h2 (agenten skriver ## øverst), ### → h3. h1 er sidens tittel.
            niva = max(2, len(m.group(1)))
            ut.append(f"<h{niva}>{inline(m.group(2))}</h{niva}>")
            i += 1
            continue
        if _er_tabellrad(s):
            rader = []
            while i < len(linjer) and _er_tabellrad(linjer[i]):
                rader.append(_celler(linjer[i]))
                i += 1
            hode, kropp = rader[0], rader[1:]
            if kropp and all(re.fullmatch(r":?-{2,}:?", c) for c in kropp[0]):
                kropp = kropp[1:]
            th = "".join(f"<th>{inline(c)}</th>" for c in hode)
            tr = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in kropp)
            ut.append(f'<div class="tabell"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>')
            continue
        if re.match(r"([-*]|\d+\.)\s+", s):
            nummerert = bool(re.match(r"\d+\.", s))
            punkter = []
            while i < len(linjer) and re.match(r"\s*([-*]|\d+\.)\s+", linjer[i]):
                punkter.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", linjer[i]))
                i += 1
                # Fortsettelseslinjer (innrykket) hører til forrige punkt.
                while i < len(linjer) and linjer[i].startswith("  ") and linjer[i].strip() \
                        and not re.match(r"\s*([-*]|\d+\.)\s+", linjer[i]):
                    punkter[-1] += " " + linjer[i].strip()
                    i += 1
            tag = "ol" if nummerert else "ul"
            ut.append(f"<{tag}>" + "".join(f"<li>{inline(p)}</li>" for p in punkter) + f"</{tag}>")
            continue
        avsnitt = [s]
        i += 1
        while i < len(linjer) and linjer[i].strip() and not re.match(
                r"(#{1,4}\s|```|\||([-*]|\d+\.)\s)", linjer[i].strip()):
            avsnitt.append(linjer[i].strip())
            i += 1
        ut.append(f"<p>{inline(' '.join(avsnitt))}</p>")
    return "\n".join(ut)


STIL = """<style>
/* Rapportside: én kolonne, sammendrag øverst, tabeller i egen rullebeholder.
   Grønn aksent fra exday.no sin palett (CLAUDE.md) — aldri Arctic-fargene. */
:root {
  --bg: #f5f8f6; --flate: #ffffff; --fg: #16241b; --demp: #58695e;
  --kant: #dbe5de; --aksent: #15803d; --kritisk: #b42318; --kritisk-bg: #fdecea;
  --advarsel: #9a5b00; --advarsel-bg: #fff4de; --ok: #166534; --ok-bg: #e7f6ec;
  --tekst: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0e1511; --flate: #141e18; --fg: #e2ebe4; --demp: #93a699;
  --kant: #26352c; --aksent: #4ade80; --kritisk: #ff9b8f; --kritisk-bg: #3a1714;
  --advarsel: #f5c05a; --advarsel-bg: #33260b; --ok: #6ee79a; --ok-bg: #12301d;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0e1511; --flate: #141e18; --fg: #e2ebe4; --demp: #93a699;
  --kant: #26352c; --aksent: #4ade80; --kritisk: #ff9b8f; --kritisk-bg: #3a1714;
  --advarsel: #f5c05a; --advarsel-bg: #33260b; --ok: #6ee79a; --ok-bg: #12301d;
  color-scheme: dark; }
body { background: var(--bg); color: var(--fg); font: 16px/1.6 var(--tekst);
  padding-inline: 16px; padding-block: 28px 56px; }
.side { max-width: 760px; margin: 0 auto; display: grid; gap: 20px; min-width: 0; }
header { display: grid; gap: 6px; border-bottom: 2px solid var(--aksent); padding-bottom: 16px; }
.merke { font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--aksent); }
h1 { font-size: 28px; line-height: 1.2; margin: 0; text-wrap: balance; }
.meta { color: var(--demp); font-size: 14px; margin: 0; }
main { display: grid; gap: 14px; min-width: 0; }
h2 { font-size: 20px; margin: 14px 0 0; text-wrap: balance; }
h3, h4 { font-size: 17px; margin: 8px 0 0; }
p, ul, ol { margin: 0; max-width: 68ch; }
ul, ol { padding-left: 22px; display: grid; gap: 4px; }
a { color: var(--aksent); }
code { font: 13px var(--mono); background: var(--flate); border: 1px solid var(--kant);
  border-radius: 4px; padding: 0 4px; overflow-wrap: anywhere; }
pre.blokk { margin: 0; background: var(--flate); border: 1px solid var(--kant); border-radius: 6px;
  padding: 12px; overflow-x: auto; }
pre.blokk code { border: 0; padding: 0; background: none; }
.tabell { overflow-x: auto; border: 1px solid var(--kant); border-radius: 6px; background: var(--flate); }
table { border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--kant); vertical-align: top; }
th { font-weight: 600; color: var(--demp); font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }
tr:last-child td { border-bottom: 0; }
.chip { display: inline-block; font: 600 11px/1.6 var(--mono); letter-spacing: .04em;
  text-transform: uppercase; padding: 0 6px; border-radius: 3px; }
.chip-kritisk { color: var(--kritisk); background: var(--kritisk-bg); }
.chip-advarsel, .chip-mistenkt { color: var(--advarsel); background: var(--advarsel-bg); }
.chip-bekreftet { color: var(--ok); background: var(--ok-bg); }
.tom { background: var(--flate); border: 1px dashed var(--kant); border-radius: 6px; padding: 18px; color: var(--demp); }
footer { color: var(--demp); font-size: 13px; border-top: 1px solid var(--kant); padding-top: 14px; }
</style>"""


def bygg_side(md, dato=None, neste=None):
    """Hele sideinnholdet (uten <html>/<body> — Artifact legger det til)."""
    tittel_dato = norsk_dato(dato) if dato else ""
    kropp = markdown_til_html(md) if md.strip() else (
        '<div class="tom">Ingen rapport ennå. Den første fra den ukentlige '
        'kontrollen kommer hit så snart den er kjørt.</div>')
    neste_tekst = f" Neste kontroll: {norsk_dato(neste)}." if neste and norsk_dato(neste) else ""
    return f"""<title>Tallkontroll exday.no</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@500;600&display=swap">
{STIL}
<div class="side">
<header>
  <span class="merke">exday.no · ukentlig tallkontroll</span>
  <h1>Tallkontroll{(" " + tittel_dato) if tittel_dato else ""}</h1>
  <p class="meta">Tallene på exday.no sammenlignet med Yahoos ujusterte rådata, selskapenes meldinger til Oslo Børs og Euronexts noteringsliste.{neste_tekst}</p>
</header>
<main>
{kropp}
</main>
<footer>Skrevet av tallkontroll-agenten (<code>.claude/agents/tallkontroll.md</code>). Siden erstattes hver uke; ingenting her er rettet ennå — rettingene gjøres i en egen økt.</footer>
</div>
"""


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("rapport", nargs="?", help="markdown-fil (utelat for tom side)")
    p.add_argument("--dato", help="rapportens dato, ISO")
    p.add_argument("--neste", help="neste planlagte kontroll, ISO")
    a = p.parse_args()
    md = open(a.rapport, encoding="utf-8").read() if a.rapport else ""
    sys.stdout.write(bygg_side(md, a.dato, a.neste))


if __name__ == "__main__":
    main()
