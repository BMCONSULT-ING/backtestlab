"""
Backtest Trading — application web (Streamlit) — v2
5 strategies classiques, frais de transaction, tableau des trades,
comparateur de strategies et comparateur d'actifs.
Lancer :  streamlit run app.py
"""
import time

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

from strategies import STRATEGIES, backtester

st.set_page_config(page_title="Backtest Trading", page_icon="static/icon-192.png",
                   layout="wide", initial_sidebar_state="expanded")


# ------------------------------------------------------- PWA + confort mobile
def activer_pwa():
    """Rend l'app installable sur l'ecran d'accueil (mode plein ecran, sans barre
    d'adresse). Les balises doivent aller dans le <head> de la page parente :
    on passe par une iframe dont le script y accede en JavaScript."""
    st.iframe("""
    <script>
      const head = window.parent.document.head;
      const ajouter = (balise, attrs) => {
        const sel = balise + Object.entries(attrs)
              .map(([k, v]) => `[${k}="${v}"]`).join('');
        if (head.querySelector(sel)) return;            // deja injecte
        const el = window.parent.document.createElement(balise);
        Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
        head.appendChild(el);
      };
      ajouter('link', {rel: 'manifest', href: '/app/static/manifest.json'});
      ajouter('link', {rel: 'apple-touch-icon', href: '/app/static/icon-192.png'});
      ajouter('meta', {name: 'apple-mobile-web-app-capable', content: 'yes'});
      ajouter('meta', {name: 'apple-mobile-web-app-title', content: 'Backtest'});
      ajouter('meta', {name: 'apple-mobile-web-app-status-bar-style',
                       content: 'black-translucent'});
      ajouter('meta', {name: 'mobile-web-app-capable', content: 'yes'});
    </script>
    """, height=1)   # st.iframe exige une hauteur > 0 : 1 pixel, invisible


def theme_sombre() -> bool:
    """Thème actif cote navigateur. Repli sur clair si l'info n'est pas encore la."""
    return getattr(getattr(st, "context", None), "theme", None) is not None \
        and getattr(st.context.theme, "type", "light") == "dark"


SOMBRE = theme_sombre()

# Palette "terminal de trading" : neutres ardoise legerement bleutes (jamais de gris
# pur), UN seul bleu d'accent, et le vert / rouge reserves strictement au sens
# gain / perte. Si le vert sert aussi de couleur d'accent, il perd sa signification.
if SOMBRE:
    FOND, SURFACE, SURFACE2 = "#0b111c", "#131c2b", "#182336"
    BORD, BORD_FORT = "#1f2a3c", "#2b3a52"
    TEXTE, TEXTE2, TEXTE3 = "#e6edf6", "#94a2b8", "#6b7891"
    ACCENT = "#4c93f7"
    VERT, ROUGE = "#18c48a", "#e5566e"
    GRIS, ORANGE, VIOLET = "#6b7891", "#f0b429", "#a78bfa"
    GRILLE = "#1b2536"
    OMBRE = "0 1px 2px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.02)"
else:
    FOND, SURFACE, SURFACE2 = "#f7f9fc", "#ffffff", "#f1f5fa"
    BORD, BORD_FORT = "#e3e9f2", "#cfd9e8"
    TEXTE, TEXTE2, TEXTE3 = "#0f1b2b", "#5b6980", "#8a97ab"
    ACCENT = "#2563eb"
    VERT, ROUGE = "#0f9d63", "#d1495b"
    GRIS, ORANGE, VIOLET = "#8a97ab", "#b8790a", "#7c5cd6"
    GRILLE = "#eaeff6"
    OMBRE = "0 1px 2px rgba(16,32,54,.06), 0 0 0 1px rgba(16,32,54,.03)"

BLEU = ACCENT
MONO = "'SFMono-Regular', 'JetBrains Mono', 'Cascadia Mono', Consolas, monospace"

