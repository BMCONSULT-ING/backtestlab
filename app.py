"""
Backtest Trading — application web (Streamlit) — v2
5 strategies classiques, frais de transaction, tableau des trades,
comparateur de strategies et comparateur d'actifs.
Lancer :  streamlit run app.py
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

from strategies import STRATEGIES, backtester

st.set_page_config(page_title="Backtest Trading", page_icon="static/icon-192.png", layout="wide")


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


CSS_MOBILE = """
<style>
  /* Sur telephone, 5 indicateurs cote a cote deviennent illisibles :
     on les laisse passer a la ligne au lieu de les comprimer. */
  @media (max-width: 640px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .5rem !important; }
    [data-testid="stColumn"] { flex: 1 1 45% !important; min-width: 45% !important; }
    .block-container { padding: 1rem .8rem 3rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    [data-testid="stMetricLabel"] p { font-size: .72rem !important; }
    [data-testid="stMetricDelta"] { font-size: .75rem !important; }
    h1 { font-size: 1.35rem !important; }
    h2, h3 { font-size: 1.05rem !important; }
    /* les onglets tiennent sur une ligne defilante plutot que de deborder */
    [data-testid="stTabs"] [role="tablist"] { overflow-x: auto; scrollbar-width: none; }
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display: none; }
  }
  /* Confort tactile : cibles plus grandes au doigt */
  @media (pointer: coarse) {
    [data-testid="stTabs"] [role="tab"] { padding: .55rem .8rem; }
  }
</style>
"""

activer_pwa()
st.markdown(CSS_MOBILE, unsafe_allow_html=True)

VERT, ROUGE, GRIS, BLEU, ORANGE, VIOLET = "#2f9e6a", "#d1495b", "#8a94a3", "#3b82f6", "#f59e0b", "#a855f7"

# ---------------------------------------------------------------- Données
@st.cache_data(show_spinner=False, ttl=3600)
def charger_prix(ticker: str, periode: str) -> pd.Series:
    df = yf.download(ticker, period=periode, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    return df["Close"].squeeze().dropna()

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
st.sidebar.title("Réglages")

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
nom_strat = st.sidebar.selectbox("Stratégie", list(STRATEGIES.keys()), index=0)
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
dev = devise_de(ticker)
capital = st.sidebar.number_input(f"Capital de départ ({dev})", 1000, 1_000_000, 10_000, step=1000)
frais = st.sidebar.slider("Frais par opération (%)", 0.0, 1.0, 0.1, 0.05,
                          help="Ce que ton courtier prélève à chaque achat ou vente. 0,1 % est courant.")

stop_actif = st.sidebar.checkbox("Activer le stop-loss", value=False,
                                 help="Vente automatique dès que la perte dépasse un seuil. "
                                      "C'est la base de la gestion du risque chez les traders pro.")
stop = st.sidebar.slider("Vendre si la perte dépasse (%)", 1, 30, 8, disabled=not stop_actif) if stop_actif else 0
if stop_actif:
    st.sidebar.caption(f"Chaque position est coupée automatiquement à −{stop} % "
                       "sous son prix d'achat. On attend ensuite un nouveau signal pour revenir.")

# ---------------------------------------------------------------- En-tête
st.title("Backtest de stratégies de trading")
st.caption("Teste des stratégies classiques sur de vrais prix historiques — sans risquer d'argent réel.")

close = charger_prix(ticker, periode)
if close.empty:
    st.error(f"Aucune donnée pour « {ticker} ». Vérifie le symbole (ex. AAPL, BTC-USD).")
    st.stop()

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
    st.plotly_chart(fig_eq, width='stretch')

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
    st.plotly_chart(fig, width='stretch')

    if "RSI" in indicateurs:
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=indicateurs["RSI"].index, y=indicateurs["RSI"],
                                     name="RSI", line=dict(color=ORANGE, width=1.2)))
        fig_rsi.add_hline(y=params.get("achat", 30), line_color=VERT, line_dash="dot",
                          annotation_text="zone d'achat")
        fig_rsi.add_hline(y=params.get("vente", 70), line_color=ROUGE, line_dash="dot",
                          annotation_text="zone de vente")
        fig_rsi.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="RSI")
        st.plotly_chart(fig_rsi, width='stretch')

# ================================================================= Onglet 2 : trades
with onglet_trades:
    st.subheader(f"Les {r['nb_trades']} trades de la stratégie, un par un")
    if r["nb_trades"] == 0:
        st.info("Cette stratégie n'a déclenché aucun trade sur la période choisie.")
    else:
        st.caption("Chaque ligne = un achat suivi de sa vente. Le résultat tient compte des frais.")
        def colorer(val):
            if isinstance(val, str) and val.startswith("+"):
                return f"color: {VERT}; font-weight: 600"
            if isinstance(val, str) and val.startswith("-"):
                return f"color: {ROUGE}; font-weight: 600"
            return ""
        table = r["trades"].rename(columns={"Prix d'achat": f"Prix d'achat ({dev})",
                                            "Prix de vente": f"Prix de vente ({dev})"})
        st.dataframe(table.style.map(colorer, subset=["Resultat"]),
                     width='stretch', hide_index=True)

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
    st.dataframe(tableau.style.format({"Gain": "{:+.1%}", "Pire baisse": "{:.1%}"}),
                 width='stretch', hide_index=True)
    st.success(f"Sur cette période et cet actif, la meilleure approche était : **{meilleure}**. "
               "Ça ne garantit rien pour l'avenir — change d'actif et de période pour voir si elle reste bonne.")

    fig_cmp = go.Figure()
    fig_cmp.add_trace(go.Scatter(x=r["eq_hold"].index, y=r["eq_hold"], name="Ne rien faire",
                                 line=dict(color=GRIS, width=1.5, dash="dot")))
    for nom, eq in courbes.items():
        fig_cmp.add_trace(go.Scatter(x=eq.index, y=eq, name=nom.split(" (")[0].split(" — ")[0]))
    fig_cmp.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=f"Capital ({dev})",
                          hovermode="x unified", legend=dict(orientation="h", y=1.18))
    st.plotly_chart(fig_cmp, width='stretch')

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
            lignes.append({"Actif": nom, "Stratégie": res["perf_strat"],
                           "Ne rien faire": res["perf_hold"],
                           "Verdict": "Stratégie" if res["perf_strat"] > res["perf_hold"]
                                      else "Buy & hold"})
        if lignes:
            df_multi = pd.DataFrame(lignes)
            st.dataframe(df_multi.style.format({"Stratégie": "{:+.1%}", "Ne rien faire": "{:+.1%}"}),
                         width='stretch', hide_index=True)
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_multi["Actif"], y=df_multi["Stratégie"],
                                     name="Stratégie", marker_color=VERT))
            fig_bar.add_trace(go.Bar(x=df_multi["Actif"], y=df_multi["Ne rien faire"],
                                     name="Ne rien faire", marker_color=GRIS))
            fig_bar.update_layout(height=340, barmode="group", yaxis_tickformat="+.0%",
                                  margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.15))
            st.plotly_chart(fig_bar, width='stretch')

st.caption("Résultats passés simulés, frais inclus mais hors impôts et écarts d'exécution. "
           "Ceci n'est pas un conseil d'investissement.")
