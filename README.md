# chatbot_M1_AMIS_2025_2026

##Un chatbot pour le M1 informatique

Une formation universitaire possède un ensemble de règles et de procédures que les étudiants
doivent comprendre et suivre pour réussir sereinement leur parcours. C’est encore plus le cas dans
le contexte du M1 informatique qui regroupe 4 parcours et dépend à la fois de l’UVSQ et de
l’Université Paris-Saclay.

Le projet Chatbot pour le M1 informatique vise à développer un assistant virtuel capable d’aider les
étudiants du Master 1 Informatique dans leurs démarches académiques et administratives.
Les tâches à réaliser sont donc :
• étudier la démarche de conception d’un chatbot
• identifier les documents et informations clés à intégrer dans le chatbot
• implémenter un preuve de concept de chatbot utilisant des technologies modernes (par
exemple, des modèles de langage pré-entraînés)

Encadrement : Yehia TAHER <yehia.taher@uvsq.fr>, Stéphane LOPES <stephane.lopes@uvsq.fr>

Etudiant :  BESSAA Abderraouf <abderraouf.bessaa@ens.uvsq.fr>
            TIGHILT Idir <idir.tighilt@ens.uvsq.fr>




# Réunion de Lancement du TER - Chatbot pour Étudiants M1 
## Objectif du Projet   
Le projet consiste à développer un agent conversationnel (chatbot) destiné aux étudiants de 
M1 pour répondre à leurs questions concernant leurs études. L'objectif est de créer un 
système capable de fournir des réponses précises sur   Les modalités de contrôle de connaissances, Les coefficients et crédits ECTS des UE, Les règlements d'études, Les questions administratives liées au M1...   

## Approche Technique : RAG (Retrieval Augmented Generation)   
Le projet s'appuiera sur la technologie RAG plutôt que sur un chatbot traditionnel à règles 
strictes. Cette approche permet d'avoir Interface conversationnelle, Base de connaissances structurée, ransformation de la question utilisateur en vecteur (embedding), Recherche de similarité dans la base vectorielle, Récupération des chunks de documents pertinents, Génération de réponse via LLM local avec prompt augmenté.

## Évolution du Système
au depart on prevoit de coder en dur quellques fonctionelites pour tester des differents approches en suite on suite viendra l'implementation de fonctionalites plus avance comme le une interface administrateur pour l'ajout de nouveaux documents et la capacité de téléversement de fichiers (Word, PDF)

### Livrables Attendus 
- Recherches sur les différentes générations de chatbots
- Étude approfondie des RAG et outils associés
- Preuve de concept fonctionnelle
- Documentation technique complète   


## Points d'action   
- Effectuer des recherches sur les chatbots et les technologies RAG
- Identifier et analyser les documents sources (règlement Paris-Saclay, descriptions de 
masters)
- Préparer une première ébauche de l'approche technique pour la prochaine réunion
- Documenter les trouvailles et liens intéressants au fur et à mesure des recherches
