import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, PyPDFDirectoryLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

DATA_PATH = r"data"
CHROMA_PATH = r"chroma_db"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))


def load_documents():
    pdf_documents = PyPDFDirectoryLoader(DATA_PATH).load()
    txt_documents = DirectoryLoader(
        DATA_PATH,
        glob="**/*.txt",
        loader_cls=TextLoader,
        silent_errors=True,
    ).load()
    return pdf_documents + txt_documents, len(pdf_documents), len(txt_documents)


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


def build_vector_store():
    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )


def main():
    raw_documents, pdf_count, txt_count = load_documents()
    if not raw_documents:
        raise RuntimeError(f"Aucun document trouve dans {DATA_PATH}.")

    chunks = build_chunks(raw_documents)
    shutil.rmtree(CHROMA_PATH, ignore_errors=True)
    vector_store = build_vector_store()

    uuids = []
    for chunk in chunks:
        chunk_id = str(uuid4())
        enrich_chunk(chunk, chunk_id)
        uuids.append(chunk_id)

    vector_store.add_documents(documents=chunks, ids=uuids)
    print(f"Documents charges : {len(raw_documents)} (PDF/pages={pdf_count}, txt={txt_count})")
    print(f"Chunks indexes : {len(chunks)}")
    print(f"Embedding model : {EMBEDDING_MODEL}")
    print(f"Index reconstruit dans : {CHROMA_PATH}")


if __name__ == "__main__":
    main()
