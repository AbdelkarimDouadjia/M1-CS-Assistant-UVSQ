from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from uuid import uuid4

# import the .env file
from dotenv import load_dotenv

from smart_parcing import SmartChunkingConfig
load_dotenv()

# configuration
DATA_PATH = r"data"
CHROMA_PATH = r"chroma_db"



# initiate the embeddings model (local)
embeddings_model = HuggingFaceEmbeddings(
    model_name="./models/bge-base-en-v1.5",  # chemin local
    model_kwargs={"device": "cpu"}
)
# initiate the vector store
vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings_model,
    persist_directory=CHROMA_PATH,
)

existing = vector_store.get(include=["metadatas"])

already_indexed = set()

for m in existing["metadatas"]:
    if "source" in m:
        already_indexed.add(m["source"])

print(f"📚 Documents déjà indexés : {len(already_indexed)}")



# loading PDFc:\Users\idir\Downloads\Réunion_de_rentrée_—_M1_AMIS,_DataScale,_IRS_et_SeCReTS.pdf documents
pdf_loader = PyPDFDirectoryLoader(DATA_PATH)
pdf_documents = pdf_loader.load()


# loading plain text documents
txt_loader = DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader)
txt_documents = txt_loader.load()


markdoun_loader = DirectoryLoader(DATA_PATH, glob="**/*.md", loader_cls=TextLoader)
markdown_documents = markdoun_loader.load()
# combine both document types
raw_documents = pdf_documents + txt_documents + markdown_documents



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





# # splitting the document
# text_splitter = RecursiveCharacterTextSplitter(
#     separators=[
#         r"\n\n(?=TITRE \d+ – [^\n]+)",
#         r"\n\n(?=Article \d+\.(?!\d|[a-z])\s|PREAMBULE\n)",
#         r"\n\n(?=Article \d+\.[a-zA-Z0-9]+\.?\s)",
#         r"\n\n",
#         r"\n",
#         r"\. ",
#         r"\? ",
#         r"! ",
#         r"; ",
#         r": ",
#         r", ",
#         r" ",
#         r""
#     ],
#     chunk_size=3000,
#     chunk_overlap=300,
#     is_separator_regex=True
# )
# # creating the chunks
# chunks = text_splitter.split_documents(raw_documents)

# # creating unique ID's
# uuids = [str(uuid4()) for _ in range(len(chunks))]

# # adding chunks to vector store
# vector_store.add_documents(documents=chunks, ids=uuids)