# Fonctionnalites Actuelles

Ce fichier resume les principales fonctionnalites actuellement presentes dans le projet du chatbot M1 Informatique.

## Chatbot

### Assistant RAG

- Repond aux questions a partir de la base documentaire locale.
- Utilise ChromaDB pour stocker et rechercher les documents vectorises.
- Utilise des embeddings HuggingFace pour la recherche semantique.
- Affiche les sources consultees quand une reponse utilise des documents.
- Supporte le reranking quand l'API du reranker est activee.
- Peut quand meme repondre avec le contexte de conversation, la memoire ou les fichiers joints si la recherche documentaire n'est pas disponible.

### Memoire Etudiante

- Memoire persistante partagee entre toutes les conversations.
- Stocke les informations utiles du profil etudiant : nom, age, lieu, statut, parcours, semestre, UEs choisies et encadrant TER.
- Extrait automatiquement les faits stables depuis les messages de l'utilisateur.
- Supporte des commandes explicites de memorisation :
  - `souviens-toi que ...`
  - `n'oublie pas que ...`
  - `remember that ...`
  - `/remember ...`
- La memoire peut etre activee, desactivee, modifiee, enregistree ou videe depuis la barre laterale.
- La memoire est utilisee dans les reponses personnelles et dans les calculs de moyenne.
- Les anciennes memoires par conversation peuvent etre recuperees dans la memoire globale.

### Conversations

- Gestion de plusieurs conversations.
- Creation d'une nouvelle conversation depuis la barre laterale.
- Sauvegarde de l'historique dans SQLite.
- Recherche dans la liste des conversations.
- Possibilite d'epingler ou de desepingler une conversation.
- Suppression de conversations.
- Rechargement automatique des anciens messages.
- Generation automatique d'un meilleur titre pour les conversations par defaut.

### Contexte De Session

- Garde les derniers echanges utiles dans le contexte du prompt.
- Aide le chatbot a comprendre les questions de suivi.
- Permet de mieux gerer les references comme "ca", "cette question" ou "mon message precedent".

### Calculateur De Moyenne

- Assistant guide pour calculer les moyennes du M1 Informatique.
- Detection du parcours depuis la question ou depuis la memoire.
- Calculs possibles par semestre, annee ou UE.
- Gestion des regles par parcours.
- Gestion des UEs optionnelles.
- Calcul des moyennes d'UE, de BCC, de compensation et du statut final.
- Possibilite d'envoyer le rapport de calcul dans la conversation.

### Simulateur "Et Si"

- Simulateur interactif pour tester des notes possibles.
- Ouverture depuis la barre laterale ou par une demande en langage naturel.
- Choix du parcours, de la periode et des UEs optionnelles.
- Sliders pour modifier les notes.
- Affichage en direct des moyennes, compensations, avertissements et statuts.
- Remise a zero des notes.
- Possibilite d'envoyer le rapport du simulateur dans le chat.

### Fichiers Joints

- Envoi de plusieurs fichiers directement dans le chat.
- Formats documents supportes : PDF, TXT, MD et DOCX.
- Formats images supportes : PNG, JPG, JPEG et WEBP.
- Extraction du texte des documents joints.
- Analyse des images avec Gemini Vision quand la cle est disponible.
- Repli OCR avec Tesseract quand Gemini Vision n'est pas disponible.
- Ajout du contenu extrait dans le contexte envoye au modele.

### Export

- Export de la derniere reponse ou de toute la conversation.
- Export en PDF.
- Export en DOCX.
- Generation de rapports propres et telechargeables.
- Acces aux fichiers generes depuis la barre laterale.

### Voix Et Actions Rapides

- Saisie vocale depuis le champ de chat.
- Lecture vocale des reponses de l'assistant.
- Bouton pour copier une reponse.
- Bouton pour regenerer une reponse.
- Boutons like/dislike.
- Enregistrement du feedback dans SQLite pour l'administration.

### Interface Et Branding

