# Mail Manager - Promotions

Version Streamlit qui lit les mails de l'onglet Promotions Gmail en lecture seule, anonymise le texte, puis utilise un LLM gratuit (Groq) pour produire, en un seul appel : un resume, une categorie, un score de pertinence selon vos envies, le code promo, la date d'expiration et un signalement des fausses promos permanentes.

## Installation

1. Creer un fichier `.env` a partir de `.env.example`.
2. Mettre `credentials.json` a la racine du projet.
3. Creer une cle API gratuite sur https://console.groq.com/keys et la mettre dans `GROQ_API_KEY`.
4. Creer un environnement virtuel et installer les dependances :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration Google

1. Ouvrir Google Cloud Console.
2. Creer un projet si besoin.
3. Activer l'API Gmail.
4. Aller dans `Google Auth Platform > Clients`.
5. Cliquer sur `Create client`, choisir `Web application`.
6. Donner un nom, par exemple `mail-manager-local`.
7. Dans `Authorized redirect URIs`, ajouter :
   `http://localhost:8501`
8. Creer le client, telecharger le JSON.
9. Le renommer en `credentials.json` et le placer a la racine du projet.

Le scope utilise est : `https://www.googleapis.com/auth/gmail.readonly`

> En mode test Google Cloud, ajouter le compte Gmail dans les `test users`.

## Lancement

```powershell
streamlit run mail_manager/streamlit_app.py
```

Puis ouvrir : `http://localhost:8501`

Variables utiles dans `.env` :

```env
DEBUG=true
GROQ_MODEL=llama-3.3-70b-versatile
MAIL_MAX_RESULTS=10
MAIL_BODY_MAX_CHARS=1500
```

## Fonctionnalites

- lecture de l'onglet Promotions uniquement (`CATEGORY_PROMOTIONS`)
- anonymisation (emails, telephones, liens) avant envoi au LLM
- resume + categorie + score de pertinence /10 selon les envies saisies
- extraction du code promo avec bouton copier
- date d'expiration avec badge d'urgence (rouge si moins de 3 jours)
- detection des promos permanentes suspectes
- lien direct vers le mail dans Gmail
- lien de desabonnement (header `List-Unsubscribe`) quand disponible
- tri par pertinence, filtres par categorie et recherche texte

## Limites du prototype

- pas de base de donnees
- pas d'actions sur les mails (le desabonnement ouvre simplement le lien de l'expediteur)
- pas de tests automatiques
- quota du tier gratuit Groq (largement suffisant pour un usage perso)
