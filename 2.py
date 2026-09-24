import os
import sys
import requests
from collections import Counter

# ================================================================
#                        НАСТРОЙКИ
# ================================================================

URL = "http://localhost:5000/solve"
TEST_DIR = "test_captchas"          # папка с тестовыми картинками
VALID_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
TIMEOUT = 10                        # секунд на один запрос

# ================================================================
#                        ПРОВЕРКА ПАПКИ
# ================================================================

if not os.path.isdir(TEST_DIR):
    print(f"❌ Папка '{TEST_DIR}' не найдена.")
    sys.exit(1)

files = sorted(
    f for f in os.listdir(TEST_DIR)
    if f.lower().endswith(VALID_EXT)
)

if not files:
    print(f"❌ В папке '{TEST_DIR}' нет картинок.")
    sys.exit(1)

print(f"📁 Найдено картинок: {len(files)}")
print(f"🌐 Сервер: {URL}\n")
print("-" * 60)

# ================================================================
#                        ОСНОВНОЙ ЦИКЛ
# ================================================================

total = 0
correct = 0
errors = []            # список (filename, expected, got)
api_failures = []      # список (filename, ошибка)

for fname in files:
    path = os.path.join(TEST_DIR, fname)
    expected = os.path.splitext(fname)[0].strip()

    try:
        with open(path, "rb") as f:
            r = requests.post(
                URL,
                files={"file": f},
                timeout=TIMEOUT
            )
    except requests.exceptions.RequestException as e:
        print(f"⚠️  {fname}: ошибка запроса — {e}")
        api_failures.append((fname, str(e)))
        continue

    if r.status_code != 200:
        print(f"⚠️  {fname}: HTTP {r.status_code} — {r.text[:100]}")
        api_failures.append((fname, f"HTTP {r.status_code}"))
        continue

    try:
        got = r.json().get("result", "")
    except ValueError:
        print(f"⚠️  {fname}: ответ не JSON — {r.text[:100]}")
        api_failures.append((fname, "не JSON"))
        continue

    total += 1
    ok = (got == expected)

    if ok:
        correct += 1
        print(f"✅ {fname:30s} ожидалось={expected:6s} получено={got:6s}")
    else:
        print(f"❌ {fname:30s} ожидалось={expected:6s} получено={got:6s}")
        errors.append((fname, expected, got))

# ================================================================
#                        ИТОГОВАЯ СТАТИСТИКА
# ================================================================

print("\n" + "=" * 60)
print("📊 ИТОГИ")
print("=" * 60)

if total == 0:
    print("❌ Ни одной успешно обработанной картинки.")
    sys.exit(1)

acc = correct / total * 100
print(f"Всего проверено:   {total}")
print(f"Правильно:         {correct}")
print(f"Неправильно:       {len(errors)}")
print(f"Точность:          {acc:.2f}%")

if api_failures:
    print(f"\n⚠️  Сбоев API:      {len(api_failures)}")

# ================================================================
#                        АНАЛИЗ ОШИБОК
# ================================================================

if errors:
    print("\n" + "-" * 60)
    print("🔍 ОШИБКИ (что путает модель)")
    print("-" * 60)

    # какие символы чаще всего путаются
    char_errors = Counter()
    length_errors = 0

    for fname, exp, got in errors:
        if len(exp) != len(got):
            length_errors += 1
            print(f"  {fname}: длина не совпала ({len(got)} вместо {len(exp)}), получено '{got}'")
        else:
            for a, b in zip(exp, got):
                if a != b:
                    char_errors[f"{a} → {b}"] += 1

    if char_errors:
        print("\n  Топ-10 частых подмен символов:")
        for pair, cnt in char_errors.most_common(10):
            print(f"    {pair:10s} : {cnt} раз")

    if length_errors:
        print(f"\n  Ошибок по длине строки: {length_errors} "
              f"(модель нашла не 5 цифр)")

# ================================================================
#                        СОХРАНЕНИЕ ОШИБОК В ФАЙЛ
# ================================================================

if errors:
    out = "errors.txt"
    with open(out, "w", encoding="utf-8") as f:
        for fname, exp, got in errors:
            f.write(f"{fname}\texpected={exp}\tgot={got}\n")
    print(f"\n💾 Список ошибок сохранён в '{out}'")