CSS = f"""
<style>
  /* ---------- chrome Streamlit : on retire ce qui appartient a l'outil ---------- */
  [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"] {{ display: none !important; }}
  [data-testid="stHeader"] {{ background: transparent; }}

  .block-container {{ padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1500px; }}

  /* Chiffres : chasse fixe et tabulaire. C'est ce qui fait basculer une page web
     vers la sensation "terminal" : les colonnes de chiffres s'alignent. */
  [data-testid="stMetricValue"], [data-testid="stMetricDelta"],
  [data-testid="stDataFrame"], .mono {{ font-variant-numeric: tabular-nums; }}

  /* ---------- en-tete facon salle de marche ---------- */
  .entete {{ border-bottom: 1px solid {BORD}; padding-bottom: .9rem; margin-bottom: 1.3rem; }}
  .entete-haut {{ display: flex; align-items: flex-end; justify-content: space-between;
                  gap: 1.2rem; flex-wrap: wrap; }}
  .entete .surtitre {{ font-size: .68rem; letter-spacing: .16em; text-transform: uppercase;
                       color: {TEXTE3}; font-weight: 600; margin-bottom: .3rem; }}
  .entete h1 {{ font-size: 1.55rem; font-weight: 600; letter-spacing: -.02em;
                margin: 0; color: {TEXTE}; line-height: 1.15; }}
  .entete .sous {{ font-size: .82rem; color: {TEXTE2}; margin-top: .35rem; }}
  /* Cotation : ce qu'un terminal affiche en premier apres le nom de l'instrument. */
  .cotation {{ text-align: right; }}
  .cotation .prix {{ font-family: {MONO}; font-size: 1.72rem; font-weight: 600;
                     color: {TEXTE}; line-height: 1.1; letter-spacing: -.02em; }}
  .cotation .prix .dev {{ font-size: .95rem; color: {TEXTE3}; margin-left: .18rem;
                          font-weight: 500; }}
  .cotation .var {{ font-family: {MONO}; font-size: .88rem; font-weight: 600;
                    margin-top: .22rem; }}
  .cotation .var.hausse {{ color: {VERT}; }}
  .cotation .var.baisse {{ color: {ROUGE}; }}
  .cotation .ref {{ font-size: .72rem; color: {TEXTE3}; margin-top: .3rem;
                    font-variant-numeric: tabular-nums; }}

  .jetons {{ display: flex; gap: .4rem; flex-wrap: wrap; margin-top: .9rem; }}
  .jeton {{ font-size: .72rem; padding: .3rem .6rem; border-radius: 6px;
            border: 1px solid {BORD}; background: {SURFACE2}; color: {TEXTE2};
            white-space: nowrap; }}
  .jeton b {{ color: {TEXTE}; font-weight: 600; font-family: {MONO}; }}
  .jeton.on {{ border-color: {ACCENT}55; color: {ACCENT}; }}

  /* ---------- cartes de metriques ---------- */
  [data-testid="stMetric"] {{
      background: {SURFACE}; border: 1px solid {BORD}; border-radius: 10px;
      padding: .85rem .95rem; box-shadow: {OMBRE};
      transition: border-color .15s ease; }}
  [data-testid="stMetric"]:hover {{ border-color: {BORD_FORT}; }}
  [data-testid="stMetricLabel"] p {{
      font-size: .68rem !important; letter-spacing: .09em; text-transform: uppercase;
      color: {TEXTE3} !important; font-weight: 600; }}
  [data-testid="stMetricValue"] {{
      font-family: {MONO}; font-size: 1.7rem !important; font-weight: 600;
      line-height: 1.25; letter-spacing: -.02em; color: {TEXTE}; }}
  [data-testid="stMetricValue"] > div {{ font-size: inherit !important; }}
  [data-testid="stMetricDelta"] {{ font-size: .78rem !important; font-weight: 600; }}
  [data-testid="stMetricDelta"] svg {{ display: none; }}   /* la couleur suffit */

  /* ---------- onglets ---------- */
  [data-testid="stTabs"] [role="tablist"] {{
      gap: .15rem; border-bottom: 1px solid {BORD}; }}
  [data-testid="stTabs"] [role="tab"] {{
      color: {TEXTE2}; font-size: .88rem; font-weight: 500;
      padding: .55rem .9rem; border-radius: 6px 6px 0 0; }}
  [data-testid="stTabs"] [role="tab"]:hover {{ color: {TEXTE}; background: {SURFACE2}; }}
  [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
      color: {ACCENT}; font-weight: 600; }}
  [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background: {ACCENT}; height: 2px; }}

  /* ---------- barre laterale ---------- */
  [data-testid="stSidebar"] {{ border-right: 1px solid {BORD}; }}
  [data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
  [data-testid="stSidebar"] hr {{ margin: 1.1rem 0 .9rem; border-color: {BORD}; opacity: .8; }}
  /* micro-titres de section : la hierarchie manquait entre les groupes de reglages */
  .rubrique {{ font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
               color: {TEXTE3}; font-weight: 700; margin: .2rem 0 .55rem; }}
  [data-testid="stSidebar"] label p {{ font-size: .8rem !important; color: {TEXTE2}; }}
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
      font-size: .74rem !important; color: {TEXTE3}; line-height: 1.45; }}

  /* ---------- titres de section ---------- */
  h2, h3 {{ font-size: .95rem !important; font-weight: 600; letter-spacing: .01em;
            color: {TEXTE}; margin-top: .4rem !important; }}

  /* ---------- tableaux ---------- */
  [data-testid="stDataFrame"] {{ border: 1px solid {BORD}; border-radius: 10px; overflow: hidden; }}

  /* ---------- alertes : filet colore a gauche plutot qu'un gros aplat ---------- */
  [data-testid="stAlert"] {{ border-radius: 8px; border: 1px solid {BORD};
                             background: {SURFACE}; padding: .7rem .9rem; }}
  [data-testid="stAlert"] p {{ font-size: .85rem; color: {TEXTE2}; }}

  /* ---------- ecran d'attente maison ---------- */
  .chargement {{ display: flex; flex-direction: column; align-items: center;
                 justify-content: center; gap: 1.1rem; padding: 4.5rem 1rem; }}
  .chargement svg {{ width: 108px; height: 62px; overflow: visible; }}
  .chargement .trace {{ fill: none; stroke: {ACCENT}; stroke-width: 5;
                        stroke-linecap: round; stroke-linejoin: round;
                        stroke-dasharray: 260; stroke-dashoffset: 260;
                        animation: tracer 1.6s ease-in-out infinite; }}
  .chargement .socle {{ stroke: {BORD_FORT}; stroke-width: 3; stroke-linecap: round; }}
  .chargement .txt {{ font-size: .85rem; color: {TEXTE3}; letter-spacing: .02em; }}
  @keyframes tracer {{
    0%   {{ stroke-dashoffset: 260; }}
    55%  {{ stroke-dashoffset: 0; }}
    100% {{ stroke-dashoffset: -260; }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    .chargement .trace {{ animation: none; stroke-dashoffset: 0; }}
  }}

  /* ---------- telephone : les 5 cartes passent a la ligne au lieu d'etre ecrasees ---------- */
  @media (max-width: 640px) {{
    [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: .5rem !important; }}
    [data-testid="stColumn"] {{ flex: 1 1 45% !important; min-width: 45% !important; }}
    .block-container {{ padding: 1rem .8rem 3rem !important; }}
    [data-testid="stMetric"] {{ padding: .6rem .7rem; }}
    [data-testid="stMetricValue"] {{ font-size: 1.1rem !important; }}
    [data-testid="stMetricLabel"] p {{ font-size: .62rem !important; }}
    [data-testid="stMetricDelta"] {{ font-size: .72rem !important; }}
    .entete-haut {{ align-items: flex-start; gap: .6rem; }}
    .entete h1 {{ font-size: 1.2rem; }}
    /* la cotation passe sous le nom et s'aligne a gauche comme le reste */
    .cotation {{ text-align: left; }}
    .cotation .prix {{ font-size: 1.4rem; }}
    .jetons {{ margin-top: .7rem; }}
    h2, h3 {{ font-size: .9rem !important; }}
    [data-testid="stTabs"] [role="tablist"] {{ overflow-x: auto; scrollbar-width: none; }}
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar {{ display: none; }}
  }}
  @media (pointer: coarse) {{
    [data-testid="stTabs"] [role="tab"] {{ padding: .6rem .85rem; }}
  }}
</style>
"""

