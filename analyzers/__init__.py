# analyzers/__init__.py
"""
Analyzers moduli: matn, URL va fayl tahlili uchun funksiyalar.
"""

from .text_analyzer import analyze_text, train_scam_model
from .url_scanner import scan_url
from .file_scanner import scan_file

__all__ = [
    "analyze_text",
    "train_scam_model",
    "scan_url",
    "scan_file",
]