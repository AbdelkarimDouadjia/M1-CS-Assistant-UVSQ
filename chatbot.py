import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="RAG Chatbot",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main { padding-top: 0; }
    .stChatMessage { background-color: #f0f2f6; border-radius: 10px; padding: 15px; }
    </style>
    """, unsafe_allow_html=True)


# configuration
CHROMA_PATH = r"chroma_db"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "questions" not in st.session_state:
    st.session_state.questions = []
if "responces" not in st.session_state:
    st.session_state.responces = []

# Initialize models
@st.cache_resource
def load_models():
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    llm = ChatGoogleGenerativeAI(temperature=0.5, model='gemini-2.5-flash')
    vector_store = Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    retriever = vector_store.as_retriever(search_kwargs={'k': 8}, score_threshold=0.6)
    return llm, retriever

llm, retriever = load_models()

# UI
st.title("💬 RAG Chatbot")
st.markdown("*Ask anything - I'll answer based on the knowledge base*")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
if user_input := st.chat_input("Type your question here..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.write(user_input)
    
    st.session_state.questions.append(user_input)
    

    # Retrieve knowledge and generate response
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
        placeholder = st.empty()
        response = ""
        
        for chunk in llm.stream(rag_prompt):
            response += chunk.content
            placeholder.write(response)

           # placeholder.write(" test "+knowledge)
    
    st.session_state.responces.append(response)

    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": response})