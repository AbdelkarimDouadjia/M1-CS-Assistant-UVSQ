from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from uuid import uuid4
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

from smart_parcing import SmartChunkingConfig
load_dotenv()

# configuration
DATA_PATH = r"data"
CHROMA_PATH = r"chroma_db"




# # initiate the embeddings model (local)
# embeddings_model = HuggingFaceEmbeddings(
#     model_name="./models/bge-base-en-v1.5",  # chemin local
#     model_kwargs={"device": "cpu"}
# )
# # initiate the vector store
# vector_store = Chroma(
#     collection_name="example_collection",
#     embedding_function=embeddings_model,
#     persist_directory=CHROMA_PATH,
# )

# existing = vector_store.get(include=["metadatas"])

# already_indexed = set()

# for m in existing["metadatas"]:
#     if "source" in m:
#         already_indexed.add(m["source"])

# print(f"📚 Documents déjà indexés : {len(already_indexed)}")



# # loading PDFc:\Users\idir\Downloads\Réunion_de_rentrée_—_M1_AMIS,_DataScale,_IRS_et_SeCReTS.pdf documents
# pdf_loader = PyPDFDirectoryLoader(DATA_PATH)
# pdf_documents = pdf_loader.load()


# # loading plain text documents
# txt_loader = DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader)
# txt_documents = txt_loader.load()


# markdoun_loader = DirectoryLoader(DATA_PATH, glob="**/*.md", loader_cls=TextLoader)
# markdown_documents = markdoun_loader.load()
# # combine both document types
# raw_documents = pdf_documents + txt_documents + markdown_documents



# new_documents = [
#     doc for doc in raw_documents
#     if doc.metadata.get("source") not in already_indexed
# ]

# new_sources = set(doc.metadata.get("source") for doc in new_documents)


# smart = SmartChunkingConfig()

# for source in new_sources:
#     print(f"📄 Génération config pour : {source}")
#     smart.generate(source)  # appelé une seule fois par fichier



# import yaml
# import os

# all_chunks = []

# for source in new_sources:
#     print(f"📄 Processing: {source}")

#     yaml_path = os.path.splitext(source)[0] + "_chunking_config.yaml"

#     # Générer la config si elle n'existe pas encore
#     if not os.path.exists(yaml_path):
#         smart.generate(source)

#     # Charger la config
#     with open(yaml_path, "r", encoding="utf-8") as f:
#         config = yaml.safe_load(f)

#     # Splitter les docs de cette source
#     text_splitter = RecursiveCharacterTextSplitter(
#         separators=config["separators"],
#         chunk_size=config["chunk_size"],
#         chunk_overlap=config["chunk_overlap"],
#         is_separator_regex=config.get("is_separator_regex", False)
#     )

#     docs_for_source = [d for d in new_documents if d.metadata.get("source") == source]
#     chunks = text_splitter.split_documents(docs_for_source)
#     all_chunks.extend(chunks)
#     print(f"   → {len(chunks)} chunks créés")

# # Ajouter à ChromaDB
# uuids = [str(uuid4()) for _ in range(len(all_chunks))]
# vector_store.add_documents(documents=all_chunks, ids=uuids)
# print(f"✅ {len(all_chunks)} chunks ajoutés.")





# # # splitting the document
# # text_splitter = RecursiveCharacterTextSplitter(
# #     separators=[
# #         r"\n\n(?=TITRE \d+ – [^\n]+)",
# #         r"\n\n(?=Article \d+\.(?!\d|[a-z])\s|PREAMBULE\n)",
# #         r"\n\n(?=Article \d+\.[a-zA-Z0-9]+\.?\s)",
# #         r"\n\n",
# #         r"\n",
# #         r"\. ",
# #         r"\? ",
# #         r"! ",
# #         r"; ",
# #         r": ",
# #         r", ",
# #         r" ",
# #         r""
# #     ],
# #     chunk_size=3000,
# #     chunk_overlap=300,
# #     is_separator_regex=True
# # )
# # # creating the chunks
# # chunks = text_splitter.split_documents(raw_documents)

# # # creating unique ID's
# # uuids = [str(uuid4()) for _ in range(len(chunks))]

# # # adding chunks to vector store
# # vector_store.add_documents(documents=chunks, ids=uuids)




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

    #change here



    
    existing = vector_store.get(include=["metadatas"])

    already_indexed = set()

    
    
    for m in existing["metadatas"]:
        if "source" in m:
            already_indexed.add(m["source"])

    print(f"📚 Documents déjà indexés : {len(already_indexed)}")


    new_documents = [
        doc for doc in raw_documents
        if doc.metadata.get("source") not in already_indexed
    ]

    new_sources = set(doc.metadata.get("source") for doc in new_documents)


    smart = SmartChunkingConfig()

    for source in new_sources:
        print(f"📄 Génération config pour : {source}")
        smart.generate(source)  # appelé une seule fois par fichier



    import yaml
    import os

    all_chunks = []

    for source in new_sources:
        print(f"📄 Processing: {source}")

        yaml_path = os.path.splitext(source)[0] + "_chunking_config.yaml"

        # Générer la config si elle n'existe pas encore
        if not os.path.exists(yaml_path):
            smart.generate(source)

        # Charger la config
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Splitter les docs de cette source
        text_splitter = RecursiveCharacterTextSplitter(
            separators=config["separators"],
            chunk_size=config["chunk_size"],
            chunk_overlap=config["chunk_overlap"],
            is_separator_regex=config.get("is_separator_regex", False)
        )

        docs_for_source = [d for d in new_documents if d.metadata.get("source") == source]
        chunks = text_splitter.split_documents(docs_for_source)
        all_chunks.extend(chunks)
        print(f"   → {len(chunks)} chunks créés")

    # Ajouter à ChromaDB
    uuids = [str(uuid4()) for _ in range(len(all_chunks))]
    vector_store.add_documents(documents=all_chunks, ids=uuids)
    print(f"✅ {len(all_chunks)} chunks ajoutés.")





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
