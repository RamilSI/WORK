import os


class FileHandler:
    """ Работа с файловой системой """
    def __init__(self, root_path, dir_path):
        self.root_path = os.path.join(root_path, dir_path)
        self.files = self._get_filtered_files()
        print(self.files)

    def _get_filtered_files(self):
        """ Фильтр исключающий файл .DS_Store"""
        return [f for f in os.listdir(self.root_path) if f != '.DS_Store']