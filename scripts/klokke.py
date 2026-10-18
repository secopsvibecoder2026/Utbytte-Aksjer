"""
Klokke for børsdagen: starter prisjobben og datajobben selv.

GitHub starter planlagte kjøringer for sent eller ikke i det hele tatt. I
oktober 2026 gikk prisjobben rundt tre av 37 ganger per børsdag, og datajobben
startet tre til fem timer etter timeplanen. Det hjalp ikke å flytte minuttene
bort fra hel time (2026-10-11).

Denne jobben går i stedet hele børsdagen i én kjøring og starter de to
jobbene selv med `workflow_dispatch`, som GitHub kjører med en gang. Den
trenger bare å komme i gang én gang om morgenen: workflowen prøver hver halve
time, og en kjøring som allerede går, holder de andre i kø.

En kjøring kan vare høyst seks timer. Før det starter klokka en ny kjøring av
seg selv og avslutter; den nye tar over der den slapp.

Hver gang klokka skal starte en jobb, spør den først GitHub når jobben sist
startet. Har den startet etter tidspunktet i planen (fordi timeplanen faktisk
slo til, eller klokka nettopp ble byttet ut), startes den ikke på nytt.

Kjør manuelt (viser planen, starter ingenting):
    python3 scripts/klokke.py --plan
"""

import datetime
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")

PRISJOBB = "oppdater-priser.yml"
DATAJOBB = "update-og-deploy.yml"
KLOKKE = "klokke.yml"

# Oslo-tid. Børsen er åpen 09.00–16.20 med sluttauksjon til om lag 16.25.
# Prisene hentes hvert kvarter gjennom handelsdagen, og to ganger etter
# stengning, fordi Yahoo kan bruke en stund på sluttkursen.
PRIS_TIDER = ([(t, m) for t in range(9, 17) for m in (7, 22, 37, 52)]
              + [(17, 7), (17, 37)])
# Samme klokkeslett som timeplanen i update-og-deploy.yml hadde om vinteren.
# Den siste er etter stengning, så sidene får sluttkursene.
DATA_TIDER = [(8, 41), (11, 41), (14, 41), (17, 41)]

# En kjøring på GitHub kan vare seks timer. Klokka gir seg i god tid før.
GRENSE = datetime.timedelta(hours=5, minutes=30)


def plan(dato):
    """[(tidspunkt, workflow)] for børsdagen `dato`, sortert. Tom i helgen.

    Helligdager er ikke med: børsen er stengt, men en kjøring som ikke finner
    nye kurser, committer ingenting. Det er samme oppførsel som timeplanen
    hadde.
    """
    if dato.weekday() >= 5:
        return []
    ut = [(datetime.datetime.combine(dato, datetime.time(t, m), OSLO), PRISJOBB)
          for t, m in PRIS_TIDER]
    ut += [(datetime.datetime.combine(dato, datetime.time(t, m), OSLO), DATAJOBB)
           for t, m in DATA_TIDER]
    return sorted(ut)


def skal_startes(naa, plan_, sist_startet):
    """Workflowene som skal startes nå.

    For hver workflow ses det bare på det siste tidspunktet i planen som er
    passert. Er det flere passert siden sist, startes jobben én gang, ikke én
    gang per tidspunkt: en priskjøring henter uansett dagens kurser.

    `sist_startet` er {workflow: når siste kjøring ble opprettet}, eller None
    når det ikke vites. Ukjent betyr at jobben startes; en kjøring for mye
    koster lite, en som uteblir, er det klokka finnes for å hindre.
    """
    sist_passert = {}
    for tid, wf in plan_:
        if tid <= naa:
            sist_passert[wf] = tid
    ut = []
    for wf, tid in sist_passert.items():
        s = sist_startet.get(wf)
        if s is None or s < tid:
            ut.append(wf)
    return sorted(ut)


def neste_tid(naa, plan_):
    """Første tidspunkt i planen etter `naa`, eller None når dagen er ferdig."""
    for tid, _ in plan_:
        if tid > naa:
            return tid
    return None


def ma_overlevere(start, neste, grense=GRENSE):
    """Rekker denne kjøringen ikke neste tidspunkt før sekstimersgrensen?"""
    return neste - start > grense


def _gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)


def sist_opprettet(repo, wf):
    """Når siste kjøring av `wf` ble opprettet, eller None ved feil."""
    r = _gh("api", f"repos/{repo}/actions/workflows/{wf}/runs?per_page=1")
    if r.returncode != 0:
        print(f"  Kunne ikke lese kjøringene til {wf}: {r.stderr.strip()}", flush=True)
        return None
    try:
        runs = json.loads(r.stdout).get("workflow_runs") or []
        if not runs:
            return None
        return datetime.datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00"))
    except (ValueError, KeyError) as e:
        print(f"  Uventet svar for {wf}: {e}", flush=True)
        return None


def start(repo, wf):
    for forsok in range(1, 5):
        r = _gh("workflow", "run", wf, "--ref", "main", "--repo", repo)
        if r.returncode == 0:
            print(f"  Startet {wf}", flush=True)
            return True
        print(f"  Forsøk {forsok} på {wf} feilet: {r.stderr.strip()}", flush=True)
        time.sleep(10 * forsok)
    print(f"::error::Klarte ikke å starte {wf}", flush=True)
    return False


def kjor(repo):
    oppstart = datetime.datetime.now(OSLO)
    while True:
        naa = datetime.datetime.now(OSLO)
        dagens = plan(naa.date())
        aktuelle = {wf for _, wf in dagens}
        sist = {wf: sist_opprettet(repo, wf) for wf in aktuelle}
        for wf in skal_startes(naa, dagens, sist):
            start(repo, wf)
        neste = neste_tid(naa, dagens)
        if neste is None:
            print(f"{naa:%H:%M}: ingenting mer i dag.", flush=True)
            return
        if ma_overlevere(oppstart, neste):
            print(f"{naa:%H:%M}: neste er {neste:%H:%M}, etter grensen; starter en ny klokke.",
                  flush=True)
            start(repo, KLOKKE)
            return
        vent = (neste - datetime.datetime.now(OSLO)).total_seconds() + 5
        print(f"{naa:%H:%M}: venter til {neste:%H:%M}.", flush=True)
        time.sleep(max(vent, 1))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--plan" in argv:
        i_dag = datetime.datetime.now(OSLO).date()
        for tid, wf in plan(i_dag):
            print(f"{tid:%H:%M}  {wf}")
        return 0
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("GITHUB_REPOSITORY mangler.", file=sys.stderr)
        return 1
    kjor(repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
