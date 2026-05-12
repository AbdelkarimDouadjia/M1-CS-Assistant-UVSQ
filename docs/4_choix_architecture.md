# Choix de l'architecture — Analyse comparative des alternatives technologiques

Avant de choisir le RAG, nous avons évalué plusieurs approches alternatives pour comprendre leurs limites dans notre contexte universitaire.

---

## Alternative 1 : Fine-tuning d'un modèle

Cette approche consiste à entraîner directement un modèle de langage sur les données universitaires. Le modèle mémoriserait ainsi toutes les informations spécifiques à l'université.

**Limites identifiées :**

- **Risque d'hallucinations élevé** : le modèle peut inventer des informations.
- **Mise à jour extrêmement contraignante** : chaque fois que l'université modifie un règlement ou une procédure, il faut réentraîner entièrement le modèle. Avec le RAG, il suffit d'ajouter le nouveau document.
- **Impossibilité de citer les sources** : problème majeur dans un contexte universitaire où la traçabilité est essentielle. Le modèle "sait" l'information mais ne peut pas indiquer qu'elle provient du "Règlement pédagogique, article 5.2".
- **Coûts significativement plus élevés** : un fine-tuning de GPT-4 peut coûter entre 100 et 1000 dollars selon la taille des données.

---

## Alternative 2 : Prompt Engineering avec contexte long

Cette méthode consiste à inclure tous les documents universitaires directement dans chaque prompt envoyé au modèle.

**Limites identifiées :**

- **Limites de tokens** : GPT-4 Turbo accepte 128 000 tokens (environ 300 pages) et Claude Opus 200 000 tokens (environ 500 pages). Si l'université possède plus de 1000 pages de documentation, cette approche devient impossible.
- **Coût par question prohibitif** : GPT-4 facture 0,01 dollar par 1000 tokens en entrée. Avec 100 000 tokens par requête, chaque question coûterait 1 dollar, contre 0,001 à 0,01 dollar avec le RAG (soit 100 fois moins cher).
- **Lenteur** : traiter 100 000 tokens prend entre 10 et 30 secondes, alors que le RAG répond en 1 à 3 secondes.
- **Inefficacité** : le modèle doit lire l'intégralité des documents même si la réponse se trouve dans un seul paragraphe. 99 % du contexte devient inutile pour chaque question.
- **Dégradation de qualité** : le modèle a tendance à "oublier" les détails au milieu de longs documents, un phénomène appelé "lost in the middle".

---

## Alternative 3 : Base de données traditionnelle avec règles

Cette solution implique de créer manuellement des paires de questions-réponses stockées dans une base de données classique avec recherche par mots-clés.

**Limites identifiées :**

- **Recherche basique et littérale** : le système ne comprend pas que "procédure de réinscription" et "comment se réinscrire" sont des questions identiques. Sans compréhension sémantique, beaucoup de questions légitimes restent sans réponse.
- **Maintenance cauchemardesque** : il faut créer manuellement chaque paire question-réponse. Pour couvrir 1000 questions possibles, il faut créer 1000 entrées manuellement.
- **Rigidité frustrante** : si un étudiant demande "délai de réinscription" au lieu de "date limite de réinscription", le système ne trouve pas de résultat.
- **Absence d'intelligence** : le système ne peut pas combiner plusieurs sources pour répondre à une question complexe comme "Puis-je me réinscrire si j'ai validé seulement 40 crédits l'année dernière ?"

**Cas d'usage approprié :** Cette approche fonctionne uniquement pour une FAQ très simple avec moins de 100 questions fixes. Elle peut servir de complément au RAG pour les questions les plus fréquentes nécessitant des réponses ultra-rapides.

---

## Alternative 4 : Knowledge Graph (Graphe de connaissances)

Cette méthode structure toutes les connaissances universitaires sous forme de graphe de relations entre entités.

**Limites identifiées :**

- **Complexité de mise en place très importante** : il faut structurer manuellement toutes les données universitaires, créer les entités (étudiants, cours, enseignants, règlements), définir toutes les relations possibles, et concevoir le schéma complet. Ce travail peut prendre des semaines voire des mois.
- **Manque de flexibilité** : chaque fois qu'un nouveau document est ajouté, il faut potentiellement restructurer une partie du graphe. Avec le RAG, on ajoute simplement le document.
- **Inadéquation pour le texte libre** : les graphes de connaissances excellent pour les données structurées et relationnelles (qui enseigne quel cours, qui est inscrit où), mais sont mal adaptés aux paragraphes de texte descriptif comme les procédures ou les règlements.

---

## Références

- [https://en.wikipedia.org/wiki/Chatbot](https://en.wikipedia.org/wiki/Chatbot)
- [https://www.tonic.ai/guides/rag-chatbot](https://www.tonic.ai/guides/rag-chatbot)
- [https://www.youtube.com/watch?v=xf3gAFclwqo](https://www.youtube.com/watch?v=xf3gAFclwqo)
- [https://olivierleclere.ch/blog/2024/03/fine-tuning-ou-rag/](https://olivierleclere.ch/blog/2024/03/fine-tuning-ou-rag/)
