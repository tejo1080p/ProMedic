import streamlit as st
from pathlib import Path

try:
    import chainlit as cl
except Exception:
    cl = None

from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from model_provider import chat, get_embeddings, stream_text

APP_NAME = "ProMedic+"
TAGLINE = "An AI-Powered Health Companion for Medication Adherence, Prescription Decoding"
PDF_DOC = Path("data/World-Health-Organization.pdf")
CHROMA_DIR = "./chroma_db"


def ensure_patient_context() -> None:
    if "patient_context" not in st.session_state:
        st.session_state["patient_context"] = {
            "ocr_text": "",
            "structured_data": "",
            "documents_loaded": False,
        }


def get_vector_store() -> Chroma | None:
    embedding = get_embeddings()

    if Path(CHROMA_DIR).exists():
        return Chroma(
            embedding_function=embedding,
            collection_name="simple-rag",
            persist_directory=CHROMA_DIR,
        )

    if not PDF_DOC.exists():
        return None

    loader = UnstructuredPDFLoader(file_path=str(PDF_DOC))
    docs = loader.load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300).split_documents(docs)
    return Chroma.from_documents(
        documents=chunks,
        embedding=embedding,
        collection_name="simple-rag",
        persist_directory=CHROMA_DIR,
    )


def build_prompt(question: str, context: str, ocr_text: str, structured_data: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are ProMedic+, an intelligent healthcare assistant.\n\n"
        "You must use ALL available information intelligently:\n"
        "1. Patient prescription data (highest priority)\n"
        "2. Retrieved document context\n"
        "3. General medical knowledge (only if needed)\n\n"
        "STRICT RULES:\n"
        "- If prescription data is available, prioritize it.\n"
        "- NEVER override patient data with unrelated context.\n"
        "- If context contradicts patient data, trust patient data.\n"
        "- Do NOT hallucinate diseases, medications, or conditions.\n"
        "- If unsure, say it clearly.\n\n"
        "RESPONSE STYLE:\n"
        "- Use natural paragraphs\n"
        "- Use bullet points only when useful\n"
        "- Do NOT be robotic\n"
        "- Adapt depth based on question complexity\n\n"
        "At the end, generate exactly 3 relevant follow-up questions."
    )

    user_prompt = (
        f"Patient OCR Text:\n{ocr_text or 'None'}\n\n"
        f"Structured Prescription Data:\n{structured_data or 'None'}\n\n"
        f"Retrieved Context:\n{context}\n\n"
        f"Question:\n{question}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def is_intent_general(query: str) -> bool:
    lowered = query.lower()
    keywords = ["medicine", "dosage", "what is", "uses"]
    return any(keyword in lowered for keyword in keywords)

def run_chat() -> None:
    ensure_patient_context()
    st.image("logo.jpg", width=170)
    st.title(f"{APP_NAME} Health Chat")
    st.caption(TAGLINE)

    if "promedic_chat_history" not in st.session_state:
        st.session_state["promedic_chat_history"] = []

    for item in st.session_state["promedic_chat_history"]:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    query = st.chat_input("Ask your health question in English")
    if not query:
        return

    st.session_state["promedic_chat_history"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Generating response..."):
            vector_store = get_vector_store()
            if vector_store is None:
                response_text = (
                    "Knowledge base is unavailable (missing PDF or index). "
                    "Please make sure data/World-Health-Organization.pdf exists and try again."
                )
            else:
                patient_context = st.session_state.get("patient_context", {})
                ocr_text = patient_context.get("ocr_text", "")
                structured_data = patient_context.get("structured_data", "")

                docs = vector_store.similarity_search(query, k=4)
                filtered_docs = [
                    doc
                    for doc in docs
                    if len(doc.page_content) > 80
                ]
                context = "\n\n".join(doc.page_content for doc in filtered_docs)
                if not context.strip():
                    context = "No strong external context available."
                messages = build_prompt(query, context, ocr_text, structured_data)
                answer = chat(messages, stream=True)
                complete_answer = "".join(stream_text(answer))

                sources = []
                for doc in filtered_docs:
                    src = doc.metadata.get("source", "unknown")
                    if src not in sources:
                        sources.append(src)

                source_text = "\n".join(f"- {src}" for src in sources) if sources else "- None"
                response_text = f"{complete_answer}\n\nSources:\n{source_text}"

        st.markdown(response_text)

    st.session_state["promedic_chat_history"].append({"role": "assistant", "content": response_text})


if cl is not None:
    @cl.on_chat_start
    async def on_chat_start():
        cl.user_session.set("chat_history", [])
        cl.user_session.set("vector_store", get_vector_store())
        await cl.Message(content=f"Welcome to {APP_NAME}. {TAGLINE} Ask your question in English only.").send()

    @cl.on_message
    async def generate_response(query: cl.Message):
        vector_store = cl.user_session.get("vector_store")
        if vector_store is None:
            await cl.Message(
                content=(
                    "Knowledge base is unavailable (missing PDF or index). "
                    "Please make sure data/World-Health-Organization.pdf exists and try again."
                )
            ).send()
            return

        docs = vector_store.similarity_search(query.content, k=4)
        filtered_docs = [
            doc
            for doc in docs
            if len(doc.page_content) > 80
        ]
        context = "\n\n".join(doc.page_content for doc in filtered_docs)
        if not context.strip():
            context = "No strong external context available."
        messages = build_prompt(query.content, context, "", "")

        answer = chat(messages, stream=True)
        complete_answer = "".join(stream_text(answer))

        sources = []
        for doc in filtered_docs:
            src = doc.metadata.get("source", "unknown")
            if src not in sources:
                sources.append(src)

        source_text = "\n".join(f"- {src}" for src in sources) if sources else "- None"
        response = cl.Message(content=f"{complete_answer}\n\nSources:\n{source_text}")
        await response.send()
