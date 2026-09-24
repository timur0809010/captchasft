from flask import Flask, request, jsonify
from ultralytics import YOLO
import os
import logging
import uuid
from PIL import Image

# ================================================================
#                        НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ
# ================================================================

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("ultralytics").setLevel(logging.ERROR)

# Папка для временных файлов
TEMP_DIR = "temp_captcha"
os.makedirs(TEMP_DIR, exist_ok=True)

# Путь к модели
MODEL_PATH = os.path.abspath("best.pt")

if not os.path.exists(MODEL_PATH):
    logger.error(f"Модель по пути {MODEL_PATH} не найдена!")
    exit(1)

# Загрузка модели один раз только при старте
model = YOLO(MODEL_PATH, task='detect')
logger.info(f"Модель успешно загружена: {MODEL_PATH}")

# ================================================================
#                        ФУНКЦИЯ ОБРАБОТКИ КАПЧИ
# ================================================================

def process_captcha(image_path):
    """Основная логика распознавания капчи с несколькими попытками"""
    captcha_text = ""
    best_conf = 0.5

    # Пробуем разные уверенности, начиная с самого строгого
    confidence_thresholds = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25]

    for conf in confidence_thresholds:
        results = model.predict(
            source=image_path,
            imgsz=640,
            conf=conf,
            iou=0.4,
            verbose=False
        )

        all_boxes = []
        for result in results:
            boxes = result.boxes.data.tolist()
            all_boxes.extend(boxes)

        # Если нашли хотя бы 5 символов — это основной кандидат
        if len(all_boxes) >= 5:
            # Сортируем по уверенности и берём топ-5
            all_boxes.sort(key=lambda x: x[4], reverse=True)
            top_5 = all_boxes[:5]
            # Сортируем слева направо по координате x
            top_5.sort(key=lambda x: x[0])

            captcha_text = "".join(model.names[int(box[5])] for box in top_5)
            logger.info(f"Успешно распознано (conf={conf}): {captcha_text}")
            return captcha_text

    # Если ни при одном пороге не нашли 5 символов — берём всё что есть
    # (самый последний порог — самый низкий)
    if all_boxes:
        all_boxes.sort(key=lambda x: x[0])  # слева направо
        captcha_text = "".join(model.names[int(box[5])] for box in all_boxes)
        logger.info(f"Распознано частично (меньше 5 символов): {captcha_text}")
        return captcha_text

    logger.warning("Не удалось распознать ни одного символа")
    return ""


# ================================================================
#                           ЭНДПОИНТ SOLVE
# ================================================================

@app.route('/solve', methods=['POST'])
def solve():
    temp_path = None

    try:
        # Проверка что в запросе есть файл
        if 'file' not in request.files:
            return jsonify({'error': 'Отсутствует поле file'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400

        # Уникальное имя каптчи что бы не путаться
        file_ext = os.path.splitext(file.filename)[1] or '.png'
        temp_filename = f"{uuid.uuid4()}{file_ext}"
        temp_path = os.path.join(TEMP_DIR, temp_filename)

        file.save(temp_path)

        # Проверка на существование и валидности файла
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            logger.error(f"Файл не сохранился или пустой: {temp_path}")
            return jsonify({'error': 'Не удалось сохранить файл'}), 500

        # Проверка что это изображение вообще
        try:
            with Image.open(temp_path) as img:
                img.verify()
        except Exception as e:
            logger.error(f"Повреждённый или некорректный файл изображения: {e}")
            return jsonify({'error': 'Некорректный файл изображения'}), 400

        # тут крч решает каптчу
        result_text = process_captcha(temp_path)

        return jsonify({'result': result_text})

    except Exception as e:
        logger.error(f"Критическая ошибка при обработке: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

    finally:
        # Удаление временного файла
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Не удалось удалить временный файл {temp_path}: {e}")


# ================================================================
#                             ЗАПУСК
# ================================================================

if __name__ == '__main__':
    print("Запуск сервера распознавания капчи...")
    print("Эндпоинт: http://0.0.0.0:5000/solve  (POST)")
    app.run(host='0.0.0.0', port=5000, debug=False)
