"""
Injecte un ecran d'accueil dans la page servie par Streamlit.

Pourquoi : entre le moment ou le navigateur charge la page et celui ou le tableau
de bord s'affiche, Streamlit montre sa propre attente. Ce fichier appartient a la
bibliotheque, pas a l'application : on le complete avec un voile aux couleurs du
projet, qui s'efface des que le tableau de bord est reellement dessine.

A relancer apres CHAQUE `pip install` (la reinstallation de Streamlit ecrase le
fichier). C'est pour cela que render.yaml l'appelle apres l'installation.

Usage :  python tools/patch_loader.py          (injecte)
         python tools/patch_loader.py --retirer (revient a l'original)

Auteur : Belhassen M'BARKI
"""
import io
import os
import sys

MARQUE = "<!-- ecran-accueil-backtestlab -->"
FIN_MARQUE = "<!-- /ecran-accueil-backtestlab -->"

VOILE = MARQUE + """
<style>
  #accueil-bt {
    position: fixed; inset: 0; z-index: 9999;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 1.15rem; background: #f7f9fc; color: #5b6980;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    transition: opacity .45s ease; opacity: 1;
  }
  #accueil-bt.parti { opacity: 0; pointer-events: none; }
  #accueil-bt .surtitre { font-size: .66rem; letter-spacing: .18em; text-transform: uppercase;
                          color: #8a97ab; font-weight: 600; }
  #accueil-bt svg { width: 116px; height: 66px; overflow: visible; }
  #accueil-bt .socle { stroke: #cfd9e8; stroke-width: 3; stroke-linecap: round; fill: none; }
  #accueil-bt .trace { fill: none; stroke: #2563eb; stroke-width: 5;
                       stroke-linecap: round; stroke-linejoin: round;
                       stroke-dasharray: 260; stroke-dashoffset: 260;
                       animation: bt-tracer 1.6s ease-in-out infinite; }
  #accueil-bt .txt { font-size: .85rem; letter-spacing: .02em; }
  @keyframes bt-tracer {
    0% { stroke-dashoffset: 260; } 55% { stroke-dashoffset: 0; } 100% { stroke-dashoffset: -260; }
  }
  @media (prefers-color-scheme: dark) {
    #accueil-bt { background: #0b111c; color: #94a2b8; }
    #accueil-bt .socle { stroke: #2b3a52; }
    #accueil-bt .trace { stroke: #4c93f7; }
    #accueil-bt .surtitre { color: #6b7891; }
  }
  @media (prefers-reduced-motion: reduce) {
    #accueil-bt .trace { animation: none; stroke-dashoffset: 0; }
  }
</style>
<div id="accueil-bt">
  <div class="surtitre">Backtest de stratégie</div>
  <svg viewBox="0 0 116 66" aria-hidden="true">
    <path class="socle" d="M6 60 H110" />
    <path class="trace" d="M8 50 L30 36 L50 43 L70 21 L90 28 L108 6" />
  </svg>
  <div class="txt">Préparation de l’espace de travail…</div>
</div>
<script>
  (function () {
    var voile = document.getElementById('accueil-bt');
    if (!voile) return;
    var fini = false;
    function retirer() {
      if (fini) return;
      fini = true;
      voile.classList.add('parti');
      setTimeout(function () { voile.remove(); }, 500);
    }
    // Signal fiable : l'en-tete du tableau de bord est rendu par l'application
    // elle-meme, donc sa presence prouve que la page est reellement prete.
    function pret() {
      return document.querySelector('.entete') ||
             document.querySelector('[data-testid="stMetric"]');
    }
    if (pret()) { retirer(); return; }
    var obs = new MutationObserver(function () { if (pret()) { obs.disconnect(); retirer(); } });
    obs.observe(document.body, { childList: true, subtree: true });
    // Filet de securite : jamais de voile bloque, meme si l'application echoue.
    setTimeout(function () { obs.disconnect(); retirer(); }, 25000);
  })();
</script>
""" + FIN_MARQUE


def chemin_index() -> str:
    import streamlit
    return os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")


def patcher(retirer: bool = False) -> int:
    p = chemin_index()
    if not os.path.exists(p):
        print(f"ECHEC : index.html introuvable ({p}) — Streamlit a peut-etre change de structure.")
        return 1

    html = io.open(p, encoding="utf-8").read()
    deja = MARQUE in html

    if retirer:
        if not deja:
            print("Rien a retirer : la page est deja dans son etat d'origine.")
            return 0
        debut, fin = html.index(MARQUE), html.index(FIN_MARQUE) + len(FIN_MARQUE)
        io.open(p, "w", encoding="utf-8").write(html[:debut] + html[fin:])
        print("Ecran d'accueil retire.")
        return 0

    if deja:                       # idempotent : on remplace l'ancienne version
        debut, fin = html.index(MARQUE), html.index(FIN_MARQUE) + len(FIN_MARQUE)
        html = html[:debut] + html[fin:]

    if "<body>" not in html:
        print("ECHEC : balise <body> introuvable — injection annulee, page laissee intacte.")
        return 1

    html = html.replace("<body>", "<body>\n" + VOILE, 1)
    io.open(p, "w", encoding="utf-8").write(html)
    print(f"Ecran d'accueil {'remplace' if deja else 'injecte'} dans {p}")
    return 0


if __name__ == "__main__":
    sys.exit(patcher(retirer="--retirer" in sys.argv))
