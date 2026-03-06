from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from dotenv import load_dotenv

load_dotenv()


class SmartChunkingConfig:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.llm = ChatGoogleGenerativeAI(model=model_name)
        self.separators_hint = '["\\n\\n", "\\n", ". ", "? ", "! ", "; ", ": ", ", ", " ", ""]'

    def generate(self, path: str) -> str:


        if(path.endswith(".pdf")):
            loader = PyMuPDFLoader(path)
        elif path.endswith(".txt") or path.endswith(".md"):
            loader = TextLoader(path)
        else: 
            raise ValueError("Unsupported file type. Only PDF, TXT, and MD are supported.")
        


        # Charger le document
        document = loader.load()
        document_content = "\n".join([doc.page_content for doc in document])

        # Créer le prompt
        prompt = (
            f"Voici le contenu d'un document. Analyse le texte et extrait tous les titres "
            f"de sections et sous-sections présents dans le document. "
            f"Génère un fichier YAML de configuration pour RecursiveCharacterTextSplitter de langchain "
            f"avec les règles suivantes :\n"
            f"- Détermine chunk_size et chunk_overlap adaptés à la densité et au style du document\n"
            f"- separators: liste ordonnée du plus spécifique au plus général, "
            f"en commençant par les titres les plus larges (ex: chapitres, titres), "
            f"puis les sous-titres, puis les séparateurs classiques : {self.separators_hint}\n"
            f"- Evite de séparer des éléments qui forment une unité logique\n"
            f"- Objectif : que chaque chunk soit autonome et suffisamment riche en contexte pour un système RAG.\n"
            f"- Si tu utilises des regex dans les séparateurs, convertis TOUS les séparateurs "
            f"en regex et ajoute is_separator_regex: true.\n"
            f"Donne UNIQUEMENT le contenu YAML brut, sans balises markdown, sans explication:\n{document_content}"
        )

        # Appeler le LLM
        response = self.llm.invoke(prompt)
        yaml_content = response.content

        # Nettoyer les balises markdown si présentes
        if yaml_content.strip().startswith("```"):
            lines = yaml_content.strip().split("\n")
            yaml_content = "\n".join(lines[1:-1])

        # Sauvegarder
        yaml_path=""

        if path.endswith(".pdf"):
            yaml_path =path.replace(".pdf", "_chunking_config.yaml")
        elif path.endswith(".txt"):
            yaml_path =path.replace(".txt", "_chunking_config.yaml")
        elif path.endswith(".md"):
            yaml_path =path.replace(".md", "_chunking_config.yaml")

            
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        print(f"✅ Config sauvegardée : {yaml_path}")
        return yaml_content


