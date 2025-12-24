import os
import re
import logging
import requests
import tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram import InputFile
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
COBALT_API_URL = os.getenv('COBALT_API_URL')

def check_cobalt_health():
    try:
        response = requests.get(COBALT_API_URL.rstrip('/'), timeout=5)
        logger.info(f"Cobalt доступен, статус: {response.status_code}")
        return True
    except Exception as e:
        logger.warning(f"Cobalt недоступен: {e}")
        return False

INSTAGRAM_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)|instagr\.am/(?:reel|p)/([A-Za-z0-9_-]+))',
    re.IGNORECASE
)

TWITTER_X_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:twitter\.com/\w+/status/(\d+)|x\.com/\w+/status/(\d+))',
    re.IGNORECASE
)


def extract_urls(text: str) -> list[str]:
    urls = []
    
    instagram_full_matches = INSTAGRAM_PATTERN.finditer(text)
    for match in instagram_full_matches:
        full_url = match.group(0)
        if not full_url.startswith('http'):
            full_url = 'https://' + full_url
        urls.append(full_url)
    
    twitter_full_matches = TWITTER_X_PATTERN.finditer(text)
    for match in twitter_full_matches:
        full_url = match.group(0)
        if not full_url.startswith('http'):
            full_url = 'https://' + full_url
        urls.append(full_url)
    
    return list(set(urls))


async def download_video(url: str) -> dict | None:
    api_url = COBALT_API_URL.rstrip('/')
    
    try:
        logger.info(f"Запрос к cobalt API: {api_url} с URL: {url}")
        
        response = requests.post(
            api_url,
            json={"url": url},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30
        )
        
        logger.info(f"Ответ cobalt API: статус {response.status_code}")
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP ошибка при запросе к cobalt API: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Тело ответа: {e.response.text[:500]}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Ошибка подключения к cobalt API: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к cobalt API: {e}")
        return None
    except ValueError as e:
        logger.error(f"Не удалось распарсить JSON ответ: {e}")
        return None


async def send_video(update: Update, context: ContextTypes.DEFAULT_TYPE, video_data: dict):
    temp_file = None
    try:
        if video_data.get('status') == 'error':
            error_text = video_data.get('text', 'Неизвестная ошибка')
            await update.message.reply_text(f"Ошибка при загрузке видео: {error_text}")
            return
        
        video_url = None
        
        if 'text' in video_data and video_data['text'].startswith('http'):
            video_url = video_data['text']
        elif 'url' in video_data:
            video_url = video_data['url']
        elif 'videos' in video_data and isinstance(video_data['videos'], list) and len(video_data['videos']) > 0:
            video_info = video_data['videos'][0]
            video_url = video_info.get('url') or video_info.get('videoUrl')
        elif 'video' in video_data:
            video_url = video_data['video']
        
        if not video_url:
            logger.error(f"Не удалось найти URL видео в ответе: {video_data}")
            await update.message.reply_text("Не удалось получить ссылку на видео из ответа API")
            return
        
        logger.info(f"Загружаю видео с URL: {video_url}")
        
        video_response = requests.get(video_url, stream=True, timeout=60)
        video_response.raise_for_status()
        
        content_type = video_response.headers.get('content-type', '')
        content_length = video_response.headers.get('content-length')
        
        if content_length and int(content_length) > 50 * 1024 * 1024:
            await update.message.reply_text(
                "Видео слишком большое для отправки через Telegram. "
                f"Прямая ссылка: {video_url}"
            )
            return
        
        ext = 'mp4'
        if 'video' in content_type:
            if 'webm' in content_type:
                ext = 'webm'
            elif 'quicktime' in content_type or 'mov' in content_type:
                ext = 'mov'
        else:
            url_ext = video_url.split('/')[-1].split('?')[0].split('.')[-1]
            if url_ext in ['mp4', 'webm', 'mov', 'mkv']:
                ext = url_ext
        
        temp_dir = Path(tempfile.gettempdir()) / 'tg-cobalt-bot'
        temp_dir.mkdir(exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            dir=temp_dir,
            suffix=f'.{ext}',
            delete=False
        )
        
        logger.info(f"Сохраняю видео во временный файл: {temp_file.name}")
        
        downloaded_size = 0
        chunk_size = 8192
        
        for chunk in video_response.iter_content(chunk_size=chunk_size):
            if chunk:
                temp_file.write(chunk)
                downloaded_size += len(chunk)
                
                if content_length and downloaded_size > 50 * 1024 * 1024:
                    temp_file.close()
                    os.unlink(temp_file.name)
                    await update.message.reply_text(
                        "Видео слишком большое для отправки через Telegram. "
                        f"Прямая ссылка: {video_url}"
                    )
                    return
        
        temp_file.close()
        
        file_size = os.path.getsize(temp_file.name)
        logger.info(f"Видео загружено, размер: {file_size / 1024 / 1024:.2f} MB")
        
        if file_size > 50 * 1024 * 1024:
            os.unlink(temp_file.name)
            await update.message.reply_text(
                "Видео слишком большое для отправки через Telegram. "
                f"Прямая ссылка: {video_url}"
            )
            return
        
        with open(temp_file.name, 'rb') as video_file:
            await update.message.reply_video(
                video=InputFile(video_file, filename=f'video.{ext}'),
                supports_streaming=True
            )
        
        logger.info("Видео успешно отправлено")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при загрузке видео файла: {e}")
        await update.message.reply_text("Произошла ошибка при загрузке видео файла")
    except Exception as e:
        logger.error(f"Ошибка при отправке видео: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при отправке видео")
    finally:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
                logger.debug(f"Временный файл удален: {temp_file.name}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {temp_file.name}: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    urls = extract_urls(text)
    
    if not urls:
        return
    
    for url in urls:
        status_msg = await update.message.reply_text("⏳ Обрабатываю ссылку...")
        
        try:
            video_data = await download_video(url)
            if video_data:
                await status_msg.edit_text("⏳ Отправляю видео...")
                await send_video(update, context, video_data)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ Не удалось загрузить видео")
        except Exception as e:
            logger.error(f"Ошибка при обработке ссылки {url}: {e}", exc_info=True)
            await status_msg.edit_text("❌ Произошла ошибка при обработке ссылки")


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не установлен в переменных окружения")
    
    logger.info(f"Используется COBALT_API_URL: {COBALT_API_URL}")
    check_cobalt_health()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
