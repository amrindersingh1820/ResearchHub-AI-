import pypdf
from app.utils.logging_config import logger

def read_pdf(file_path: str) -> str:
    """Extract text content from a PDF file."""
    try:
        reader = pypdf.PdfReader(file_path)
        text_content = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_content.append(text)
        return "\n\n".join(text_content)
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {e}")
        return f"Error reading PDF: {e}"