ECRAN_ATTENTE = """
<div class="chargement">
  <svg viewBox="0 0 108 62" aria-hidden="true">
    <path class="socle" d="M6 56 H102" />
    <path class="trace" d="M8 46 L28 34 L46 40 L64 20 L82 26 L100 6" />
  </svg>
  <div class="txt">{message}</div>
</div>
"""


def ecran_attente(message: str):
    """Remplace le badge 'Running' de Streamlit par une attente qui parle
    a l'utilisateur. Renvoie le conteneur pour pouvoir l'effacer ensuite."""
    boite = st.empty()
    boite.markdown(ECRAN_ATTENTE.format(message=message), unsafe_allow_html=True)
    return boite


def rubrique(titre: str):
    """Micro-titre de section dans la barre laterale."""
    st.sidebar.markdown(f'<div class="rubrique">{titre}</div>', unsafe_allow_html=True)


# st.dataframe rend ses cellules sur un canvas : le CSS ne peut pas les atteindre.
# Les zebrures et les couleurs doivent donc passer par le Styler pandas.
def zebrer(df: pd.DataFrame):
    """Une ligne sur deux legerement teintee : l'oeil suit la ligne sans regle."""
    def bandes(ligne):
        teinte = SURFACE2 if ligne.name % 2 else "rgba(0,0,0,0)"
        return [f"background-color: {teinte}"] * len(ligne)
    return df.style.apply(bandes, axis=1)


