"""
Les strategies de trading disponibles.
Chaque strategie prend la serie des prix de cloture et renvoie une "position" :
  1 = on est investi (on detient l'actif), 0 = on est hors du marche (en cash).
Toutes les strategies classiques ci-dessous sont utilisees par de vrais traders.
"""
import pandas as pd
import numpy as np


def rsi(close: pd.Series, periode: int = 14) -> pd.Series:
    """RSI (Relative Strength Index) : thermometre de sur-achat / sur-vente (0 a 100)."""
    delta = close.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / periode, adjust=False).mean()
    pertes = (-delta.clip(upper=0)).ewm(alpha=1 / periode, adjust=False).mean()
    force = gains / pertes.replace(0, np.nan)
    return 100 - 100 / (1 + force)


# ----------------------------------------------------------------- strategies
def strat_croisement(close, courte=20, longue=50, **_):
    """Achete quand la moyenne courte passe au-dessus de la longue (tendance haussiere)."""
    ma_c = close.rolling(courte).mean()
    ma_l = close.rolling(longue).mean()
    return (ma_c > ma_l).astype(int), {"MM courte": ma_c, "MM longue": ma_l}


def strat_rsi(close, periode=14, achat=30, vente=70, **_):
    """Achete quand le RSI est bas (sur-vendu), vend quand il est haut (sur-achete)."""
    ind = rsi(close, periode)
    signal = pd.Series(np.nan, index=close.index)
    signal[ind < achat] = 1     # sur-vendu -> on achete
    signal[ind > vente] = 0     # sur-achete -> on vend
    return signal.ffill().fillna(0).astype(int), {"RSI": ind}


def strat_cassure(close, fenetre=55, sortie=20, **_):
    """Achete quand le prix depasse son plus-haut recent (cassure), sort sous le plus-bas recent.
    C'est la logique des celebres 'Turtle Traders'."""
    plus_haut = close.rolling(fenetre).max().shift(1)
    plus_bas = close.rolling(sortie).min().shift(1)
    signal = pd.Series(np.nan, index=close.index)
    signal[close > plus_haut] = 1
    signal[close < plus_bas] = 0
    return signal.ffill().fillna(0).astype(int), {"Plus-haut": plus_haut, "Plus-bas": plus_bas}


def strat_macd(close, rapide=12, lent=26, sig=9, **_):
    """MACD : achete quand l'elan (momentum) redevient positif."""
    ema_r = close.ewm(span=rapide, adjust=False).mean()
    ema_l = close.ewm(span=lent, adjust=False).mean()
    macd = ema_r - ema_l
    ligne_signal = macd.ewm(span=sig, adjust=False).mean()
    return (macd > ligne_signal).astype(int), {"MACD": macd, "Signal": ligne_signal}


def strat_tendance_200(close, longue=200, **_):
    """Le grand classique 'suiveur de tendance' : investi seulement au-dessus de la MM200."""
    ma = close.rolling(longue).mean()
    return (close > ma).astype(int), {"MM 200": ma}


# ------------------------------------------------------------------ catalogue
STRATEGIES = {
    "Croisement de moyennes (MM20/MM50)": {
        "fn": strat_croisement,
        "explication": "On suit la tendance : achat quand la moyenne courte passe au-dessus de la longue.",
        "params": {"courte": ("Moyenne courte (jours)", 5, 100, 20),
                   "longue": ("Moyenne longue (jours)", 20, 250, 50)},
    },
    "RSI — achat en zone de sur-vente": {
        "fn": strat_rsi,
        "explication": "On achete quand le marche a trop baisse (RSI bas), on vend quand il a trop monte.",
        "params": {"periode": ("Periode du RSI", 5, 30, 14),
                   "achat": ("Seuil d'achat (sur-vendu)", 10, 45, 30),
                   "vente": ("Seuil de vente (sur-achete)", 55, 90, 70)},
    },
    "Cassure de plus-haut (Turtle)": {
        "fn": strat_cassure,
        "explication": "On achete quand le prix bat son record recent, on sort quand il casse son plancher recent.",
        "params": {"fenetre": ("Plus-haut sur N jours", 10, 120, 55),
                   "sortie": ("Sortie sous le plus-bas de N jours", 5, 60, 20)},
    },
    "MACD — suivi de l'elan": {
        "fn": strat_macd,
        "explication": "On achete quand l'elan haussier reprend (MACD au-dessus de sa ligne de signal).",
        "params": {},
    },
    "Filtre MM200 — le classique long terme": {
        "fn": strat_tendance_200,
        "explication": "Investi uniquement quand le prix est au-dessus de sa moyenne 200 jours. Simple et robuste.",
        "params": {},
    },
}


