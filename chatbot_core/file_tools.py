"""Conversation upload parsing and answer export helpers.

Uploaded files (PDF, text, images) are converted to plain text so the chatbot
can splice them directly into the user prompt, exactly as if the student had
typed the content.

For images we try multiple paths so the feature degrades gracefully:

1. EXIF auto-rotation + downscale via Pillow (phones often save rotated 4K
   shots that Gemini either rejects or describes upside-down).
2. Gemini Vision when ``GEMINI_API_KEY`` is set.
3. Tesseract OCR (via ``pytesseract``) when the binary is installed.
4. A clear, user-facing error string explaining what's missing so the chatbot
   can show it instead of silently swallowing the failure.
"""

from __future__ import annotations

import base64
import logging
import os
from io import BytesIO
from mimetypes import guess_type
from pathlib import Path
from typing import Iterable

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".log", ".json", ".yaml", ".yml"}

# Marker prefix the chatbot can surface verbatim to the user when an image
# cannot be processed. The chatbot UI looks at the prefix to decide whether to
# render it as a warning instead of as inlined image content.
IMAGE_FAILURE_PREFIX = "[Image non lue]"

logger = logging.getLogger(__name__)


def _guess_image_mime(filename: str, default: str = "image/png") -> str:
    mime, _ = guess_type(filename)
    if mime and mime.startswith("image/"):
        return mime
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "jpg":
        suffix = "jpeg"
    return f"image/{suffix}" if suffix else default


def _prepare_image_for_vision(raw: bytes, filename: str, max_pixels: int = 1600) -> tuple[bytes, str]:
    """Auto-rotate (EXIF), downscale, and re-encode the image for vision APIs.

    Returns ``(image_bytes, mime_type)``. Falls back to the original bytes if
    Pillow can't open the file (e.g. exotic format).
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return raw, _guess_image_mime(filename)

    try:
        with Image.open(BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "P", "LA"}:
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if "A" in image.mode else None)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            longest = max(image.size)
            if longest > max_pixels:
                ratio = max_pixels / longest
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
            return buffer.getvalue(), "image/jpeg"
    except Exception as exc:  # noqa: BLE001 - want to keep going on weird files
        logger.warning("Pillow could not preprocess %s: %s", filename, exc)
        return raw, _guess_image_mime(filename)


def _ocr_with_tesseract(image_bytes: bytes) -> str:
    """Run Tesseract OCR on the image. Returns empty string when unavailable."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            text = pytesseract.image_to_string(image, lang="fra+eng")
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tesseract OCR failed: %s", exc)
        return ""


def extract_image_text(image_bytes: bytes, filename: str, vision_model: str | None = None) -> str:
    """Describe an image and extract any visible text.

    The function returns one of:
    * a real description (Gemini or OCR succeeded);
    * a string starting with :data:`IMAGE_FAILURE_PREFIX` describing exactly
      why the image could not be read (no API key, transient API error,
      Tesseract not installed, etc.). Callers should treat this as user-facing
      feedback rather than as silent failure.
    """
    prepared, mime = _prepare_image_for_vision(image_bytes, filename)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    last_error: str | None = None

    if api_key:
        try:
            from langchain_core.messages import HumanMessage
            from langchain_google_genai import ChatGoogleGenerativeAI

            model_name = (
                (vision_model or os.getenv("VISION_MODEL") or "gemini-2.5-flash").strip()
                or "gemini-2.5-flash"
            )
            chat = ChatGoogleGenerativeAI(model=model_name, temperature=0.0)
            encoded = base64.b64encode(prepared).decode("ascii")
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "Décris cette image en français avec précision. "
                            "Si du texte est visible (panneau, document, capture d'écran, formule, tableau), "
                            "retranscris-le mot pour mot dans une section 'Texte visible'. "
                            "Sinon, fournis une description objective et concise. "
                            "Ne commente pas la qualité de l'image."
                        ),
                    },
                    {"type": "image_url", "image_url": f"data:{mime};base64,{encoded}"},
                ]
            )
            response = chat.invoke([message])
            text = str(response.content).strip()
            if text:
                return text
            last_error = "Gemini Vision a renvoyé une réponse vide."
        except ImportError:
            last_error = "Le paquet langchain-google-genai n'est pas installé."
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini Vision call failed for %s: %s", filename, exc)
            last_error = f"Gemini Vision a échoué ({type(exc).__name__})."

    ocr_text = _ocr_with_tesseract(prepared)
    if ocr_text:
        prefix = "Texte visible (OCR Tesseract)" if not api_key else "Texte visible (OCR de secours)"
        return f"{prefix} :\n{ocr_text}"

    if not api_key and not ocr_text:
        return (
            f"{IMAGE_FAILURE_PREFIX} {filename} : aucun moteur de vision n'est disponible. "
            "Configurez GEMINI_API_KEY (Google AI Studio, gratuit) ou installez Tesseract OCR "
            "(https://github.com/UB-Mannheim/tesseract/wiki) pour activer la lecture d'images."
        )

    if last_error:
        return (
            f"{IMAGE_FAILURE_PREFIX} {filename} : {last_error} "
            "Réessayez dans un instant ou installez Tesseract OCR comme solution de secours."
        )

    return f"{IMAGE_FAILURE_PREFIX} {filename} : image illisible (format ou contenu non supporté)."


