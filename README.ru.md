# vot-py

`vot-py` — это современная, быстрая и полностью типизированная библиотека на Python для взаимодействия с **Yandex Video Translation API** (Яндекс Закадровый Перевод Видео). Данная библиотека является портом популярной TypeScript-библиотеки `vot.js`.

Библиотека позволяет отправлять запросы на перевод видео, опрашивать статус готовности, получать ссылки на сгенерированные аудиодорожки перевода, извлекать субтитры (оригинальные и переведенные), скачивать и конвертировать их, а также работать со стримами в реальном времени.

---

## Оглавление
1. [Установка](#установка)
2. [Быстрый старт](#быстрый-старт)
   - [Асинхронный клиент (Рекомендуется)](#асинхронный-клиент-рекомендуется)
   - [Синхронный клиент](#синхронный-клиент)
3. [Основные возможности и модули](#основные-возможности-и-модули)
   - [Автоматическое определение сервиса и извлечение ID](#автоматическое-определение-сервиса-и-извлечение-id)
   - [Перевод видео](#перевод-видео)
   - [Получение субтитров](#получение-субтитров)
   - [Работа со стримами](#работа-со-стримами)
   - [Конвертация форматов субтитров](#конвертация-форматов-субтитров)
4. [Использование CLI (Консольной утилиты)](#использование-cli-консольной-утилиты)
5. [Разработка и тестирование](#разработка-и-тестирование)

---

## Установка

Для установки библиотеки в режиме редактирования или локального использования:

```bash
# С использованием стандартного pip
pip install -e .

# Или с использованием uv (рекомендуется)
uv pip install -e .
```

Пакет автоматически зарегистрирует команду `vot` в вашей системе для использования через консоль.

---

## Быстрый старт

### Асинхронный клиент (Рекомендуется)

Основной клиент библиотеки построен на базе асинхронного `httpx.AsyncClient`.

```python
import asyncio
import httpx
from vot import VOTClient, get_video_data

async def main():
    # Инициализируем HTTP-клиент
    async with httpx.AsyncClient() as http_client:
        # Инициализируем VOTClient
        client = VOTClient(client=http_client)
        
        # Разрешаем URL видео (автоматически определяет хостинг, извлекает ID и метаданные)
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_data = await get_video_data(url, client=http_client)
        
        print(f"Сервис: {video_data.host}, ID Видео: {video_data.video_id}")
        
        # Запрашиваем перевод видео
        response = await client.translate_video(video_data)
        
        if response.translated:
            print(f"Перевод готов! Ссылка на аудио: {response.url}")
        else:
            print(f"Перевод в процессе. Повторите через {response.remaining_time} сек. (Статус: {response.status})")

if __name__ == "__main__":
    asyncio.run(main())
```

### Синхронный клиент

Если ваше приложение написано в синхронном стиле, вы можете использовать `VOTClientSync`, который берет на себя управление циклом событий (event loop).

```python
from vot import VOTClientSync, get_video_data
import httpx

# VOTClientSync поддерживает контекстный менеджер
with VOTClientSync() as client:
    # Для разрешения URL видео все еще требуется http-клиент (синхронный или асинхронный)
    with httpx.Client() as http_client:
        # Поскольку get_video_data асинхронный, мы можем выполнить его через внутренний раннер
        video_data = client._run(get_video_data("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        
    # Запрос перевода происходит синхронно
    response = client.translate_video(video_data)
    if response.translated:
        print(f"Аудио перевода: {response.url}")
```

---

## Основные возможности и модули

### Автоматическое определение сервиса и извлечение ID

Функция `get_video_data` принимает на вход URL видео, сверяет его со встроенным реестром поддерживаемых сайтов (YouTube, Vimeo, Twitch, VK, TikTok, custom-ссылки и др.), извлекает уникальный идентификатор видео и возвращает объект `VideoData`.

```python
from vot import get_video_data

# Поддерживает YouTube (watch-страницы, shorts, live, embed, share-ссылки)
video_data = await get_video_data("https://youtu.be/dQw4w9WgXcQ")
print(video_data.video_id)  # "dQw4w9WgXcQ"
print(video_data.host)      # "youtube"
```

### Перевод видео

Метод `translate_video` отправляет сериализованный Protobuf-запрос к API Яндекса для генерации аудиодорожки.
* **Параметры перевода:**
  - `request_lang`: Исходный язык видео (например, `"en"`, `"de"`, `"zh"` или `"auto"`).
  - `response_lang`: Язык озвучки перевода (например, `"ru"`, `"en"`, `"kk"`).
* **Специфика новых видео:** Если новое видео на YouTube еще ни разу не переводилось, Яндекс требует отправить фиктивный файл отчета об ошибке аудио плеера Яндекса (`fail-audio-js`). Библиотека делает это **автоматически** при первом обращении, если передан параметр `should_send_failed_audio=True`.

### Получение субтитров

Метод `get_subtitles` возвращает структурированный ответ со списком доступных субтитров, включая ссылки на оригинальные субтитры и на их переводы от Яндекса.

```python
subs_response = await client.get_subtitles(video_data)
for sub in subs_response.subtitles:
    print(f"Язык оригинала: {sub.language} -> URL: {sub.url}")
    if sub.translated_url:
        print(f"Перевод на: {sub.translated_language} -> URL: {sub.translated_url}")
```

### Работа со стримами

Библиотека поддерживает синхронный и асинхронный перевод прямых трансляций.
1. `translate_stream` — инициирует перевод потока и возвращает M3U8 плейлист перевода.
2. `ping_stream` — периодический запрос поддержания сессии перевода стрима (keep-alive).

```python
stream_res = await client.translate_stream(video_data)
if stream_res.translated:
    print(f"M3U8 плейлист трансляции: {stream_res.result.url}")
    # Запускаем ping-цикл в фоновом режиме для поддержания активности
    await client.ping_stream(stream_res.ping_id)
```

### Конвертация форматов субтитров

Утилита `convert_subs` позволяет бесшовно конвертировать форматы субтитров между **JSON** (внутренний формат Яндекса), **SRT** и **VTT**:

```python
from vot import convert_subs

# Пример: Конвертация VTT-субтитров в SRT
vtt_data = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nПривет, мир!"
srt_data = convert_subs(vtt_data, output="srt")
print(srt_data)
# Выведет:
# 1
# 00:00:01,000 --> 00:00:03,000
# Привет, мир!

# Конвертация VTT в JSON Яндекса
json_data = convert_subs(vtt_data, output="json")
```

---

## Использование CLI (Консольной утилиты)

Пакет поставляется со встроенной консольной утилитой `vot`, которая опрашивает API в реальном времени, скачивает аудиофайл перевода, а также может сохранять субтитры.

**Вызов справки:**
```bash
vot --help
```

**Примеры использования:**

1. **Получить ссылку на переведённую дорожку (с авто-опросом статуса):**
   ```bash
   vot https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

2. **Перевести видео и скачать аудиофайл перевода локально:**
   ```bash
   vot https://www.youtube.com/watch?v=dQw4w9WgXcQ -o my_translation.mp3
   ```

3. **Запросить перевод с конкретного языка на русский и вывести ссылки на субтитры:**
   ```bash
   vot https://www.youtube.com/watch?v=dQw4w9WgXcQ -f en -t ru -s
   ```

4. **Скачать субтитры с автоматической конвертацией (например, в SRT, VTT или JSON):**
   ```bash
   vot https://www.youtube.com/watch?v=dQw4w9WgXcQ --output-subs subs.srt
   ```

---

## Разработка и тестирование

Для запуска тестов, проверки статической типизации и форматирования кода в репозитории:

```bash
# Запуск тестов (100% покрытие моками)
uv run pytest

# Статическая проверка типов
uv run mypy src tests

# Линтер и форматирование кода
uv run ruff check src tests
uv run ruff format --check src tests
```
