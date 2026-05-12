# Recherches sur les chatbots

## 1. Qu'est-ce qu'un chatbot ?

Un chatbot est un programme ou une application avec lequel les utilisateurs peuvent converser par le biais de la voix ou du texte. Vous avez peut-être utilisé un chatbot pour les ventes ou l'assistance client en ligne. Les bots simulent une conversation humaine et tentent de répondre à vos questions avant de vous transmettre à un représentant humain.

Les chatbots ont été développés pour la première fois dans les années 1966 et la technologie qui les fait fonctionner a évolué au fil du temps. Les chatbots utilisent traditionnellement des règles prédéfinies pour converser avec les utilisateurs et fournir des réponses scriptées. Les chatbots modernes utilisent le traitement du langage naturel (NLP) pour comprendre les utilisateurs et peuvent répondre à des questions complexes avec pertinence et précision. On peut utiliser les chatbots pour mettre à l'échelle, personnaliser et améliorer la communication dans tous les domaines, des flux de travail du service client à la gestion DevOps.

---

## 2. Historique des chatbots

| **Période**    | **Chatbot**                        | **Ce qui le caractérise**                                                                                    |
| -------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **1966**       | **ELIZA** (MIT)                    | Premier chatbot célèbre. Simulait un psychologue. Basé sur des règles simples et des mots-clés. Pas de vraie compréhension. |
| **1972**       | **PARRY**                          | Simulait un patient atteint de schizophrénie. Toujours basé sur des règles, mais plus complexe.              |
| **Années 90**  | **ALICE**                          | Utilisait AIML (Artificial Intelligence Markup Language). Gros système de réponses prédéfinies.              |
| **1997**       | **Jabberwacky**                    | Apprend de nouvelles réponses au lieu d'utiliser une base de données statique.                               |
| **2011**       | **Siri**                           | Début des assistants vocaux grand public. Introduction du NLP moderne + reconnaissance vocale.               |
| **2014–2018**  | **Alexa, Google Assistant**        | IA plus avancée, intégration avec services, machine learning.                                                |
| **2020+**      | **GPT, ChatGPT, Claude, Gemini**   | Modèles de langage géants capables de générer du texte naturel et contextuel.                                |

> **Avant 2010** = chatbots **scriptés**  
> **Après 2020** = chatbots **basés sur l'IA générative**

---

## 3. Les types et les générations de chatbots

Les chatbots sont des programmes capables de simuler une conversation humaine, par texte ou par voix. Ils analysent les messages des utilisateurs, en extraient le sens, puis fournissent des réponses quasi instantanées. Avec l'évolution de l'intelligence artificielle, les chatbots sont devenus de plus en plus sophistiqués.  
On peut les comprendre à travers leurs types de fonctionnement et leurs générations technologiques.

---

### 1ère génération — Chatbots basés sur des règles (Rule-Based)

**Période : 1960–2000**

Ce sont les chatbots les plus simples et les plus anciens.

**Technologie utilisée :**
- Scripts prédéfinis
- Arbres décisionnels
- Menus, boutons, choix guidés
- Logique : "Si l'utilisateur dit X → répondre Y"

**Fonctionnement :**

L'utilisateur suit un parcours fixe composé de questions et de réponses prédéterminées. Il ne peut souvent pas écrire librement, mais choisit parmi des options proposées. Le chatbot possède un "dictionnaire" interne qui associe chaque question à une réponse précise — identique pour tous les utilisateurs.