def colorer_signe(val):
    """Vert / rouge selon le signe. Reserve au sens gain-perte, jamais decoratif."""
    if isinstance(val, str) and val.startswith("+"):
        return f"color: {VERT}; font-weight: 600"
    if isinstance(val, str) and val.startswith("-"):
        return f"color: {ROUGE}; font-weight: 600"
    return ""


activer_pwa()
st.markdown(CSS, unsafe_allow_html=True)


def style_graphique(fig, hauteur: int):
    """Grille fine, legende discrete, fond transparent : le graphique doit se poser
    sur la page, pas y coller un rectangle blanc."""
    fig.update_layout(
        height=hauteur, margin=dict(l=0, r=6, t=6, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXTE2, size=11.5),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=TEXTE2),
                    borderwidth=0),
        xaxis=dict(gridcolor=GRILLE, griddash="dot", zeroline=False,
                   linecolor=BORD, showline=True, ticks="outside",
                   tickcolor=BORD, ticklen=4),
        yaxis=dict(gridcolor=GRILLE, griddash="dot", zeroline=False,
                   linecolor="rgba(0,0,0,0)", ticks=""),
        hoverlabel=dict(bgcolor=SURFACE, font_color=TEXTE, bordercolor=BORD_FORT,
                        font_size=12),
        hovermode="x unified",
    )
    return fig

# ---------------------------------------------------------------- Données
@st.cache_data(show_spinner=False, ttl=3600)
def charger_prix(ticker: str, periode: str) -> pd.Series:
    """Yahoo renvoie parfois un resultat vide de facon passagere (limitation de
    debit). On retente une fois avant d'abandonner ; l'appelant vide le cache en
    cas d'echec pour ne pas figer une erreur temporaire pendant une heure."""
    for tentative in range(2):
        try:
            df = yf.download(ticker, period=periode, progress=False, auto_adjust=True)
        except Exception:
            df = None
        if df is not None and not df.empty:
            return df["Close"].squeeze().dropna()
        if tentative == 0:
            time.sleep(1.2)
    return pd.Series(dtype=float)

ACTIFS = {
    "Apple (AAPL)": "AAPL", "Microsoft (MSFT)": "MSFT", "Tesla (TSLA)": "TSLA",
    "Nvidia (NVDA)": "NVDA", "Amazon (AMZN)": "AMZN", "Google (GOOGL)": "GOOGL",
    "Bitcoin (BTC-USD)": "BTC-USD", "Ethereum (ETH-USD)": "ETH-USD",
    "CAC 40 (^FCHI)": "^FCHI", "S&P 500 (^GSPC)": "^GSPC", "Or (GC=F)": "GC=F",
}

TYPES_FR = {"EQUITY": "Action", "ETF": "ETF", "CRYPTOCURRENCY": "Crypto",
            "INDEX": "Indice", "FUTURE": "Mat. première", "CURRENCY": "Devise",
            "MUTUALFUND": "Fonds", "OPTION": "Option"}

# Un actif cote dans SA devise : LVMH à Paris en euros, Apple à New York en dollars.
SYMBOLES_DEVISE = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
                   "CHF": "CHF", "CAD": "C$", "AUD": "A$", "HKD": "HK$"}

@st.cache_data(show_spinner=False, ttl=86400)
def devise_de(ticker: str) -> str:
    """Devise de cotation de l'actif (€, $, £…). Repli sur $ si Yahoo ne la donne pas."""
    try:
        code = yf.Ticker(ticker).fast_info.get("currency")
        return SYMBOLES_DEVISE.get(code, code or "$")
    except Exception:
        return "$"

# Ce qu'un trader veut voir en premier : actions et ETF avant les fonds obscurs.
PRIORITE_TYPE = {"EQUITY": 0, "CRYPTOCURRENCY": 1, "ETF": 2, "INDEX": 3,
                 "FUTURE": 4, "CURRENCY": 5, "MUTUALFUND": 9}
# Les grandes places : on les remonte pour eviter les cotations secondaires illiquides.
BOURSES_MAJEURES = {"NasdaqGS", "NYSE", "Paris", "London", "XETRA", "Frankfurt",
                    "Milan", "Amsterdam", "Toronto", "Tokyo", "CCC", "CCY", "SNP", "Nasdaq"}

