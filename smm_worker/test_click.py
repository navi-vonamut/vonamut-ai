import uiautomator2 as u2

# Подключаемся
d = u2.connect("192.168.100.87:5555")

# Пытаемся кликнуть по координатам X=500, Y=500
print("Пробуем нажать на экран...")
try:
    d.click(500, 500)
    print("✅ Клик прошел успешно!")
except Exception as e:
    print(f"❌ Всё ещё ошибка: {e}")