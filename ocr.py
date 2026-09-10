import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytesseract
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from model_provider import chat, stream_text

try:
    from azure.storage.blob import BlobServiceClient
except Exception:
    BlobServiceClient = None

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

APP_NAME = "ProMedic+"
TAGLINE = "An AI-Powered Health Companion for Medication Adherence, Prescription Decoding, and Nutritional Guidance"
load_dotenv()
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER", "promedic-records")

DATA_DIR = Path("data")
OCR_RECORDS_DIR = DATA_DIR / "ocr_records"
OCR_RECORDS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_patient_context() -> None:
    if "patient_context" not in st.session_state:
        st.session_state["patient_context"] = {
            "ocr_text": "",
            "structured_data": "",
            "documents_loaded": False,
        }


class ImageProcessor:
    @staticmethod
    def preprocess_image_array(image_array: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
        denoised = cv2.medianBlur(gray, 3)
        return cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

    @staticmethod
    def extract_text_from_array(image_array: np.ndarray) -> str:
        processed = ImageProcessor.preprocess_image_array(image_array)
        return pytesseract.image_to_string(processed, lang="eng").strip()

    @staticmethod
    def extract_images_from_pdf(pdf_path: str) -> list[np.ndarray]:
        doc = fitz.open(pdf_path)
        images: list[np.ndarray] = []
        for page_number in range(len(doc)):
            pix = doc[page_number].get_pixmap(dpi=300)
            image_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if image_array.shape[2] == 4:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2RGB)
            images.append(cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR))
        return images


class OptionalAzureStorage:
    def __init__(self, connection_string: str, container_name: str):
        self.enabled = bool(connection_string and BlobServiceClient)
        self.container_client = None
        if self.enabled:
            client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = client.get_container_client(container_name)
            try:
                self.container_client.create_container()
            except Exception:
                pass

    def upload_file(self, file_path: Path) -> tuple[bool, str]:
        if not self.enabled or self.container_client is None:
            return False, "Azure upload not configured."
        try:
            blob_client = self.container_client.get_blob_client(file_path.name)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            return True, f"Uploaded to Azure blob: {file_path.name}"
        except Exception as exc:
            return False, f"Azure upload failed: {exc}"


def extract_medication_lines(ocr_text: str) -> list[str]:
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    medication_like = []
    for line in lines:
        if re.search(r"\b\d+\s?(mg|ml|mcg|g|tablet|tab|capsule|cap)\b", line, re.I):
            medication_like.append(line)
        elif re.search(r"\b(take|once|twice|daily|after|before|night|morning)\b", line, re.I):
            medication_like.append(line)
    return medication_like[:20]


def structure_prescription_with_llm(ocr_text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a medical documentation assistant. "
                "Respond in English only. Return clean markdown with these sections: "
                "Doctor, Patient, Date, Medications (name/dosage/instructions), Warnings, Follow-up."
            ),
        },
        {
            "role": "user",
            "content": (
                "Extract structured prescription details from this OCR text. "
                "If a field is missing, write Unknown.\n\n"
                f"OCR TEXT:\n{ocr_text}"
            ),
        },
    ]
    return "".join(stream_text(chat(messages, stream=True))).strip()


def generate_nutrition_guidance(structured_text: str, meds: list[str]) -> str:
    meds_text = "\n".join(f"- {item}" for item in meds) if meds else "- Unknown medications"
    messages = [
        {
            "role": "system",
            "content": (
                "You are a healthcare nutrition assistant. "
                "Provide safe, general nutritional guidance only in English. "
                "Do not provide diagnosis."
            ),
        },
        {
            "role": "user",
            "content": (
                "Based on this prescription summary and medication list, provide:\n"
                "1) Food timing suggestions\n"
                "2) Hydration guidance\n"
                "3) Possible food interactions to discuss with a pharmacist\n"
                "4) Daily adherence checklist\n\n"
                f"Prescription Summary:\n{structured_text}\n\n"
                f"Medications:\n{meds_text}"
            ),
        },
    ]
    return "".join(stream_text(chat(messages, stream=True))).strip()