@st.cache_data(show_spinner=False, ttl=3600)
def chercher_actifs(requete: str) -> dict:
    """Cherche parmi TOUS les actifs du marché mondial (via Yahoo Finance),
    en remontant les instruments les plus traitables (actions, ETF) en tête."""
    try:
        res = yf.Search(requete, max_results=20)
    except Exception:
        return {}

    lignes = []
    for rang, q in enumerate(res.quotes):
        sym = q.get("symbol")
        if not sym:
            continue
        qtype = q.get("quoteType", "")
        bourse = q.get("exchDisp", "")
        score = (PRIORITE_TYPE.get(qtype, 7),          # type d'abord
                 0 if bourse in BOURSES_MAJEURES else 1,  # puis place principale
                 rang)                                  # puis pertinence Yahoo
        nom = q.get("shortname") or q.get("longname") or sym
        libelle = f"{nom} · {TYPES_FR.get(qtype, qtype)} · {bourse} ({sym})"
        lignes.append((score, libelle, sym))

    lignes.sort(key=lambda x: x[0])
    return {lib: sym for _, lib, sym in lignes[:12]}

# ---------------------------------------------------------------- Barre latérale
rubrique("Instrument")

recherche = st.sidebar.text_input(
    "Rechercher un actif", value="",
    placeholder="ex. LVMH, Total, Netflix, or, EUR/USD…",
    help="Tape un nom d'entreprise ou un symbole. La recherche couvre tout le marché mondial : "
         "actions, ETF, cryptos, indices, devises, matières premières.")

if recherche.strip():
    resultats = chercher_actifs(recherche.strip())
    if resultats:
        choix_actif = st.sidebar.selectbox(f"{len(resultats)} résultat(s)",
                                           list(resultats.keys()))
        ticker = resultats[choix_actif]
        nom_actif = choix_actif
    else:
        st.sidebar.warning("Rien trouvé — essaie un autre nom ou choisis un favori.")
        choix_actif = st.sidebar.selectbox("Favoris", list(ACTIFS.keys()), index=0)
        ticker = ACTIFS[choix_actif]
        nom_actif = choix_actif
else:
    choix_actif = st.sidebar.selectbox("Favoris", list(ACTIFS.keys()), index=0)
    ticker = ACTIFS[choix_actif]
    nom_actif = choix_actif

periode = st.sidebar.selectbox(
    "Période testée", ["1y", "2y", "5y", "10y"], index=1,
    format_func=lambda p: {"1y": "1 an", "2y": "2 ans", "5y": "5 ans", "10y": "10 ans"}[p])

st.sidebar.markdown("---")
rubrique("Stratégie")
nom_strat = st.sidebar.selectbox("Méthode testée", list(STRATEGIES.keys()), index=0,
                                 label_visibility="collapsed")
strat = STRATEGIES[nom_strat]
st.sidebar.caption(strat["explication"])

# curseurs propres a la strategie choisie
params = {}
for cle, (label, mini, maxi, defaut) in strat["params"].items():
    params[cle] = st.sidebar.slider(label, mini, maxi, defaut)
if "courte" in params and "longue" in params and params["courte"] >= params["longue"]:
    st.sidebar.error("La moyenne courte doit être plus petite que la longue.")
    st.stop()

st.sidebar.markdown("---")
rubrique("Capital et frais")
dev = devise_de(ticker)
capital = st.sidebar.number_input(f"Capital de départ ({dev})", 1000, 1_000_000, 10_000, step=1000)
frais = st.sidebar.slider("Frais par opération (%)", 0.0, 1.0, 0.1, 0.05,
                          help="Ce que ton courtier prélève à chaque achat ou vente. 0,1 % est courant.")

st.sidebar.markdown("---")
rubrique("Gestion du risque")
stop_actif = st.sidebar.checkbox("Activer le stop-loss", value=False,
                                 help="Vente automatique dès que la perte dépasse un seuil. "
                                      "C'est la base de la gestion du risque chez les traders pro.")
stop = st.sidebar.slider("Vendre si la perte dépasse (%)", 1, 30, 8, disabled=not stop_actif) if stop_actif else 0
if stop_actif:
    st.sidebar.caption(f"Chaque position est coupée automatiquement à −{stop} % "
                       "sous son prix d'achat. On attend ensuite un nouveau signal pour revenir.")

# ---------------------------------------------------------------- Données
attente = ecran_attente(f"Récupération des cours de {nom_actif}…")
close = charger_prix(ticker, periode)
attente.empty()
if close.empty:
    # Un echec ne doit jamais rester en cache : sinon un incident passager chez
    # Yahoo bloque l'actif pendant toute la duree du ttl.
    charger_prix.clear()
    st.error(f"Aucune donnée reçue pour « {ticker} ». "
             "Cela vient souvent d'une limitation temporaire de Yahoo Finance : "
             "recharge la page dans quelques secondes, ou vérifie le symbole.",
             icon=":material/cloud_off:")
    st.stop()

# ---------------------------------------------------------------- En-tête
# Un terminal annonce l'instrument, son cours, puis la configuration du test.
def fr(x: float, dec: int = 2) -> str:
    """Nombre a la francaise : espace fine pour les milliers, virgule decimale."""
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


