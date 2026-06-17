import os
import shutil
import gc
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from collections import defaultdict

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
import yaml

from chatbot_core.smart_parcing import SmartChunkingConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

DATA_PATH = str(PROJECT_ROOT / "data")
CHROMA_PATH = str(PROJECT_ROOT / "chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
SMART_CHUNKING_ENABLED = os.getenv("SMART_CHUNKING_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
SMART_CHUNKING_MODEL = os.getenv("SMART_CHUNKING_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))


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


def _default_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
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


def _load_smart_splitter(source: str, smart: SmartChunkingConfig) -> RecursiveCharacterTextSplitter | None:
    source_path = Path(source)
    if source_path.suffix.lower() not in {".pdf", ".txt", ".md"}:
        return None
    yaml_path = source_path.with_name(f"{source_path.stem}_chunking_config.yaml")
    try:
        if not yaml_path.exists():
            smart.generate(str(source_path))
        config = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        separators = config.get("separators")
        chunk_size = int(config.get("chunk_size", CHUNK_SIZE))
        chunk_overlap = int(config.get("chunk_overlap", CHUNK_OVERLAP))
        if not isinstance(separators, list) or not separators:
            return None
        return RecursiveCharacterTextSplitter(
            separators=[str(item) for item in separators],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            is_separator_regex=bool(config.get("is_separator_regex", False)),
        )
    except Exception as exc:
        print(f"Smart chunking indisponible pour {source_path.name}: {exc}")
        return None


def build_chunks(raw_documents):
    if not SMART_CHUNKING_ENABLED:
        return _default_text_splitter().split_documents(raw_documents)

    smart = SmartChunkingConfig(model_name=SMART_CHUNKING_MODEL)
    fallback_splitter = _default_text_splitter()
    docs_by_source: dict[str, list] = defaultdict(list)
    for doc in raw_documents:
        docs_by_source[str(doc.metadata.get("source") or "")].append(doc)

    chunks = []
    for source, docs_for_source in docs_by_source.items():
        splitter = _load_smart_splitter(source, smart) if source else None
        chunks.extend((splitter or fallback_splitter).split_documents(docs_for_source))
    return chunks
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
