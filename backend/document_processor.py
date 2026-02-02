import os
from pathlib import Path
from typing import List
from fastapi import UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
import PyPDF2
import io

# Use centralized uploads directory
UPLOAD_DIR = Path.home() / "tmp" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def save_upload_file(upload_file: UploadFile, use_case_id: int) -> tuple[str, int]:
    """
    Save uploaded file to ~/tmp/uploads/use_case_<id>/ directory
    Creates use-case-specific folder if it doesn't exist
    Returns: (file_path, file_size)
    """
    use_case_dir = UPLOAD_DIR / f"use_case_{use_case_id}"
    use_case_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = use_case_dir / upload_file.filename
    
    # Save file
    contents = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    return str(file_path), len(contents)

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from PDF file
    """
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text content from text file
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from file based on extension
    """
    extension = Path(file_path).suffix.lower()
    
    if extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif extension in ['.txt', '.md']:
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {extension}")

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Split text into chunks using RecursiveCharacterTextSplitter
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    return chunks
