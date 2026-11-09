"""
Klokke for børsdagen: starter prisjobben og datajobben selv.

GitHub starter planlagte kjøringer for sent eller ikke i det hele tatt. I
oktober 2026 gikk prisjobben rundt tre av 37 ganger per børsdag, og datajobben
startet tre til fem timer etter timeplanen. Det hjalp ikke å flytte minuttene
bort fra hel time (2026-10-11).

Denne jobben går i stedet som en kjede av kjøringer og starter de to jobbene
selv med `workflow_dispatch`, som GitHub kjører med en gang.

En kjøring kan vare høyst seks timer. Når den har levd i `GRENSE`, starter den
en ny kjøring av seg selv og avslutter; den nye tar over der den slapp.

Kjeden går også gjennom natten (2026-11-09). Før det ga klokka seg etter
siste tidspunkt og ventet på at GitHubs timeplan skulle starte den neste
morgen. Timeplanen kom fem til ti timer for sent hver eneste dag: første
kjøring startet mellom 13.01 og 17.04 norsk tid, og 9. november gikk hele
børsdagen uten én kursoppdatering. Nå venter klokka til neste børsdags første
tidspunkt når det er under `MAKS_VENT` unna. Over helgen gir den seg, og
timeplanen starter den igjen søndag kveld eller natt til mandag.

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

# Så lenge venter klokka på neste tidspunkt i planen. Fra siste tidspunkt en
# hverdag til første neste morgen er det 15 timer. Fra fredag kveld til mandag
# morgen er det 63, og da gir klokka seg i stedet for å holde en maskin i gang
# hele helgen.
MAKS_VENT = datetime.timedelta(hours=20)

# En kjøring som har levd kortere enn dette, starter aldri en ny klokke.
# Natt til 3. november 2026 startet klokka seg selv om igjen hvert tiende
# sekund i tre timer, rundt tusen kjøringer: den startet 00.12, så at neste
# tidspunkt (08.41) lå mer enn `GRENSE` unna, og overleverte med en gang til
# en ny kjøring som så det samme. Nå venter den til den selv har levd i
# `GRENSE`, og denne grensen stopper en ny løkke om regelen over skulle ryke.
MIN_LEVETID = datetime.timedelta(minutes=30)

VENT, OVERLEVER, FERDIG = "vent", "overlever", "ferdig"


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


def neste_i_planen(naa, dager=4):
    """Første tidspunkt etter `naa`, i dag eller en av de neste dagene.

    Fire dager fram dekker en helg. None betyr at det ikke er noe i sikte.
    """
    for i in range(dager + 1):
        tid = neste_tid(naa, plan(naa.date() + datetime.timedelta(days=i)))
        if tid is not None:
            return tid
    return None


def sekunder(fra, til):
    """Sekunder fra `fra` til `til`, målt i faktisk tid.

    To tidspunkt i samme tidssone trekkes fra hverandre som klokkeslett i
    Python, så en natt med overgang til eller fra sommertid blir en time feil.
    """
    return til.timestamp() - fra.timestamp()


def neste_steg(naa, frist, neste, maks_vent=MAKS_VENT):
    """Hva kjøringen gjør nå: (VENT, til), (OVERLEVER, til) eller (FERDIG, None).

    `frist` er når denne kjøringen må gi seg (oppstart + GRENSE), og `neste`
    er neste tidspunkt i planen.

    - VENT: neste tidspunkt nås før fristen. Vent til det.
    - OVERLEVER: det nås ikke. Vent til fristen, og start så en ny klokke.
      Kjøringen venter altså selv først; den som overleverer med en gang,
      lager en løkke (se MIN_LEVETID).
    - FERDIG: ingenting i sikte, eller lenger unna enn `maks_vent` (helg).
    """
    if neste is None or sekunder(naa, neste) > maks_vent.total_seconds():
        return FERDIG, None
    if neste <= frist:
        return VENT, neste
    return OVERLEVER, frist


def kan_overlevere(oppstart, naa, min_levetid=MIN_LEVETID):
    """Har kjøringen levd lenge nok til å starte en ny klokke?"""
    return sekunder(oppstart, naa) >= min_levetid.total_seconds()


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


def _naa():
    return datetime.datetime.now(OSLO)


def kjor(repo, naa_fn=_naa, sov=time.sleep):
    """Går til dagen er ferdig eller en ny klokke har tatt over.

    Returnerer False når overleveringen feilet, slik at kjøringen blir rød og
    synes i loggen. Da er kjeden brutt til timeplanen starter en ny.
    """
    oppstart = naa_fn()
    # Regnet i UTC, så fristen er GRENSE i faktisk tid også over sommertidsskiftet.
    frist = (oppstart.astimezone(datetime.timezone.utc) + GRENSE).astimezone(OSLO)
    while True:
        naa = naa_fn()
        dagens = plan(naa.date())
        aktuelle = {wf for _, wf in dagens}
        sist = {wf: sist_opprettet(repo, wf) for wf in aktuelle}
        for wf in skal_startes(naa, dagens, sist):
            start(repo, wf)
        neste = neste_i_planen(naa)
        steg, til = neste_steg(naa, frist, neste)
        if steg == FERDIG:
            hvorfor = "ingenting i sikte" if neste is None else f"neste er {neste:%a %H:%M}"
            print(f"{naa:%H:%M}: {hvorfor}; gir seg til timeplanen starter en ny klokke.",
                  flush=True)
            return True
        if steg == VENT:
            print(f"{naa:%H:%M}: venter til {til:%a %H:%M}.", flush=True)
        else:
            print(f"{naa:%H:%M}: neste er {neste:%a %H:%M}; venter til {til:%H:%M} "
                  "og starter en ny klokke.", flush=True)
        sov(max(sekunder(naa_fn(), til) + (5 if steg == VENT else 0), 1))
        if steg == OVERLEVER:
            naa = naa_fn()
            if not kan_overlevere(oppstart, naa):
                print(f"::error::Klokka har bare levd {sekunder(oppstart, naa):.0f} s; "
                      "starter ikke en ny.", flush=True)
                return False
            return start(repo, KLOKKE)


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
    return 0 if kjor(repo) else 1


if __name__ == "__main__":
    sys.exit(main())
