# Backtest Trading — application web

Application web pour **tester des stratégies de trading** sur de vrais prix historiques,
sans risquer d'argent réel. Construite avec [Streamlit](https://streamlit.io).

## Ce qu'elle fait

- **Recherche mondiale** : n'importe quelle action, ETF, crypto, indice ou devise (via Yahoo Finance)
- **5 stratégies** : croisement de moyennes, RSI, cassure de plus-haut (Turtle), MACD, filtre MM200
- **Frais de transaction** et **stop-loss** paramétrables
- **4 onglets** : résultat, détail de chaque trade, classement des stratégies, comparaison d'actifs
- Comparaison systématique avec le « ne rien faire » (buy & hold)

## Lancer en local

```bash
pip install -r requirements.txt
python tools/patch_loader.py
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501

### À propos de `tools/patch_loader.py`

Ce script ajoute un écran d'accueil aux couleurs du projet, affiché **pendant que
Streamlit démarre** — avant même que le code de l'application s'exécute. Il s'efface
tout seul dès que le tableau de bord est dessiné.

Pour cela il modifie `index.html` **à l'intérieur du paquet Streamlit installé**.
Deux conséquences :

- Il doit être **rejoué après chaque `pip install`**, sinon la réinstallation
  l'écrase. Le `render.yaml` s'en charge automatiquement au déploiement.
- Il est sans risque : idempotent (relançable), il refuse d'agir s'il ne reconnaît
  pas la structure du fichier, et `python tools/patch_loader.py --retirer` remet
  la page d'origine.

## Déployer sur Render

Le fichier `render.yaml` configure tout automatiquement (Blueprint Render).

**1. Envoyer le code sur GitHub**

```bash
git remote add origin https://github.com/<ton-compte>/<ton-depot>.git
git branch -M main
git push -u origin main
```

**2. Créer le service sur Render**

- Aller sur [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**
- Connecter le dépôt GitHub : Render lit `render.yaml` et configure le service seul
- Cliquer sur **Apply**

Le premier déploiement prend environ 5 minutes (installation des dépendances).

**Déploiement manuel** (sans Blueprint), si tu préfères passer par *New → Web Service* :

| Réglage | Valeur |
|---|---|
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` |
| Health check path | `/_stcore/health` |

⚠️ La *start command* est le point critique : sans `--server.port $PORT --server.address 0.0.0.0`,
Render ne détecte pas le service et le déploiement échoue.

## Bon à savoir sur le plan gratuit Render

- **Mise en veille** : le service s'endort après ~15 minutes sans visite. La visite suivante
  prend environ 50 secondes (démarrage à froid). C'est normal.
- **Mémoire limitée** (512 Mo) : éviter les périodes très longues sur beaucoup d'actifs à la fois.
- **Données Yahoo Finance** : depuis un serveur partagé, Yahoo peut limiter le nombre de requêtes.
  Les résultats sont mis en cache 1 heure pour réduire ce risque.

## Structure

| Fichier | Rôle |
|---|---|
| `app.py` | Interface web (barre latérale, 4 onglets, graphiques) |
| `strategies.py` | Les 5 stratégies, le moteur de backtest et le stop-loss |
| `render.yaml` | Configuration de déploiement Render |
| `.streamlit/config.toml` | Réglages Streamlit (thème, mode serveur) |

## Avertissement

Outil éducatif. Résultats passés simulés, frais inclus mais hors impôts et écarts d'exécution.
**Ceci n'est pas un conseil d'investissement.**
