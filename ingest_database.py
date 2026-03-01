# ================================================================
# ingest_database.py - Ingestion des documents dans ChromaDB
# ================================================================
# Ce fichier est le "moteur" qui transforme des fichiers PDF/TXT
# en données vectorielles stockées dans ChromaDB.
#
# Processus complet :
#   1. Lire tous les fichiers PDF et TXT du dossier data/
#   2. Découper les textes en petits morceaux (chunks) de 3000 caractères
#   3. Convertir chaque chunk en vecteur numérique (embedding)
#   4. Stocker les vecteurs dans ChromaDB
#
# Ce fichier peut être :
#   - Exécuté directement : python ingest_database.py
#   - Importé depuis admin_dashboard.py pour le bouton "Mettre à jour"
# ================================================================

# --- Imports ---
from langchain_community.document_loaders import (
    PyPDFDirectoryLoader,    # Charge tous les PDF d'un dossier
    DirectoryLoader,         # Charge des fichiers d'un dossier selon un pattern
    TextLoader,              # Charge des fichiers texte (.txt)
)
from langchain_text_splitters import RecursiveCharacterTextSplitter  # Découpe les textes en chunks
from langchain_google_genai import GoogleGenerativeAIEmbeddings      # Modèle d'embeddings Google
from langchain_chroma import Chroma    # Base de données vectorielle
from uuid import uuid4                 # Génère des identifiants uniques
import os

# Charger la clé API Google depuis le fichier .env
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
DATA_PATH = r"data"          # Dossier contenant les fichiers PDF/TXT à ingérer
CHROMA_PATH = r"chroma_db"   # Dossier où ChromaDB stocke sa base de données


def get_embeddings_model():
    """
    Crée et retourne le modèle d'embeddings Google.
    
    Un embedding = transformer du texte en une liste de nombres (vecteur).
    Exemple : "Bonjour" → [0.12, -0.45, 0.78, ...] (768 nombres)
    
    Deux textes similaires auront des vecteurs proches.
    C'est comme ça que le chatbot trouve les documents pertinents.
    """
    return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")


def get_vector_store(embeddings_model=None):
    """
    Crée et retourne la connexion à la base ChromaDB.
    
    ChromaDB est une base de données spécialisée pour stocker des vecteurs.
    Elle permet de chercher les vecteurs les plus similaires à une requête.
    
    Args:
        embeddings_model: Le modèle d'embeddings à utiliser.
                         Si None, on en crée un nouveau.
    
    Returns:
        Un objet Chroma connecté à la base de données.
    """
    if embeddings_model is None:
        embeddings_model = get_embeddings_model()
    return Chroma(
        collection_name="example_collection",   # Nom de la collection dans ChromaDB
        embedding_function=embeddings_model,    # Le modèle pour convertir texte → vecteur
        persist_directory=CHROMA_PATH,          # Dossier de stockage sur disque
    )


def ingest_all_documents():
    """
    Fonction principale : charge TOUS les documents du dossier data/
    et les ajoute dans la base vectorielle ChromaDB.
    
    Étapes :
        1. Charger les PDF → liste de documents
        2. Charger les TXT → liste de documents
        3. Combiner les deux listes
        4. Découper en chunks de 3000 caractères
        5. Générer un ID unique pour chaque chunk
        6. Ajouter les chunks dans ChromaDB
    
    Returns:
        int : Le nombre de chunks créés et ajoutés.
    """
    embeddings_model = get_embeddings_model()
    vector_store = get_vector_store(embeddings_model)

    # --- Étape 1 : Charger tous les fichiers PDF du dossier data/ ---
    pdf_loader = PyPDFDirectoryLoader(DATA_PATH)
    pdf_documents = pdf_loader.load()  # Retourne une liste de Document(page_content, metadata)

    # --- Étape 2 : Charger tous les fichiers TXT du dossier data/ ---
    # glob="**/*.txt" = chercher récursivement tous les fichiers .txt
    txt_loader = DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader)
    txt_documents = txt_loader.load()

    # --- Étape 3 : Combiner PDF + TXT ---
    raw_documents = pdf_documents + txt_documents

    # --- Étape 4 : Découper les documents en chunks ---
    # Pourquoi découper ? Un PDF de 50 pages est trop gros pour l'IA.
    # On le découpe en morceaux de 3000 caractères pour que l'IA
    # puisse traiter chaque morceau individuellement.
    text_splitter = RecursiveCharacterTextSplitter(
        # Séparateurs prioritaires : on coupe d'abord aux "Article", "TITRE", etc.
        # Si le chunk est encore trop gros, on coupe aux paragraphes (\n\n)
        separators=[
            "\nArticle ",    # Coupe aux articles (documents juridiques)
            "\nARTICLE ",
            "\nTITRE ",     # Coupe aux titres
            "\nTitre ",
            "\n\n"          # Sinon coupe aux paragraphes
        ],
        chunk_size=3000,     # Taille max d'un chunk : 3000 caractères
        chunk_overlap=300,   # Chevauchement de 300 caractères entre chunks
                             # (pour ne pas perdre le contexte aux bordures)
    )

    # Découper tous les documents en chunks
    chunks = text_splitter.split_documents(raw_documents)

    # --- Étape 5 : Créer un identifiant unique pour chaque chunk ---
    # Chaque chunk a besoin d'un ID unique dans ChromaDB
    uuids = [str(uuid4()) for _ in range(len(chunks))]

    # --- Étape 6 : Ajouter les chunks dans ChromaDB ---
    # ChromaDB va automatiquement :
    #   1. Convertir chaque chunk en vecteur (via embeddings_model)
    #   2. Stocker le vecteur + le texte original
    vector_store.add_documents(documents=chunks, ids=uuids)

    return len(chunks)


def clear_and_reingest():
    """
    Vide complètement la base ChromaDB puis réingère tous les documents.
    
    Pourquoi vider d'abord ?
    Si on ajoute simplement les nouveaux documents, les anciens restent.
    → Risque de doublons et de données obsolètes.
    En vidant puis en réingérant, on est sûr d'avoir une base propre.
    
    Appelée depuis admin_dashboard.py quand l'admin clique sur
    "Mettre à jour la base de données".
    
    Returns:
        int : Le nombre de chunks créés après réingestion.
    """
    embeddings_model = get_embeddings_model()

    # Étape 1 : Supprimer tous les documents de la collection
    vector_store = get_vector_store(embeddings_model)
    vector_store.reset_collection()  # Vide la collection ChromaDB

    # Étape 2 : Recharger tous les documents du dossier data/
    return ingest_all_documents()


# ================================================================
# EXÉCUTION DIRECTE
# ================================================================
# Ce bloc s'exécute UNIQUEMENT si on lance : python ingest_database.py
# Il ne s'exécute PAS quand on importe le fichier (from ingest_database import ...)
if __name__ == "__main__":
    nb_chunks = ingest_all_documents()
    print(f"{nb_chunks} chunks ajoutés à la base de données.")