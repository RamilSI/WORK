import re
import shutil


class FileRename:
    """Переименование и перемещение файлов"""
    @staticmethod
    def sanitize(name):
        return re.sub(r'[\\/*?:"|<>]', '_', name).strip(' .')

    def rename(self, src, dest_dir):
        """Безопасное переименование с обработкой ошибок"""
        try:
            shutil.move(src, dest_dir)
        except (FileNotFoundError, PermissionError) as e:
            print(f'Ошибка {e}')