- Interface Streamlit modernisee.
- Style visuel inspire UVSQ / Universite Paris-Saclay.
- Logo personnalise dans `app/assets/m1-assistant-logo.png`.
- Systeme de couleurs et de typographie injecte par CSS.
- Hero section avec titre, sous-titre, logo et statuts des outils.
- Indicateurs de statut pour RAG, reranker, memoire, fichiers et LLM.
- Mise en page responsive.
- Bouton de menu de la barre laterale corrige : il apparait uniquement quand la barre laterale est fermee.
- Injection CSS corrigee pour eviter l'affichage du CSS brut dans la page.

## Tableau De Bord Admin

### Vue Generale

- Nombre total de messages.
- Taux de reponses reussies.
- Nombre de questions sans reponse.
- Nombre de messages du jour.
- Nombre de likes.
- Taux de satisfaction.
- Nombre de corrections en attente.
- Export CSV de tous les logs.

### Onglet Review

- Liste des questions sans reponse.
- Liste des interactions recentes.
- Affichage du statut, du feedback, de la date, des sources et des outils utilises.
- Aide a reperer les questions qui doivent etre corrigees ou ameliorees.

### Onglet Feedback

- Workflow de correction pour les reponses dislikees.
- Filtrage par statut : pending, in review, resolved ou all.
- Affichage de la question etudiante, de la reponse originale, du commentaire de feedback, des outils et des sources.
- Ecriture d'une reponse corrigee par l'admin.
- Ajout de notes internes.
- Suivi du statut de correction et de la personne qui corrige.
- Ajout possible d'une correction dans la base de connaissance.
- Reconstruction possible de la base vectorielle apres correction.
- Export CSV de la file de corrections.

### Onglet Trends

- Graphique d'evolution des messages.
- Vues sur 7, 14 ou 30 jours.
- Graphique des reponses trouvees et non trouvees.
- Suivi de l'utilisation et de la qualite du chatbot.

### Onglet Knowledge Base

- Upload de documents admin dans la base documentaire.
- Formats supportes : PDF, TXT et MD.
- Liste des fichiers presents dans le dossier `data/`.
- Suppression de fichiers de connaissance.
- Reconstruction de la base ChromaDB.
- Nettoyage de la base vectorielle.
- Creation manuelle d'entrees de connaissance depuis le dashboard.
- Sauvegarde des entrees manuelles en Markdown dans `data/admin_entries/`.

### Onglet Settings

- Sauvegarde des reglages dans `data/admin_settings.json`.
- Activation ou desactivation des fonctionnalites :
  - upload de fichiers
  - upload d'images
  - suggestions
  - entree vocale
  - sortie vocale
  - export PDF/DOCX
  - memoire etudiante
  - reranker
- Choix du backend LLM :
  - auto
  - vLLM
  - fallback vLLM
  - Gemini
- Reglages de generation :
  - temperature
  - nombre maximal de tokens
- Reglages des modeles :
  - modele vLLM principal
  - modele fallback
  - modele Gemini
  - modele vision
- Reglages de recherche :
  - nombre de documents recuperes
  - nombre de documents gardes apres reranking
  - nombre final de contextes envoyes au modele
  - taille maximale du texte extrait des fichiers joints
- Sauvegarde des reglages sans redemarrer l'application.
- Reinitialisation des reglages par defaut.

### Onglet Evaluations

- Lecture des rapports d'evaluation depuis `evaluation_chatbot`.
- Affichage du nombre de questions evaluees.
- Affichage du taux de reponse.
- Affichage du score hybride quand il existe.
- Affichage des resultats dans un tableau.
- Rappel de la commande pour lancer les evaluations.

### Onglet All Logs

- Historique complet des logs du chatbot.
- Filtrage par :
  - tous les logs
  - reponses trouvees
  - reponses non trouvees
  - likes
  - dislikes
- Inspection detaillee du comportement du chatbot.

## Infrastructure Du Projet

- Base SQLite pour les conversations, logs, feedbacks et memoire etudiante.
- Base ChromaDB pour la recherche RAG.
- Corrections admin reinjectables dans la base de connaissance.
- Configuration locale avec le fichier `.env`.
- Modele de configuration disponible dans `.env.example`.
- Guide d'installation dans `setup.md`.
- Outil d'evaluation disponible dans `tools/evaluate_chatbot.py`.
- Support du serveur vLLM via tunnel SSH.
- Support de Gemini comme solution de repli quand la cle est configuree.
