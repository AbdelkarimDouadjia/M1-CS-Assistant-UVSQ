# Architecture RAG recommandée

## Justification technique du choix du RAG pour le chatbot universitaire

Pour répondre aux besoins spécifiques de notre chatbot universitaire, nous avons opté pour une architecture RAG (Retrieval-Augmented Generation) structurée autour de quatre composants principaux.

---

## Composants de l'architecture

### Base de données vectorielle

Le système utilise une base de données vectorielle qui stocke tous les documents universitaires (règlements, guides, procédures) sous forme d'embeddings (représentations vectorielles). Plusieurs options sont envisageables : Pinecone, Weaviate, Qdrant, ou PostgreSQL avec l'extension pgvector. Cette base permet d'effectuer des recherches sémantiques rapides en comparant la similarité entre la question de l'étudiant et les contenus disponibles.

### Pipeline de traitement des documents

Les documents administratifs suivent un processus de transformation en plusieurs étapes. D'abord, ils sont découpés intelligemment en segments logiques (chunking) par paragraphe ou section. Ensuite, chaque segment est converti en vecteur mathématique grâce à un modèle d'embedding (OpenAI, Cohere, ou des modèles open-source). Ces vecteurs sont finalement stockés dans la base vectorielle pour permettre la recherche.

### Backend API

Le serveur backend joue le rôle d'orchestrateur. Il reçoit les questions des utilisateurs, recherche les passages pertinents dans la base vectorielle, combine ces passages avec la question originale, envoie le tout au modèle de langage (LLM), et retourne la réponse accompagnée de ses sources.

### LLM avec instructions strictes

Le modèle de langage est configuré avec des instructions système cruciales pour garantir la fiabilité. Il doit :
- Répondre uniquement en se basant sur les documents fournis
- Indiquer clairement lorsque l'information n'est pas disponible dans ses documents
- Ne jamais spéculer
- Toujours citer ses sources avec précision

---

## Mesures de fiabilité critiques

Pour éviter les erreurs et garantir la qualité des réponses, plusieurs mécanismes sont mis en place.

### Validation des réponses

Un système de scoring de confiance évalue chaque réponse générée. Le système vérifie que la réponse provient bien du contexte fourni et applique un seuil minimum de similarité avant de déclencher une réponse. Si le score de confiance est trop faible, le chatbot préfère indiquer qu'il ne peut pas répondre.

### Citations obligatoires

Chaque réponse doit obligatoirement référencer le document source dont elle provient. L'extrait exact utilisé pour construire la réponse est affiché à l'utilisateur, permettant une vérification facile et renforçant la transparence.

### Mode conservateur

Les paramètres du modèle de langage sont configurés en mode conservateur avec une température fixée à 0 pour obtenir des réponses déterministes et cohérentes. Le système privilégie toujours une réponse "Je ne sais pas" plutôt qu'une réponse incertaine ou approximative.

### Boucle de feedback

Une interface d'administration permet aux gestionnaires universitaires de corriger et valider les réponses du chatbot. Tous les logs des interactions sont conservés de manière détaillée pour analyser les performances et identifier les points d'amélioration.
