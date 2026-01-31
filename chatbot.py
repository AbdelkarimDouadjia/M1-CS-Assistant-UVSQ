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

# Initialize models
@st.cache_resource
def load_models():
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    llm = ChatGoogleGenerativeAI(temperature=0.5, model='gemini-2.5-flash')
    vector_store = Chroma(
        collection_name="example_collection",
        embedding_function=embeddings_model,
        persist_directory=CHROMA_PATH,
    )
    retriever = vector_store.as_retriever(search_kwargs={'k': 5})
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
    
    # Retrieve knowledge and generate response
    docs = retriever.invoke(user_input)
    knowledge = "\n\n".join([doc.page_content for doc in docs])
    
    rag_prompt = f"""
    You are an assistant which answers questions based on knowledge which is provided to you.
    While answering, you don't use your internal knowledge, 
    but solely the information in the "The knowledge" section.
    You don't mention anything to the user about the provided knowledge.

    The question: {user_input}

    The knowledge: {knowledge}
    """
    
    # Display assistant response with streaming
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = ""
        
        for chunk in llm.stream(rag_prompt):
            response += chunk.content
            placeholder.write(response)
    
    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": response})