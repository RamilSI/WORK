#!/usr/bin/env python3
"""Добавляет плотности и дозы в мл в файл колеровок."""

import openpyxl
from copy import copy

INPUT = 'Microservices/25г_04_02_Колеровки_Грунт_эмаль_АС_1607_Рем_Люкс.xlsx'
DENSITY = 'Microservices/плотности Рем Колор.xlsx'
OUTPUT = 'Microservices/25г_04_02_Колеровки_Грунт_эмаль_АС_1607_Рем_Люкс.xlsx'

# Читаем плотности
dw = openpyxl.load_workbook(DENSITY, data_only=True)
ds = dw.active
density_map = {}
for row in ds.iter_rows(min_row=3, max_row=ds.max_row, values_only=True):
    name = row[1]
    val = row[2]
    if name and val:
        density_map[str(name).strip()] = float(val)

print("=== Загруженные плотности ===")
for k, v in sorted(density_map.items()):
    print(f"  {k}: {v}")

# Открываем файл колеровок (с формулами)
wb = openpyxl.load_workbook(INPUT)

DENS_COL = 7  # G
DOSE_COL = 8  # H

def find_density(component_name):
    """Ищет плотность по имени компонента (нечеткое сопоставление)."""
    name = str(component_name).strip()
    # Прямое совпадение
    if name in density_map:
        return density_map[name]
    # Попробуем без лишних пробелов/кавычек
    for key, val in density_map.items():
        if key.replace('"', '').replace(' ', '') == name.replace('"', '').replace(' ', ''):
            return val
    # Попробуем частичное совпадение
    for key, val in density_map.items():
        if name.startswith(key[:20]) or key.startswith(name[:20]):
            return val
    return None

def process_sheet(ws):
    total_rows = ws.max_row
    # Найдем строку с заголовком и строку с Итого
    header_row = 1
    total_row = None
    data_rows = []
    
    for r in range(1, total_rows + 1):
        cell = ws.cell(row=r, column=1)
        if cell.value and 'Итого' in str(cell.value):
            total_row = r
            break
    
    if total_row is None:
        print(f"  ⚠ Нет строки 'Итого', пропускаю")
        return
    
    data_rows = list(range(2, total_row))  # строки данных (между заголовком и итогом)
    data_rows = [r for r in data_rows if ws.cell(row=r, column=2).value is not None]
    
    if not data_rows:
        print(f"  ⚠ Нет данных, пропускаю")
        return
    
    # 1. Заголовки
    h_g = ws.cell(row=header_row, column=DENS_COL)
    h_g.value = 'Плотность, г/мл'
    
    h_h = ws.cell(row=header_row, column=DOSE_COL)
    h_h.value = 'Доза, мл'
    
    # 2. Заполняем данные
    for r in data_rows:
        comp = ws.cell(row=r, column=1).value
        if comp is None:
            continue
        
        dens_val = find_density(comp)
        dens_cell = ws.cell(row=r, column=DENS_COL)
        
        if dens_val is not None:
            dens_cell.value = dens_val
            # Формат числа
            dens_cell.number_format = '0.000'
        else:
            print(f"  ⚠ Плотность не найдена для: '{comp}'")
            continue
        
        # Доза = D / плотность
        dose_cell = ws.cell(row=r, column=DOSE_COL)
        dose_cell.value = f'=D{r}/G{r}'
        dose_cell.number_format = '0.00'
    
    # 3. Итого для дозы
    dose_cells = [f'H{r}' for r in data_rows]
    if dose_cells:
        total_dose = ws.cell(row=total_row, column=DOSE_COL)
        total_dose.value = f'=SUM({",".join(dose_cells)})'
        total_dose.number_format = '0.00'
    
    print(f"  ✅ Обработано: {len(data_rows)} компонентов")

# Обработка всех RAL-листов
ral_sheets = [s for s in wb.sheetnames if s != 'List']
for sheet_name in ral_sheets:
    print(f"\n=== Обработка {sheet_name} ===")
    ws = wb[sheet_name]
    process_sheet(ws)

# Сохраняем
wb.save(OUTPUT)
print(f"\n✅ Сохранено в {OUTPUT}")
