from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from uuid import uuid4

# import the .env file
from dotenv import load_dotenv
load_dotenv()

# configuration
DATA_PATH = r"data"
CHROMA_PATH = r"chroma_db"

# initiate the embeddings model
embeddings_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
# initiate the vector store
vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings_model,
    persist_directory=CHROMA_PATH,
)

# loading PDFc:\Users\idir\Downloads\Réunion_de_rentrée_—_M1_AMIS,_DataScale,_IRS_et_SeCReTS.pdf documents
pdf_loader = PyPDFDirectoryLoader(DATA_PATH)
pdf_documents = pdf_loader.load()

# loading plain text documents
txt_loader = DirectoryLoader(DATA_PATH, glob="**/*.txt", loader_cls=TextLoader)
txt_documents = txt_loader.load()

# combine both document types
raw_documents = pdf_documents + txt_documents

# splitting the document
text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\nArticle ",
        "\nARTICLE ",
        "\nTITRE ",
        "\nTitre ",
        "\n\n"
    ],
    chunk_size=3000,
    chunk_overlap=300,
)
# creating the chunks
chunks = text_splitter.split_documents(raw_documents)

# creating unique ID's
uuids = [str(uuid4()) for _ in range(len(chunks))]

# adding chunks to vector store
vector_store.add_documents(documents=chunks, ids=uuids)