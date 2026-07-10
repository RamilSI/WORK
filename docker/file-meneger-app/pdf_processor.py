import re
import fitz


class PDFProcessor:
    """Обработка PDF-файлов"""
    def __init__(self, pattern):
        self.pattern = re.compile(pattern)

    def extract_text(self, file_path) -> str:
        """Извлекает текст из PDF"""
        with fitz.open(file_path) as doc:
            return "".join(page.get_text() for page in doc)

    def find_matches(self, text):
        """Ищет совпадения по паттерну"""
        return self.pattern.findall(text)