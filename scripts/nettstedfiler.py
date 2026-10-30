"""Samler nettstedet i en egen mappe for GitHub Pages, uten interne filer.

Deployen i GitHub Actions lastet tidligere opp hele repoet (``path: "."``),
og Jekyll-bygget fra grenen gjorde prosjektdokumentene om til sider. Begge
deler gjorde CLAUDE.md, ROADMAP.md, skriptene og testene offentlige på
exday.no (funnet 30.10.2026).

Lista over hva som holdes utenfor står i ``_config.yml`` under ``exclude``.
Jekyll leser den selv, og dette skriptet leser den for Actions-deployen, så
de to byggene publiserer de samme filene.

    python scripts/nettstedfiler.py MÅLMAPPE
"""

import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
KONFIG = ROT / "_config.yml"

# Filer nettstedet ikke virker uten. Mangler en av dem i utvalget, er noe
# galt med lista, og da er det bedre å stoppe deployen enn å publisere et
# halvt nettsted.
MAA_MED = ("index.html", "CNAME", "ads.txt", "robots.txt", "sw.js",
           "manifest.json", "data/aksjer.json")


def les_unntak(tekst):
    """Mønstrene under «exclude:» i _config.yml.

    Bare den enkle listeformen («  - mønster») støttes, og det er den fila
    bruker. Kommentarer og andre nøkler hoppes over.
    """
    unntak = []
    i_lista = False
    for linje in tekst.splitlines():
        rad = linje.rstrip()
        innhold = rad.strip()
        if not innhold or innhold.startswith("#"):
            continue
        if not rad[0].isspace():
            i_lista = innhold == "exclude:"
            continue
        if i_lista and innhold.startswith("- "):
            unntak.append(innhold[2:].strip().strip("'\""))
    return unntak


def er_unntatt(sti, unntak):
    """Om en fil (sti relativ til roten, med «/») holdes utenfor.

    Samme regel som Jekyll: navn som begynner med punktum eller understrek
    publiseres aldri, ellers holdes fila utenfor når et mønster passer hele
    stien (der «*» også går over «/», som i Jekyll) eller fila ligger i en
    mappe som er nevnt.
    """
    if any(del_.startswith((".", "_")) for del_ in sti.split("/")):
        return True
    for monster in unntak:
        monster = monster.rstrip("/")
        if (fnmatch.fnmatchcase(sti, monster) or sti == monster
                or sti.startswith(monster + "/")):
            return True
    return False


def nettstedfiler(filer, unntak):
    """Filene som skal publiseres, sortert."""
    return sorted(f for f in filer if not er_unntatt(f, unntak))


def sporede_filer(rot=ROT):
    """Filene git sporer. Det er det samme utvalget Jekyll-bygget fra
    grenen ser, og det holder node_modules og lokale filer ute."""
    ut = subprocess.run(["git", "ls-files", "-z"], cwd=rot, check=True,
                        capture_output=True).stdout
    return [f for f in ut.decode("utf-8").split("\0") if f]


def kopier(filer, kilde, maal):
    """Kopierer filene fra kilde til maal og beholder mappestrukturen.

    En sporet fil som mangler på disk, hoppes over. Returnerer antallet
    som ble kopiert.
    """
    antall = 0
    for f in filer:
        fra = Path(kilde) / f
        if not fra.is_file():
            continue
        til = Path(maal) / f
        til.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fra, til)
        antall += 1
    return antall


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    maal = Path(argv[1])
    if maal.exists() and any(maal.iterdir()):
        print(f"{maal} finnes og er ikke tom", file=sys.stderr)
        return 2
    unntak = les_unntak(KONFIG.read_text(encoding="utf-8"))
    if not unntak:
        print("Fant ingen «exclude» i _config.yml", file=sys.stderr)
        return 1
    alle = sporede_filer()
    utvalg = nettstedfiler(alle, unntak)
    mangler = [f for f in MAA_MED if f not in utvalg]
    if mangler:
        print("Mangler i utvalget: " + ", ".join(mangler), file=sys.stderr)
        return 1
    antall = kopier(utvalg, ROT, maal)
    print(f"Samlet {antall} filer i {maal} ({len(alle) - len(utvalg)} holdt utenfor)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