**Exemples :**
- ELIZA (1966 — un des premiers chatbots de l'histoire, utilisant des patterns de reconnaissance)
- Bots FAQ sur les sites web
- Assistants de support simples avec menus à choix multiples

**Avantages :**
- Simples à créer
- Réponses prévisibles et contrôlables
- Adaptés aux tâches basiques (FAQ, suivi de commande)
- Peu coûteux

**Limites :**
- Aucune compréhension réelle du langage
- Se bloquent si la question sort du script
- Difficiles à faire évoluer
- Inadaptés aux situations complexes
- Expérience utilisateur rigide et frustrante

**Type correspondant :** Chatbots basés sur des règles

---

### 2ème génération — Chatbots basés sur mots-clés et NLP

**Période : 2000–2015**

Cette génération introduit une première forme de "compréhension".

**Technologie utilisée :**
- Reconnaissance de mots-clés
- NLP basique (Natural Language Processing)
- NLU de base (Natural Language Understanding)
- Machine Learning supervisé
- Détection d'intention
- Classification de texte

**Fonctionnement :**

Le chatbot analyse les mots importants dans la phrase pour identifier l'intention.

**Exemple :**
- "Je veux annuler ma commande"
- "Comment supprimer mon achat ?"

→ Le bot comprend que l'intention est **annuler un achat**

Les réponses restent cependant scriptées et préprogrammées.

**Outils typiques :**
- Dialogflow (Google)
- IBM Watson Assistant
- Microsoft Bot Framework
- Rasa (open source)

**Avantages :**
- Meilleure compréhension du langage naturel
- Peut apprendre à partir des données d'entraînement
- Plus flexible que les bots à règles
- Gère les variations linguistiques

**Limites :**
- Toujours limités aux scénarios prévus à l'avance
- Peu créatifs dans les réponses
- Mauvaise gestion des phrases ambiguës ou complexes
- Nécessite beaucoup d'exemples pour chaque intention
- Difficulté avec le contexte conversationnel

---

### 3ème génération — Chatbots optimisés par l'IA (IA conversationnelle)

**Période : 2015–2023**

Ici, on entre dans l'ère de l'intelligence artificielle avancée.

**Technologie utilisée :**
- Deep Learning
- Réseaux neuronaux profonds
- NLU avancé (Natural Language Understanding)
- NLG (Natural Language Generation)
- Architecture Transformers
- Grands modèles de langage (LLM — Large Language Models)
- IA générative

Ces chatbots ne suivent plus seulement des règles :
- Ils analysent le contexte
- Ils prédisent les mots suivants
- Ils génèrent des réponses dynamiques et naturelles

**Fonctionnement :**

Ils peuvent :
- Comprendre des questions complexes et nuancées
- Détecter le ton, le sentiment, voire le sarcasme
- Maintenir un contexte conversationnel
- Passer d'un sujet à un autre de manière fluide
- Répondre avec humour ou empathie
- Générer du contenu original

**Exemple :**

*"Je sais que c'est l'heure de pointe, mais dans combien de temps puis-je recevoir ma nourriture ?"*

→ Le chatbot comprend le contexte (heure de pointe), l'implication (délai possiblement plus long) et répond naturellement en tenant compte de la situation.

**Exemples de chatbots :**
- ChatGPT (OpenAI)
- Claude (Anthropic)
- Gemini (Google)
- Copilot (Microsoft)

**Avantages :**
- Conversations naturelles et fluides
- Création de texte, résumé, traduction
- Aide au code et à l'analyse
- Capacité créative et adaptabilité
- Apprentissage contextuel durant la conversation
- Gestion de tâches variées sans reprogrammation

**Limites :**
- Peuvent générer des **hallucinations** (informations incorrectes présentées avec assurance)
- Dépendent fortement de la qualité des données d'entraînement
- Manque de connaissances en temps réel (selon le modèle)
- Coût de calcul et d'infrastructure élevé
- Questions éthiques (biais, confidentialité)
- Difficulté à vérifier la fiabilité des réponses

**Type correspondant :** Chatbots optimisés par l'IA générative

---

### 4ème génération — Agents IA

**Période : 2023 à aujourd'hui — En cours de généralisation**

On dépasse le simple chatbot : on parle maintenant d'**agents intelligents** capables d'agir de manière autonome.

**Technologies supplémentaires :**
- Mémoire à long terme et persistante
- Accès à des outils externes (web, bases de données, APIs, code)
- Raisonnement multi-étapes (chain-of-thought)
- Automatisation de tâches complexes
- Planification et exécution autonomes
- Utilisation d'outils (tool use / function calling)

**Capacités :**

Ces systèmes peuvent :
- **Planifier** des actions et des stratégies
- **Utiliser** des outils externes (moteur de recherche, calculatrice, bases de données)
- **Manipuler** des fichiers et documents
- **Gérer** des tâches complexes de bout en bout
- **Exécuter** du code et interagir avec des systèmes
- **Apprendre** de leurs interactions passées

**Ils ne font plus que discuter : ils agissent.**

**Exemples d'agents IA :**
- Claude avec Computer Use (Anthropic)
- AutoGPT et BabyAGI
- Microsoft Copilot avec plugins
- Agents créés via LangChain, CrewAI, AutoGen
- Agent Google Gemini
- Devin (agent de codage)

**Différence clé : Chatbot vs Agent**
- **Chatbot** : répond aux questions, dialogue
- **Agent** : prend des initiatives, accomplit des tâches, utilise des outils

**Avantages :**
- Très autonomes dans l'accomplissement de tâches
- Peuvent résoudre des problèmes complexes multi-étapes
- Interaction plus proche d'un assistant intelligent polyvalent
- Capacité d'orchestration entre plusieurs outils
- Adaptation dynamique aux besoins

**Limites :**
- Fiabilité et contrôle encore en amélioration
- Risques de comportements imprévus
- Enjeux éthiques importants (autonomie, responsabilité)
- Questions de sécurité (accès aux systèmes)
- Coût computationnel très élevé
- Nécessite une supervision humaine

---

## Meilleures pratiques en matière de création de chatbots

La création d'un chatbot qui répond aux attentes des gens et correspond à nos objectifs commerciaux nécessite de prêter attention aux meilleures pratiques.

**Transparence**

Pour plus de transparence, informez les clients lorsqu'ils interagissent avec un chatbot alimenté par l'IA. Cette information permet de définir des attentes claires, d'accroître la satisfaction et d'améliorer l'expérience client. Vous pouvez renforcer la confiance des clients et accroître l'acceptation des chatbots conversationnels.

**Intégrations**

Des réponses efficaces et instantanées sont essentielles à la réussite d'un chatbot. Intégrez votre base de connaissances pour donner à votre chatbot un accès immédiat aux informations pertinentes. Connectez-le à d'autres systèmes dorsaux tels que le CRM ou l'ERP pour répondre avec des informations personnalisées basées sur l'historique des interactions du client ou les détails de son compte. Ainsi, votre chatbot peut répondre aux requêtes courantes avec précision, réduire le temps de réponse et améliorer la satisfaction des utilisateurs.

**Tester et améliorer**

Un chatbot nécessite des tests continus pour s'assurer qu'il répond aux normes de performance. Mettez en œuvre l'automatisation pour surveiller les interactions du chatbot afin de garantir la conformité aux directives de service. Utilisez les informations issues des commentaires des clients pour optimiser les interactions avec les chatbots et étendre leur utilisation. Les informations vous permettent également de développer de nouveaux cas d'utilisation, de prendre en charge des langues supplémentaires et d'améliorer le service sur différents canaux. Cette approche axée sur les données garantit que votre chatbot reste pertinent et répond aux besoins actuels des clients.