cours_actuel, cours_debut = float(close.iloc[-1]), float(close.iloc[0])
var_abs = cours_actuel - cours_debut
var_pct = cours_actuel / cours_debut - 1
sens = "hausse" if var_abs >= 0 else "baisse"
date_debut = close.index[0].strftime("%d/%m/%Y")
date_fin = close.index[-1].strftime("%d/%m/%Y")

libelle_periode = {"1y": "1 an", "2y": "2 ans", "5y": "5 ans", "10y": "10 ans"}[periode]
jetons = [
    f"Période <b>{libelle_periode}</b>",
    f"Capital <b>{fr(capital, 0)} {dev}</b>",
    f"Frais <b>{frais:g} %</b>",
    (f'<span class="jeton on">Stop-loss <b>−{stop} %</b></span>' if stop_actif
     else "Stop-loss <b>désactivé</b>"),
]
st.markdown(
    f"""
    <div class="entete">
      <div class="entete-haut">
        <div>
          <div class="surtitre">Backtest de stratégie</div>
          <h1>{nom_actif}</h1>
          <div class="sous">{nom_strat}</div>
        </div>
        <div class="cotation">
          <div class="prix">{fr(cours_actuel)}<span class="dev">{dev}</span></div>
          <div class="var {sens}">{'+' if var_abs >= 0 else '−'}{fr(abs(var_abs))} {dev}
              ({'+' if var_pct >= 0 else '−'}{fr(abs(var_pct) * 100, 1)} %)</div>
          <div class="ref">clôture du {date_fin} · départ {fr(cours_debut)} {dev} le {date_debut}</div>
        </div>
      </div>
      <div class="jetons">
        {''.join(j if j.startswith('<span') else f'<span class="jeton">{j}</span>' for j in jetons)}
      </div>
    </div>
    """,
    unsafe_allow_html=True)

position_brute, indicateurs = strat["fn"](close, **params)
r = backtester(close, position_brute, capital, frais, stop)
r_sans_stop = backtester(close, position_brute, capital, frais, 0) if stop else None

onglet_bt, onglet_trades, onglet_strats, onglet_actifs = st.tabs(
    [":material/query_stats: Résultat",
     ":material/table_rows: Détail des trades",
     ":material/emoji_events: Classement des stratégies",
     ":material/compare_arrows: Comparer des actifs"])