# ------------------------------------------------------------------ stop-loss
def appliquer_stop_loss(close: pd.Series, signal: pd.Series, stop_pct: float) -> pd.Series:
    """Coupe la position des que la perte depuis le prix d'achat depasse stop_pct.
    Apres un stop, on attend un NOUVEAU signal d'achat pour revenir (pas de rachat immediat).
    Le test se fait sur la cloture ; la sortie prend effet le lendemain (shift du backtest)."""
    sig = signal.values.copy()
    prix = close.values
    prix_entree = None
    stoppe = False
    for i in range(len(sig)):
        if sig[i] == 1:
            if stoppe:                      # deja stoppe : on reste dehors
                sig[i] = 0
                continue
            if prix_entree is None:
                prix_entree = prix[i]       # nouvelle entree
            elif prix[i] / prix_entree - 1 <= -stop_pct / 100:
                sig[i] = 0                  # stop declenche
                stoppe = True
                prix_entree = None
        else:                               # le signal retombe : on peut re-rentrer plus tard
            prix_entree = None
            stoppe = False
    return pd.Series(sig, index=signal.index)


# ------------------------------------------------------------------- backtest
def backtester(close: pd.Series, position_brute: pd.Series,
               capital: float, frais_pct: float, stop_pct: float = 0.0):
    """Simule la strategie : rendements, frais a chaque operation, courbe de capital."""
    if stop_pct and stop_pct > 0:
        position_brute = appliquer_stop_loss(close, position_brute, stop_pct)
    position = position_brute.shift(1).fillna(0)          # on agit le lendemain du signal
    operations = position.diff().abs().fillna(position)   # 1 a chaque achat OU vente
    r_marche = close.pct_change().fillna(0)
    r_strat = r_marche * position - (frais_pct / 100) * operations

    eq_strat = capital * (1 + r_strat).cumprod()
    eq_hold = capital * (1 + r_marche).cumprod()

    pic = eq_strat.cummax()
    drawdown_strat = float((eq_strat / pic - 1).min())
    pic_h = eq_hold.cummax()
    drawdown_hold = float((eq_hold / pic_h - 1).min())

    achats = list(close.index[position.diff() == 1])
    ventes = list(close.index[position.diff() == -1])

    # ------- tableau des trades (chaque achat associe a sa vente)
    lignes = []
    for i, d_achat in enumerate(achats):
        d_vente = ventes[i] if i < len(ventes) else None
        p_achat = float(close.loc[d_achat])
        p_vente = float(close.loc[d_vente]) if d_vente is not None else float(close.iloc[-1])
        gain = p_vente / p_achat - 1 - 2 * frais_pct / 100
        lignes.append({
            "Achat le": d_achat.strftime("%d/%m/%Y"),
            "Prix d'achat": round(p_achat, 2),
            "Vente le": d_vente.strftime("%d/%m/%Y") if d_vente is not None else "— en cours —",
            "Prix de vente": round(p_vente, 2),
            "Duree (jours)": int(((d_vente or close.index[-1]) - d_achat).days),
            "Resultat": f"{gain:+.1%}",
            "_gain": gain,
        })
    trades = pd.DataFrame(lignes)
    gagnants = int((trades["_gain"] > 0).sum()) if len(trades) else 0

    return {
        "eq_strat": eq_strat, "eq_hold": eq_hold,
        "perf_strat": float(eq_strat.iloc[-1] / capital - 1),
        "perf_hold": float(eq_hold.iloc[-1] / capital - 1),
        "final_strat": float(eq_strat.iloc[-1]), "final_hold": float(eq_hold.iloc[-1]),
        "drawdown_strat": drawdown_strat, "drawdown_hold": drawdown_hold,
        "achats": achats, "ventes": ventes,
        "nb_trades": len(achats), "gagnants": gagnants,
        "trades": trades.drop(columns=["_gain"]) if len(trades) else trades,
        "position": position,
    }
