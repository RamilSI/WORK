""" /Users/admin/Desktop/docker/line-colorant/
├── Dockerfile
├── requirements.txt
├── line-color.py
├── input/
│   └── input.pdf (ваш входящий PDF-файл)
└── output/ (папка для исходящих файлов) """





import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from PyPDF2 import PdfReader, PdfWriter

# Пути к папкам
input_dir = "/app/input"
output_dir = "/app/output"

# Убедимся, что папка для исходящих файлов существует
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Путь к входящему файлу
input_file = os.path.join(input_dir, "input.pdf")

# Путь к исходящему файлу
output_file = os.path.join(output_dir, "output.pdf")

# Чтение входящего PDF-файла
reader = PdfReader(input_file)
writer = PdfWriter()

# Добавляем все страницы из входящего файла в исходящий
for page in reader.pages:
    writer.add_page(page)

# Создаем новый PDF-документ для добавления таблицы
doc = SimpleDocTemplate("temp.pdf", pagesize=A4)

# Данные для таблицы
data = [
    ["Строка 1", "Данные 1"],
    ["Строка 2", "Данные 2"],
    ["Строка 3", "Данные 3"],
]

# Создаем таблицу
table = Table(data, colWidths=[4 * cm, 4 * cm])

# Задаем стиль таблицы
style = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Заголовок
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 12),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Основные строки
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
])

# Применяем стиль
table.setStyle(style)

# Задаем точную высоту строк (в сантиметрах, с точностью до 4 знаков)
row_heights = [0.3050 * cm, 0.4050 * cm, 0.5050 * cm]  # Пример высот строк
for i, height in enumerate(row_heights):
    table._argH[i] = height

# Добавляем таблицу в документ и сохраняем
elements = [table]
doc.build(elements)

# Добавляем созданную таблицу в исходящий PDF
temp_reader = PdfReader("temp.pdf")
for page in temp_reader.pages:
    writer.add_page(page)

# Сохраняем исходящий PDF-файл
with open(output_file, "wb") as f:
    writer.write(f)

# Удаляем временный файл
os.remove("temp.pdf")

print(f"Исходящий PDF-файл сохранен: {output_file}")