# ================================================================= Onglet 1 : résultat
with onglet_bt:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Stratégie", f"{r['final_strat']:,.0f} {dev}", f"{r['perf_strat']:+.1%}")
    c2.metric("Ne rien faire (buy & hold)", f"{r['final_hold']:,.0f} {dev}", f"{r['perf_hold']:+.1%}")
    c3.metric("Pire baisse subie", f"{r['drawdown_strat']:.1%}",
              f"vs {r['drawdown_hold']:.1%} sans stratégie", delta_color="off")
    c4.metric("Trades", f"{r['nb_trades']}")
    taux = f"{r['gagnants']}/{r['nb_trades']}" if r["nb_trades"] else "—"
    c5.metric("Trades gagnants", taux)

    if r["perf_strat"] > r["perf_hold"]:
        st.success(f"Sur cette période, **{nom_strat}** a fait mieux que garder {nom_actif} sans rien faire "
                   f"({r['perf_strat']:+.1%} contre {r['perf_hold']:+.1%}).",
                   icon=":material/check_circle:")
    else:
        st.warning(f"Sur cette période, mieux valait simplement garder {nom_actif} "
                   f"({r['perf_hold']:+.1%} contre {r['perf_strat']:+.1%} pour la stratégie). "
                   "C'est fréquent — et c'est exactement ce qu'un backtest sert à découvrir avant de risquer de l'argent.",
                   icon=":material/cancel:")

    if r_sans_stop is not None:
        ecart = r["perf_strat"] - r_sans_stop["perf_strat"]
        ecart_dd = r["drawdown_strat"] - r_sans_stop["drawdown_strat"]
        verdict_stop = ("a **amélioré** le gain" if ecart > 0 else "a **coûté** du gain")
        st.info(
            f"**Effet du stop-loss à −{stop} %** : le gain passe de "
            f"{r_sans_stop['perf_strat']:+.1%} (sans stop) à **{r['perf_strat']:+.1%}** (avec stop) — "
            f"il {verdict_stop} de {abs(ecart):.1%}. "
            f"Côté risque, la pire baisse passe de {r_sans_stop['drawdown_strat']:.1%} à "
            f"**{r['drawdown_strat']:.1%}**"
            + (f" (soit {abs(ecart_dd):.1%} de risque en moins)." if ecart_dd > 0
               else ".")
            + "  \n*Le stop protège des grosses pertes, mais coupe parfois des positions qui seraient reparties à la hausse.*",
            icon=":material/shield:")

    st.subheader("Évolution du capital")
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=r["eq_strat"].index, y=r["eq_strat"], name="Stratégie",
                                line=dict(color=VERT, width=2)))
    fig_eq.add_trace(go.Scatter(x=r["eq_hold"].index, y=r["eq_hold"], name="Ne rien faire",
                                line=dict(color=GRIS, width=1.5, dash="dot")))
    fig_eq.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Capital ({dev})",
                         hovermode="x unified", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(style_graphique(fig_eq, fig_eq.layout.height or 320), width='stretch')

    st.subheader("Prix, indicateurs et signaux")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=close.index, y=close, name="Prix", line=dict(color=BLEU, width=1.6)))
    couleurs_ind = [ORANGE, VIOLET, "#0e8a9c"]
    for i, (nom_ind, serie) in enumerate(indicateurs.items()):
        if nom_ind == "RSI":     # le RSI (0-100) n'est pas a l'echelle du prix -> panneau dedie plus bas
            continue
        fig.add_trace(go.Scatter(x=serie.index, y=serie, name=nom_ind,
                                 line=dict(color=couleurs_ind[i % 3], width=1)))
    if r["achats"]:
        fig.add_trace(go.Scatter(x=r["achats"], y=close.loc[r["achats"]], mode="markers", name="Achat",
                                 marker=dict(color=VERT, size=11, symbol="triangle-up")))
    if r["ventes"]:
        fig.add_trace(go.Scatter(x=r["ventes"], y=close.loc[r["ventes"]], mode="markers", name="Vente",
                                 marker=dict(color=ROUGE, size=11, symbol="triangle-down")))
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Prix ({dev})",
                      hovermode="x unified", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(style_graphique(fig, fig.layout.height or 320), width='stretch')

    if "RSI" in indicateurs:
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=indicateurs["RSI"].index, y=indicateurs["RSI"],
                                     name="RSI", line=dict(color=ORANGE, width=1.2)))
        fig_rsi.add_hline(y=params.get("achat", 30), line_color=VERT, line_dash="dot",
                          annotation_text="zone d'achat")
        fig_rsi.add_hline(y=params.get("vente", 70), line_color=ROUGE, line_dash="dot",
                          annotation_text="zone de vente")
        fig_rsi.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="RSI")
        st.plotly_chart(style_graphique(fig_rsi, fig_rsi.layout.height or 320), width='stretch')

# ================================================================= Onglet 2 : trades
with onglet_trades:
    st.subheader(f"Les {r['nb_trades']} trades de la stratégie, un par un")
    if r["nb_trades"] == 0:
        st.info("Cette stratégie n'a déclenché aucun trade sur la période choisie.")
    else:
        st.caption("Chaque ligne = un achat suivi de sa vente. Le résultat tient compte des frais.")
        table = r["trades"].rename(columns={"Prix d'achat": f"Prix d'achat ({dev})",
                                            "Prix de vente": f"Prix de vente ({dev})",
                                            "Resultat": "Résultat"})
        st.dataframe(
            zebrer(table).map(colorer_signe, subset=["Résultat"]),
            width='stretch', hide_index=True,
            column_config={
                f"Prix d'achat ({dev})": st.column_config.NumberColumn(format="%.2f"),
                f"Prix de vente ({dev})": st.column_config.NumberColumn(format="%.2f"),
                "Duree (jours)": st.column_config.NumberColumn("Durée (j)", format="%d"),
            })

