import calendar

print ('Добро пожаловать в Супер Календарь \n')

year = int(input('Пожалуйста введите год: '))

while not (1 <= (month := int(input(" Пожалуйста введите номер любого месяца:"))) <= 12): print("Ошибка: число должно быть от 1 до 12.")
print(f"Вы ввели корректное число: {month}")

print (calendar.month(year, month))

print ('Всего хорошего! ')