def extract_uploaded_text(
    uploaded_file,
    max_chars: int = 12000,
    vision_model: str | None = None,
) -> tuple[str, str]:
    """Extract textual content from a Streamlit ``UploadedFile``.

    Returns a tuple of (text, kind) where ``kind`` is one of
    ``text``, ``pdf``, ``image`` or ``unsupported``.
    """
    suffix = Path(uploaded_file.name).suffix.lower()
    raw = uploaded_file.getvalue()
    if suffix in TEXT_EXTENSIONS:
        text = raw.decode("utf-8", errors="replace")
        return text[:max_chars], "text"
    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError(
                "Installez PyMuPDF pour lire les PDF uploadés: pip install pymupdf"
            ) from exc
        text_parts = []
        with fitz.open(stream=raw, filetype="pdf") as doc:
            for index, page in enumerate(doc, 1):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"[Page {index}]\n{page_text}")
                if sum(len(part) for part in text_parts) >= max_chars:
                    break
        return "\n\n".join(text_parts)[:max_chars], "pdf"
    if suffix in IMAGE_EXTENSIONS:
        description = extract_image_text(raw, uploaded_file.name, vision_model=vision_model)
        return description[:max_chars], "image"
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError:
            return "", "unsupported"
        try:
            document = Document(BytesIO(raw))
            paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
            return "\n".join(paragraphs)[:max_chars], "text"
        except Exception:
            return "", "unsupported"
    return "", "unsupported"


def build_inline_prompt(user_text: str, attachments: Iterable[dict[str, str]]) -> str:
    """Splice attached files into the user prompt as plain text.

    The result is treated exactly like typed input downstream: there is no
    hidden RAG side-channel for the uploads, the LLM sees the same prompt the
    student would have typed by pasting the file content in chat.
    """
    sections: list[str] = []
    typed = (user_text or "").strip()
    if typed:
        sections.append(typed)
    for item in attachments:
        name = item.get("name") or "fichier"
        kind = item.get("kind") or "text"
        text = (item.get("text") or "").strip()
        if not text:
            if kind == "image":
                sections.append(
                    f"[Image jointe : {name} — description automatique indisponible]"
                )
            else:
                sections.append(f"[Fichier joint : {name} — contenu vide ou non lisible]")
            continue
        if kind == "image":
            header = f"[Image jointe : {name} — lecture automatique]"
        elif kind == "pdf":
            header = f"[Document PDF joint : {name}]"
        else:
            header = f"[Fichier joint : {name}]"
        sections.append(f"{header}\n{text}")
    return "\n\n".join(sections).strip()


def attachment_display(attachments: Iterable[dict[str, str]]) -> str:
    """A short markdown summary shown above the inlined content in chat."""
    items = []
    for item in attachments:
        name = item.get("name") or "fichier"
        kind = item.get("kind") or "file"
        icon = {"pdf": "PDF", "image": "Image", "text": "Texte"}.get(kind, "Fichier")
        items.append(f"- **{icon}** : {name}")
    if not items:
        return ""
    return "*Pièces jointes converties en texte :*\n" + "\n".join(items)


# Backward-compatible alias kept in case other modules import it.
def build_uploaded_context(upload_summaries: Iterable[dict[str, str]]) -> str:
    return build_inline_prompt("", upload_summaries)


def export_markdown_to_pdf(title: str, body: str) -> bytes:
    """Render Markdown ``body`` into a polished PDF (headings, tables, code...).

    The heavy lifting lives in :mod:`chatbot_core.export_renderer` so the same
    formatter is reused for downloads triggered from chat ("génère un PDF") and
    for any future exports added to the admin dashboard.
    """
    try:
        from chatbot_core.export_renderer import render_pdf
    except ImportError as exc:
        raise RuntimeError(
            "Installez les dépendances PDF: pip install reportlab markdown beautifulsoup4"
        ) from exc
    return render_pdf(title, body)


def export_markdown_to_docx(title: str, body: str) -> bytes:
    """Render Markdown ``body`` into a properly styled .docx (headings, tables, runs)."""
    try:
        from chatbot_core.export_renderer import render_docx
    except ImportError as exc:
        raise RuntimeError(
            "Installez les dépendances DOCX: pip install python-docx markdown beautifulsoup4"
        ) from exc
    return render_docx(title, body)