# ================================================================= Onglet 3 : comparateur de stratégies
with onglet_strats:
    st.subheader(f"Toutes les stratégies sur {nom_actif} ({periode.replace('y', ' an(s)')})")
    st.caption("Chaque stratégie est testée avec ses réglages par défaut, frais inclus. "
               "La ligne « Ne rien faire » sert de référence.")
    lignes = []
    courbes = {}
    for nom, s in STRATEGIES.items():
        defauts = {cle: p[3] for cle, p in s["params"].items()}
        pos, _ = s["fn"](close, **defauts)
        res = backtester(close, pos, capital, frais, stop)
        lignes.append({"Stratégie": nom, "Gain": res["perf_strat"],
                       "Pire baisse": res["drawdown_strat"], "Trades": res["nb_trades"]})
        courbes[nom] = res["eq_strat"]
    lignes.append({"Stratégie": "Ne rien faire (buy & hold)", "Gain": r["perf_hold"],
                   "Pire baisse": r["drawdown_hold"], "Trades": 0})

    tableau = pd.DataFrame(lignes).sort_values("Gain", ascending=False).reset_index(drop=True)
    tableau.insert(0, "Rang", [str(i) for i in range(1, len(tableau) + 1)])
    meilleure = tableau.iloc[0]["Stratégie"]
    st.dataframe(
        zebrer(tableau).format({"Gain": "{:+.1%}", "Pire baisse": "{:.1%}"})
                       .map(lambda v: f"color: {VERT}; font-weight: 600" if isinstance(v, float) and v > 0
                            else (f"color: {ROUGE}; font-weight: 600" if isinstance(v, float) and v < 0 else ""),
                            subset=["Gain"]),
        width='stretch', hide_index=True,
        column_config={"Rang": st.column_config.TextColumn(width="small"),
                       "Trades": st.column_config.NumberColumn(format="%d")})
    st.success(f"Sur cette période et cet actif, la meilleure approche était : **{meilleure}**. "
               "Ça ne garantit rien pour l'avenir — change d'actif et de période pour voir si elle reste bonne.")

    fig_cmp = go.Figure()
    fig_cmp.add_trace(go.Scatter(x=r["eq_hold"].index, y=r["eq_hold"], name="Ne rien faire",
                                 line=dict(color=GRIS, width=1.5, dash="dot")))
    for nom, eq in courbes.items():
        fig_cmp.add_trace(go.Scatter(x=eq.index, y=eq, name=nom.split(" (")[0].split(" — ")[0]))
    fig_cmp.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Capital ({dev})",
                          hovermode="x unified", legend=dict(orientation="h", y=1.18))
    st.plotly_chart(style_graphique(fig_cmp, fig_cmp.layout.height or 320), width='stretch')

# ================================================================= Onglet 4 : comparateur d'actifs
with onglet_actifs:
    st.subheader(f"La stratégie « {nom_strat} » sur plusieurs actifs")
    # l'actif courant (meme trouve par recherche) + deux references classiques
    options_multi = dict(ACTIFS)
    if nom_actif not in options_multi:
        options_multi = {nom_actif: ticker, **options_multi}
    defaut = [nom_actif]
    for ref in ["S&P 500 (^GSPC)", "Bitcoin (BTC-USD)", "Apple (AAPL)"]:
        if ref in options_multi and ref not in defaut and len(defaut) < 3:
            defaut.append(ref)
    choix_multi = st.multiselect("Actifs à comparer", list(options_multi.keys()), default=defaut)
    if choix_multi:
        lignes = []
        for nom in choix_multi:
            serie = charger_prix(options_multi[nom], periode)
            if serie.empty:
                continue
            pos, _ = strat["fn"](serie, **params)
            res = backtester(serie, pos, capital, frais, stop)
            d = devise_de(options_multi[nom])
            lignes.append({"Actif": nom,
                           "Cours actuel": f"{fr(float(serie.iloc[-1]))} {d}",
                           "Au départ": f"{fr(float(serie.iloc[0]))} {d}",
                           "Variation": f"{float(serie.iloc[-1]) / float(serie.iloc[0]) - 1:+.1%}",
                           "Stratégie": res["perf_strat"],
                           "Ne rien faire": res["perf_hold"],
                           "Verdict": "Stratégie" if res["perf_strat"] > res["perf_hold"]
                                      else "Buy & hold"})
        if lignes:
            df_multi = pd.DataFrame(lignes)
            st.dataframe(
                zebrer(df_multi).format({"Stratégie": "{:+.1%}", "Ne rien faire": "{:+.1%}"})
                                .map(lambda v: f"color: {VERT}; font-weight: 600" if isinstance(v, float) and v > 0
                                     else (f"color: {ROUGE}; font-weight: 600" if isinstance(v, float) and v < 0 else ""),
                                     subset=["Stratégie", "Ne rien faire"])
                                .map(colorer_signe, subset=["Variation"]),
                width='stretch', hide_index=True)
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_multi["Actif"], y=df_multi["Stratégie"],
                                     name="Stratégie", marker_color=VERT))
            fig_bar.add_trace(go.Bar(x=df_multi["Actif"], y=df_multi["Ne rien faire"],
                                     name="Ne rien faire", marker_color=GRIS))
            fig_bar.update_layout(height=340, barmode="group", yaxis_tickformat="+.0%",
                                  margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.15))
            st.plotly_chart(style_graphique(fig_bar, fig_bar.layout.height or 320), width='stretch')

st.caption("Résultats passés simulés, frais inclus mais hors impôts et écarts d'exécution. "
           "Ceci n'est pas un conseil d'investissement.")
