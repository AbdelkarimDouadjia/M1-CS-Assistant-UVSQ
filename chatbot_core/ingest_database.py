import os
import shutil
import gc
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# ================================================================
# ingest_database.py - Ingestion des documents dans ChromaDB
# ================================================================
# Ce fichier est le "moteur" qui transforme des fichiers PDF/TXT
# en données vectorielles stockées dans ChromaDB.
#
# Processus complet :
#   1. Lire tous les fichiers PDF et TXT du dossier data/
#   2. Découper les textes en petits morceaux (chunks)
#   3. Convertir chaque chunk en vecteur numérique (embedding)
#   4. Stocker les vecteurs dans ChromaDB
#
# Ce fichier peut être :
#   - Exécuté directement : python ingest_database.py
#   - Importé depuis admin_dashboard.py pour le bouton "Mettre à jour"
# ================================================================

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, PyPDFDirectoryLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

DATA_PATH = str(PROJECT_ROOT / "data")
CHROMA_PATH = str(PROJECT_ROOT / "chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))


def load_documents():
    pdf_loader = PyPDFDirectoryLoader(DATA_PATH, recursive=True)
    pdf_documents = pdf_loader.load()
    txt_documents = DirectoryLoader(
        DATA_PATH,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        silent_errors=True,
        recursive=True,
    ).load()
    md_documents = DirectoryLoader(
        DATA_PATH,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        silent_errors=True,
        recursive=True,
    ).load()
    return (
        pdf_documents + txt_documents + md_documents,
        len(pdf_documents),
        len(txt_documents),
        len(md_documents),
    )


def extract_section(text: str) -> str:
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if 6 <= len(cleaned) <= 120:
            return cleaned
    return ""


def enrich_chunk(doc, chunk_id: str):
    source = doc.metadata.get("source", "")
    source_path = Path(source) if source else None
    source_name = source_path.name if source_path else "Unknown"
    page = doc.metadata.get("page")
    if isinstance(page, int):
        doc.metadata["page"] = page + 1
    if source_path and source_path.exists():
        doc.metadata["last_updated"] = datetime.fromtimestamp(
            source_path.stat().st_mtime
        ).isoformat(timespec="seconds")
    doc.metadata["source_name"] = source_name
    doc.metadata["title"] = source_path.stem if source_path else "Unknown"
    doc.metadata["section"] = doc.metadata.get("section") or extract_section(doc.page_content)
    doc.metadata["chunk_id"] = chunk_id


def build_chunks(raw_documents):
    text_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n# ",
            "\n## ",
            "\nArticle ",
            "\nARTICLE ",
            "\nTitre ",
            "\nTITRE ",
            "\n\n",
            "\n",
            ". ",
            " ",
        ],
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return text_splitter.split_documents(raw_documents)


def build_vector_store(embeddings_model=None, persist_directory: str | None = None):
    return get_vector_store(embeddings_model, persist_directory)


def get_embeddings_model():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vector_store(embeddings_model=None, persist_directory: str | None = None):
    if embeddings_model is None:
        embeddings_model = get_embeddings_model()
    return Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=persist_directory or CHROMA_PATH,
    )


def ingest_all_documents():
    raw_documents, pdf_count, txt_count, md_count = load_documents()
    if not raw_documents:
        raise RuntimeError(f"Aucun document trouve dans {DATA_PATH}.")

    chunks = build_chunks(raw_documents)
    embeddings_model = get_embeddings_model()
    chroma_path = Path(CHROMA_PATH)
    temp_chroma_path = PROJECT_ROOT / "chroma_db_tmp"
    backup_chroma_path = PROJECT_ROOT / "chroma_db_backup"
    shutil.rmtree(temp_chroma_path, ignore_errors=True)
    vector_store = build_vector_store(
        embeddings_model=embeddings_model,
        persist_directory=str(temp_chroma_path),
    )

    uuids = []
    for chunk in chunks:
        chunk_id = str(uuid4())
        enrich_chunk(chunk, chunk_id)
        uuids.append(chunk_id)

    vector_store.add_documents(documents=chunks, ids=uuids)
    del vector_store
    gc.collect()

    shutil.rmtree(backup_chroma_path, ignore_errors=True)
    if chroma_path.exists():
        shutil.move(str(chroma_path), str(backup_chroma_path))
    try:
        shutil.move(str(temp_chroma_path), str(chroma_path))
    except Exception:
        if backup_chroma_path.exists() and not chroma_path.exists():
            shutil.move(str(backup_chroma_path), str(chroma_path))
        raise
    shutil.rmtree(backup_chroma_path, ignore_errors=True)
    print(
        f"Documents charges : {len(raw_documents)} "
        f"(PDF/pages={pdf_count}, txt={txt_count}, md={md_count})"
    )
    print(f"Chunks indexes : {len(chunks)}")
    print(f"Embedding model : {EMBEDDING_MODEL}")
    print(f"Index reconstruit dans : {CHROMA_PATH}")
    return len(chunks)


def clear_and_reingest(reset_vector_store=False):
    if reset_vector_store:
        shutil.rmtree(CHROMA_PATH, ignore_errors=True)
        print(f"Index supprime dans : {CHROMA_PATH}")
        return 0
    return ingest_all_documents()


def main():
    ingest_all_documents()


if __name__ == "__main__":
    main()