def save_record(ocr_text: str, structured_text: str, nutrition_text: str, meds: list[str]) -> Path:
    payload = {
        "id": uuid.uuid4().hex,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ocr_text": ocr_text,
        "medication_candidates": meds,
        "structured_summary": structured_text,
        "nutrition_guidance": nutrition_text,
    }
    record_path = OCR_RECORDS_DIR / f"prescription_record_{payload['id']}.json"
    with open(record_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=True, indent=2)
    return record_path


def run_ocr():
    ensure_patient_context()
    st.image("logo.jpg", width=170, caption=APP_NAME, use_container_width=False)
    st.markdown(f"<h1>{APP_NAME} - Prescription Decoder</h1>", unsafe_allow_html=True)
    st.markdown(f"<p>{TAGLINE}</p>", unsafe_allow_html=True)
    st.markdown("<p>Upload a prescription image or PDF to extract, structure, and save results.</p>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload an image or PDF", type=["jpg", "jpeg", "png", "pdf"])
    use_camera = st.checkbox("Use camera input")
    image_to_process = None

    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(uploaded_file.read())
                pdf_images = ImageProcessor.extract_images_from_pdf(temp_pdf.name)
            if pdf_images:
                image_to_process = pdf_images[0]
                st.image(cv2.cvtColor(image_to_process, cv2.COLOR_BGR2RGB), caption="First page of uploaded PDF", use_container_width=True)
        else:
            pil_image = np.array(Image.open(uploaded_file).convert("RGB"))
            image_to_process = cv2.cvtColor(pil_image, cv2.COLOR_RGB2BGR)
            st.image(pil_image, caption="Uploaded prescription", use_container_width=True)

    elif use_camera:
        picture = st.camera_input("Capture prescription")
        if picture:
            pil_image = np.array(Image.open(picture).convert("RGB"))
            image_to_process = cv2.cvtColor(pil_image, cv2.COLOR_RGB2BGR)
            st.image(pil_image, caption="Captured prescription", use_container_width=True)

    if image_to_process is None:
        st.info("Upload or capture a prescription to start processing.")
        return

    if not st.button("Process Prescription", type="primary"):
        return

    with st.spinner("Running OCR and structuring prescription details..."):
        processed = ImageProcessor.preprocess_image_array(image_to_process)
        ocr_text = pytesseract.image_to_string(processed, lang="eng").strip()
        meds = extract_medication_lines(ocr_text)

        if not ocr_text:
            st.error("No text was extracted. Try a clearer image.")
            return

        structured_text = structure_prescription_with_llm(ocr_text)
        nutrition_text = generate_nutrition_guidance(structured_text, meds)
        record_path = save_record(ocr_text, structured_text, nutrition_text, meds)
        st.session_state["patient_context"]["ocr_text"] = ocr_text
        st.session_state["patient_context"]["structured_data"] = structured_text

    st.image(processed, caption="Preprocessed image", channels="GRAY")
    st.subheader("Extracted OCR Text")
    st.text_area("OCR text", ocr_text, height=180)

    st.subheader("Medication Candidates")
    if meds:
        for item in meds:
            st.write(f"- {item}")
    else:
        st.write("- No clear medication lines detected.")

    st.subheader("Structured Prescription Summary")
    st.markdown(structured_text)

    st.subheader("Nutritional Guidance")
    st.markdown(nutrition_text)

    st.success(f"Local record saved: {record_path}")

    azure_storage = OptionalAzureStorage(AZURE_CONNECTION_STRING, AZURE_CONTAINER_NAME)
    uploaded, message = azure_storage.upload_file(record_path)
    if uploaded:
        st.success(message)
    else:
        st.info(message)


if __name__ == "__main__":
    run_ocr()
