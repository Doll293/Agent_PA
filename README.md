# Mail Manager — Assistant Promos IA

Application Streamlit qui lit les emails de l'onglet **Promotions** de Gmail, les anonymise, puis utilise **Groq (LLM)** pour :

- extraire les infos clés de chaque promo (entreprise, code promo, réduction, date d'expiration)
- filtrer les vraies promos des newsletters / confirmations
- classer par catégorie (mode, tech, voyage, food...)
- générer une **fiche récapitulative** par jour / semaine / mois
- discuter avec un **assistant chat** qui connaît vos promos et propose des recommandations

Connexion Gmail via **IMAP + mot de passe d'application** (aucun `credentials.json` ni Google Cloud Console requis).

## Fonctionnalités

- **Récupération ciblée** — utilise `X-GM-RAW category:promotions` pour ne lire que les emails de l'onglet Promotions
- **Analyse IA batch** — 8 mails traités par appel API Groq (rapide)
- **Cache par `message_id`** — pas de réanalyse au refresh
- **Reconnexion IMAP automatique** — la session se reprend seule entre les pages
- **Boutons directs** — "Voir dans Gmail" et "Se désabonner" (via header `List-Unsubscribe`)
- **Fiche promos** — tableau récap filtrable par période (jour/semaine/mois)
- **Chat IA** — page dédiée pour poser des questions sur vos promos, avec liens cliquables vers chaque mail

## Installation

1. Cloner le repo et créer un environnement virtuel :

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# ou : .venv\Scripts\Activate.ps1  (Windows PowerShell)
```

2. Installer les dépendances :

```bash
pip install -r requirements.txt
```

3. Créer le fichier `.env` à partir de `.env.example` et le compléter (voir section suivante).

## Configuration

### 1. Clé API Groq (gratuite)

1. Créer un compte sur [console.groq.com](https://console.groq.com)
2. Aller sur [console.groq.com/keys](https://console.groq.com/keys)
3. Cliquer **Create API Key** → copier la clé (commence par `gsk_`)
4. La coller dans le `.env` :

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
```

### 2. Mot de passe d'application Gmail

1. Aller sur [myaccount.google.com/security](https://myaccount.google.com/security)
2. Activer la **validation en deux étapes**
3. Ouvrir [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Créer un mot de passe (nom : `Mail Manager`)
5. Copier le code à 16 caractères — vous le collerez dans le formulaire de login

> Le mot de passe n'est jamais écrit sur le disque, il est gardé en mémoire pendant la session Streamlit uniquement.

## Lancement

```bash
streamlit run mail_manager/streamlit_app.py
```

Ouvrir [http://localhost:8501](http://localhost:8501). Se connecter avec son email Gmail + mot de passe d'application.

## Navigation

L'app a deux pages accessibles depuis la sidebar :

### Page principale — Fiche Promos

- Choix du nombre de mails (20, 50, 100, 200)
- Bouton **Charger les mails promos** → récupère depuis l'onglet Promotions Gmail
- Onglet **Fiche Promos** — tableau récap + cartes filtrable par jour / semaine / mois
- Onglet **Par catégorie** — promos groupées par type (mode, tech, voyage...)
- Chaque carte : boutons **Voir dans Gmail** et **Se désabonner**

### Page Chat Promos

- Chat avec l'IA qui connaît toutes vos promos chargées
- Suggestions rapides : *"Résume-moi les meilleures promos"*, *"Quelles expirent bientôt ?"*, etc.
- Chaque `#id` dans la réponse est un lien cliquable vers le mail Gmail
- Historique de conversation persistant dans la session

## Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `GROQ_API_KEY` | *(requis)* | Clé API Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Modèle Groq à utiliser |
| `MAIL_MAX_RESULTS` | `10` | Nombre de mails par défaut |
| `MAIL_PREVIEW_LENGTH` | `220` | Longueur de l'extrait affiché |
| `SESSION_SECRET` | `change-me` | Secret de session |
| `DEBUG` | `false` | Active les logs verbeux |

## Architecture

```
mail_manager/
├── streamlit_app.py       # Page principale (login + fiche promos)
├── pages/
│   └── 1_Chat_Promos.py   # Page chat IA
├── gmail_client.py        # Client IMAP Gmail (login, fetch, unsubscribe)
├── processors.py          # Analyse Groq (batch + JSON)
├── workflow.py            # Anonymisation + analyse
├── privacy.py             # Anonymisation avant envoi à l'IA
└── config.py              # Chargement .env
```

## Sécurité

- Les mails sont **anonymisés** (emails, numéros, noms) avant envoi à l'IA
- Seul le contenu anonymisé quitte votre machine (vers l'API Groq)
- Aucune écriture sur disque : credentials, promos, cache — tout en mémoire session
- Connexion Gmail en **lecture seule** (IMAP), pas d'action destructive possible

## Limites

- Pas de base de données — les analyses sont perdues à la fermeture de l'onglet
- L'onglet Gmail "Promotions" doit être activé pour que le filtre côté serveur fonctionne
- Limite de 6000 tokens/minute sur le tier gratuit Groq (l'app compacte le contexte pour rester sous cette limite)
- Pas d'action sur les mails (suppression, archivage) — seulement lecture + liens

## Dépannage

**Connexion IMAP échoue** — vérifier que la 2FA est active et que le mot de passe d'application est correctement copié (sans espaces)

**"Aucun email trouvé dans l'onglet Promotions"** — activer l'onglet Promotions dans Gmail (Paramètres → Boîte de réception → Type de boîte → Par défaut avec onglets)

**Rate limit Groq (413)** — attendre 1 minute ou réduire le nombre de mails chargés

**Modèle décommissionné** — mettre à jour `GROQ_MODEL` dans `.env` avec un modèle actuel (voir [console.groq.com/docs/models](https://console.groq.com/docs/models))
