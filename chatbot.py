# ================================================================
# chatbot.py - Interface du chatbot RAG (Retrieval-Augmented Generation)
# ================================================================
# Ce fichier crée l'interface utilisateur du chatbot avec Streamlit.
# Le chatbot utilise la technique RAG :
#   1. L'utilisateur pose une question
#   2. On cherche les documents pertinents dans ChromaDB (retrieval)
#   3. On envoie la question + les documents trouvés à l'IA (generation)
#   4. L'IA répond en se basant UNIQUEMENT sur les documents fournis
#   5. La question et la réponse sont enregistrées dans SQLite (logging)
# ================================================================

# --- Imports ---
import streamlit as st                          # Framework pour créer l'interface web
from langchain_google_genai import (
    ChatGoogleGenerativeAI,                     # Modèle de chat Google Gemini (génère les réponses)
    GoogleGenerativeAIEmbeddings,               # Modèle d'embeddings (transforme le texte en vecteurs)
)
from langchain_chroma import Chroma             # Base de données vectorielle ChromaDB
from dotenv import load_dotenv                  # Charge les variables d'environnement (.env)
from chat_logger import log_question            # Notre module pour enregistrer les questions dans SQLite
from uuid import uuid4                          # Génère des identifiants uniques pour les sessions

# Charger la clé API Google depuis le fichier .env
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

# --- Configuration de la page Streamlit ---
# Définit le titre de l'onglet, la disposition large, et masque la sidebar
st.set_page_config(
    page_title="RAG Chatbot",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Style CSS personnalisé ---
# Améliore l'apparence des messages du chat
st.markdown("""
    <style>
    .main { padding-top: 0; }
    .stChatMessage { background-color: #f0f2f6; border-radius: 10px; padding: 15px; }
    </style>
    """, unsafe_allow_html=True)


# configuration
CHROMA_PATH = r"chroma_db"

# ================================================================
# INITIALISATION DE LA SESSION
# ================================================================
# Streamlit recharge tout le script à chaque interaction.
# st.session_state permet de garder des données entre les rechargements.

# Historique des messages (liste de dictionnaires {role: "user"/"assistant", content: "..."})
if "messages" not in st.session_state:
    st.session_state.messages = []
if "questions" not in st.session_state:
    st.session_state.questions = []
if "responces" not in st.session_state:
    st.session_state.responces = []

# Identifiant unique de la session utilisateur
# Permet de regrouper les questions d'un même utilisateur dans les logs
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())

# ================================================================
# CHARGEMENT DES MODÈLES IA
# ================================================================
# @st.cache_resource : met en cache les modèles pour ne pas les recharger
# à chaque fois que Streamlit recharge la page (gain de performance)
@st.cache_resource
def load_models():
    """
    Charge et retourne les modèles nécessaires au chatbot :
    - embeddings_model : convertit le texte en vecteurs numériques
      (utilisé pour chercher les documents similaires)
    - llm : le modèle de langage Gemini qui génère les réponses
    - vector_store : la base ChromaDB qui stocke les documents vectorisés
    - retriever : l'outil de recherche qui trouve les 5 documents les plus pertinents
    """
    # Modèle d'embeddings Google (même modèle que dans ingest_database.py)
#     embeddings_model = HuggingFaceEmbeddings(
#     model_name="./models/bge-base-en-v1.5",  # chemin local
#     model_kwargs={"device": "cpu"}
# )
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # Modèle de chat Gemini (temperature=0.5 : semi-créatif, semi-factuel)
    llm = ChatGoogleGenerativeAI(temperature=0.5, model='gemini-2.5-flash')

    # Connexion à la base de données ChromaDB
    vector_store = Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    retriever = vector_store.as_retriever(search_kwargs={'k': 8}, score_threshold=0.6)
    return llm, retriever

# Charger les modèles au démarrage
llm, retriever = load_models()

# ================================================================
# INTERFACE UTILISATEUR (UI)
# ================================================================
st.title("💬 RAG Chatbot")
st.markdown("*Ask anything - I'll answer based on the knowledge base*")

# --- Afficher l'historique des messages ---
# À chaque rechargement, on réaffiche tous les messages précédents
for message in st.session_state.messages:
    with st.chat_message(message["role"]):   # "user" ou "assistant"
        st.write(message["content"])

