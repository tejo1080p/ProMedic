from pathlib import Path
import uuid

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from model_provider import get_chat_model, get_embeddings

APP_NAME = "ProMedic+"
TAGLINE = "An AI-Powered Health Companion for Medication Adherence, Prescription Decoding, and Nutritional Guidance"
PDF_DOC = Path("data/World-Health-Organization.pdf")
DOCS_DIR = Path("data") / "documents"
CHROMA_DIR = "./chroma_db"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_patient_context() -> None:
    if "patient_context" not in st.session_state:
        st.session_state["patient_context"] = {
            "ocr_text": "",
            "structured_data": "",
            "documents_loaded": False,
        }


def load_documents() -> list:
    documents = []
    if PDF_DOC.exists():
        documents.extend(UnstructuredPDFLoader(file_path=str(PDF_DOC)).load())

    for path in DOCS_DIR.rglob("*"):
        if path.suffix.lower() == ".pdf":
            documents.extend(UnstructuredPDFLoader(file_path=str(path)).load())
        elif path.suffix.lower() in {".txt", ".md"}:
            documents.extend(TextLoader(str(path), encoding="utf-8").load())

    return documents


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300)
    return splitter.split_documents(documents)


@st.cache_resource
def load_vector_db():
    embedding = get_embeddings()
    if Path(CHROMA_DIR).exists():
        return Chroma(
            embedding_function=embedding,
            collection_name="simple-rag",
            persist_directory=CHROMA_DIR,
        )

    data = load_documents()
    if not data:
        return None

    chunks = split_documents(data)
    return Chroma.from_documents(
        documents=chunks,
        embedding=embedding,
        collection_name="simple-rag",
        persist_directory=CHROMA_DIR,
    )


def create_retriever(vector_db, llm):
    query_prompt = ChatPromptTemplate.from_template(
        """Generate five English search queries for the user question to improve retrieval.
Original question: {question}"""
    )
    return MultiQueryRetriever.from_llm(vector_db.as_retriever(), llm, prompt=query_prompt)


def create_chain(retriever, llm):
    system_prompt = (
        "You are ProMedic+, a healthcare assistant.\n\n"
        "Provide clear, natural, and clinically sensible answers.\n\n"
        "Adapt your response style dynamically:\n"
        "- Use paragraphs for explanations\n"
        "- Use bullet points only when they improve clarity (lists, symptoms, steps)\n\n"
        "Do NOT be mechanical or overly templated.\n\n"
        "Adapt depth based on the question:\n"
        "- Simple question -> short answer\n"
        "- Complex clinical question -> deeper explanation\n\n"
        "Use retrieved context as the primary source, but you may use general medical knowledge when needed.\n\n"
        "Avoid contradictions.\n"
        "Do not fabricate missing facts - if something is unclear, say it briefly.\n\n"
        "Maintain a professional but human-like tone.\n\n"
        "Reasoning improvements:\n"
        "- Infer medical meaning when safe (e.g., diabetes -> glucose control, lifestyle -> diet/exercise)\n"
        "- Do not say 'no treatment plan' if one is implied\n"
        "- Combine context + general knowledge intelligently\n\n"
        "Disclaimer behavior:\n"
        "- Do NOT include a disclaimer in every answer\n"
        "- Only add when advice is sensitive\n"
        "- Keep it short: 'This is general information; consult a healthcare professional for personalized advice.'\n\n"
        "Follow-up questions (always include exactly 3):\n"
        "- Specific to the current context or document\n"
        "- Practical and natural, not generic\n"
        "- Use emojis if helpful\n\n"
        "Format:\n"
        "Follow-up questions:\n"
        "1. ...\n"
        "2. ...\n"
        "3. ..."
    )
    user_prompt = (
        "Patient profile:\n{patient_profile}\n\n"
        "Context:\n{context}\n\n"
        "Question:\n{question}"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("user", user_prompt),
        ]
    )
    return prompt | llm


def is_intent_general(query: str) -> bool:
    lowered = query.lower()
    keywords = ["medicine", "dosage", "what is", "uses"]
    return any(keyword in lowered for keyword in keywords)


def run_documents():
    ensure_patient_context()
    st.image("logo.jpg", width=170)
    st.title(APP_NAME)
    st.caption(TAGLINE)

    uploaded_docs = st.file_uploader(
        "Upload additional documents (.pdf, .txt, .md)",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )

    if uploaded_docs and st.button("Save uploaded documents and refresh index"):
        for doc in uploaded_docs:
            target = DOCS_DIR / f"{uuid.uuid4().hex}_{doc.name}"
            target.write_bytes(doc.getvalue())
        load_vector_db.clear()
        st.session_state["patient_context"]["documents_loaded"] = True
        st.success("Documents saved. Vector index will be rebuilt on next question.")

    patient_profile = st.text_area(
        "Optional patient profile",
        placeholder="Example: 65 years old, type 2 diabetes, hypertension, on metformin.",
    )

    user_input = st.text_input("Enter your question in English", "")

    if user_input:
        with st.spinner("Generating response..."):
            try:
                llm = get_chat_model()
                vector_db = load_vector_db()
                if vector_db is None:
                    st.error("Unable to load the document knowledge base.")
                    return

                retriever = create_retriever(vector_db, llm)
                chain = create_chain(retriever, llm)
                retrieved_docs = retriever.invoke(user_input)
                filtered_docs = [
                    doc
                    for doc in retrieved_docs
                    if len(doc.page_content.strip()) >= 80
                ]
                context = "\n\n".join(doc.page_content for doc in filtered_docs)
                use_context = bool(filtered_docs)
                if not use_context and is_intent_general(user_input):
                    use_context = False
                response = chain.invoke(
                    {
                        "question": user_input,
                        "patient_profile": patient_profile or "No profile provided.",
                        "context": context if use_context else "",
                    }
                ).content

                supporting_docs = vector_db.similarity_search(user_input, k=4)
                sources = []
                for doc in supporting_docs:
                    src = doc.metadata.get("source", "unknown")
                    if src not in sources:
                        sources.append(src)

                st.markdown("**Assistant:**")
                st.write(response)

                st.markdown("**Sources:**")
                if sources:
                    for src in sources:
                        st.write(f"- {src}")
                else:
                    st.write("- No sources found")
            except Exception as exc:
                st.error(f"An error occurred: {exc}")
    else:
        st.info("Type a question to begin.")


if __name__ == "__main__":
    run_documents()