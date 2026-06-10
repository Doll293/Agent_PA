# Mail Manager

Version Streamlit pour lire 10 mails Gmail en lecture seule, anonymiser le texte, puis afficher une categorie et une suggestion simple. La classification utilise `transformers`, et retombe sur des regles locales si le modele ne peut pas etre charge.

## Installation

1. Creer un fichier `.env` a partir de `.env.example`.
2. Mettre `credentials.json` a la racine du projet.
3. Creer un environnement virtuel et installer les dependances :

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

Pour des logs plus verbeux, mettre dans `.env` :

```env
DEBUG=true
```

> Le premier demarrage peut etre plus long car `transformers` telecharge le modele.

## Limites du prototype

- pas de base de donnees
- pas d'actions sur les mails
- pas de corps complet stocke
- pas de tests automatiques
- modele `transformers` potentiellement long a charger au premier demarrage

## Demo rapide

1. Lancer l'application.
2. Ouvrir `http://localhost:8501`.
3. Cliquer sur `Se connecter avec Gmail`.
4. Se connecter avec le compte de test.
5. Revenir sur l'application.
6. Montrer les 10 derniers mails, la version anonymisee, la categorie et la suggestion.

Le prototype lit seulement quelques mails Gmail en lecture seule, anonymise avant le classement, et ne fait aucune action destructive.