# --- Zone de saisie du chat ---
# st.chat_input() retourne le texte saisi quand l'utilisateur appuie sur Entrée
# L'opérateur := (walrus) assigne et teste en même temps
if user_input := st.chat_input("Type your question here..."):

    # Étape 1 : Ajouter la question de l'utilisateur à l'historique
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Étape 2 : Afficher la question dans l'interface
    with st.chat_message("user"):
        st.write(user_input)
    
    st.session_state.questions.append(user_input)
    

    # Retrieve knowledge and generate response
    
    # ============================================================
    # Étape 3 : RETRIEVAL - Chercher les documents pertinents
    # ============================================================
    # Le retriever cherche dans ChromaDB les 5 documents les plus similaires
    # à la question de l'utilisateur (basé sur la similarité des vecteurs)
    docs = retriever.invoke(user_input)

    knowledge_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', 'Unknown')
        page = doc.metadata.get('page', 'N/A')
        
        # Extraire juste le nom du fichier (sans le chemin complet)
        filename = source.split('\\')[-1] if '\\' in source else source.split('/')[-1]
        
        knowledge_parts.append(
            f"[Source {i}: {filename}, Page {page}]\n{doc.page_content}"
        )

    knowledge = "\n\n---\n\n".join(knowledge_parts)
    questions_knowledge="\n\n---\n\n".join(st.session_state.questions)
    response_knowledge="\n\n---\n\n".join(st.session_state.responces)
    
    rag_prompt = f"""
    Vous êtes un assistant qui répond aux questions en vous basant uniquement sur les connaissances qui vous sont fournies.
    Lors de vos réponses, vous n'utilisez pas vos connaissances internes,
    mais uniquement les informations de la section "Les connaissances".
    Vous ne mentionnez jamais à l'utilisateur que la réponse provient de ces connaissances fournies.
    ET tu peux utiliser l'lhistorique des questions et réponses précédentes pour rependre à la question actuelle si cette derniere en fait référence.

    La question : {user_input}

    Les connaissances : {knowledge}

    Historique des questions et réponses : {questions_knowledge} {response_knowledge}

    Indiquez toujours la source et le numéro de page lorsque vous fournissez une information issue des connaissances.
    """
    
    # Display assistant response with streaming
    # Debug: afficher l'historique des questions
    with st.expander("🔍 Debug - Historique des questions"):
        st.write(questions_knowledge)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()   # Zone vide qu'on met à jour au fur et à mesure
        response = ""

        # llm.stream() retourne la réponse morceau par morceau (chunk)
        for chunk in llm.stream(rag_prompt):
            response += chunk.content
            placeholder.write(response)

           # placeholder.write(" test "+knowledge)
    
    st.session_state.responces.append(response)


    # ============================================================
    # Étape 6 : DÉTECTION - Le chatbot a-t-il pu répondre ?
    # ============================================================
    # On vérifie si la réponse contient des mots-clés qui indiquent
    # que le chatbot n'a PAS trouvé de réponse dans les documents.
    # Exemple : "je ne sais pas", "ne contient pas d'information", etc.
    unanswered_keywords = [
        # Français
        "je ne sais pas", "je n'ai pas", "pas d'information",
        "ne contient pas", "ne précise pas", "ne précisent pas",
        "ne mentionne pas", "ne mentionnent pas",
        "pas trouvé", "aucune information", "je ne trouve pas",
        "ne contient aucune", "ne contiennent pas",
        "ne permet pas de répondre", "ne fournit pas",
        "ne fournissent pas", "pas mentionné",
        "désolé", "je ne peux pas", "impossible de répondre",
        "pas disponible", "pas dans les informations",
        "hors du contexte", "pas de réponse",
        # Anglais
        "i don't know", "no information", "i cannot", "i can't",
        "not found", "no relevant", "sorry",
        "does not contain", "do not contain",
        "not mentioned", "not available",
        "cannot answer", "unable to answer",
        "does not provide", "not in the provided",
    ]
    # Si UN SEUL mot-clé est trouvé dans la réponse → answered = False (sans réponse)
    # any() retourne True dès qu'un mot-clé est trouvé, not l'inverse
    answered = not any(kw in response.lower() for kw in unanswered_keywords)

    # ============================================================
    # Étape 7 : LOGGING - Enregistrer dans SQLite
    # ============================================================
    # On sauvegarde la question, la réponse, le statut (répondu ou non),
    # le nombre de documents trouvés, et l'ID de session
    # → Ces données seront affichées dans le dashboard admin
    log_question(
        question=user_input,           # La question posée
        response=response,             # La réponse générée
        answered=answered,             # True/False : le bot a-t-il répondu ?
        num_docs_found=len(docs),      # Nombre de documents trouvés dans ChromaDB
        session_id=st.session_state.session_id,  # ID unique de la session
    )

    # Étape 8 : Ajouter la réponse à l'historique pour l'affichage
    st.session_state.messages.append({"role": "assistant", "content": response})