""" project/
├── main.py
├── file_handler.py
├── pdf_processor.py
├── file_rename.py
├── requirements.txt
└── Dockerfile """

import os

from file_handler import FileHandler
from pdf_processor import PDFProcessor
from file_rename import FileRename


config = {
    'root_path': '/data/scan',  # Путь внутри контейнера
    'dir_path': 'Новая папка/',
    'pattern': r'№\s[0-9][0-9][0-9][0-9]|Цвет\sRAL\s\d+|№\s\d+[/]\d+',
    'dest_dir': '/data/base_sert'  # Путь внутри контейнера
}


class SertificateProcessor:
    def __init__(self, config):
        self.file_handler = FileHandler(config['root_path'], config['dir_path'])
        self.pdf_processor = PDFProcessor(config['pattern'])
        self.rename = FileRename()
        self.dest_dir = config['dest_dir']

    def process_files(self):
        for file_name in self.file_handler.files:
            src_path = os.path.join(self.file_handler.root_path, file_name)
            print(f'старый путь: {src_path}')

            # Извлекаем текст и ищем совпадения
            text = self.pdf_processor.extract_text(src_path)
            print(f' text {text}')
            matches = self.pdf_processor.find_matches(text)
            print(f' new name file: {matches}')

            # Формируем новое имя
            clean_name = self.rename.sanitize(' '.join(matches))
            dest_path = os.path.join(self.dest_dir, f'{clean_name}.pdf')

            # Переименование
            self.rename.rename(src_path, dest_path)


if __name__ == '__main__':
    processor = SertificateProcessor(config)
    processor.process_files()
