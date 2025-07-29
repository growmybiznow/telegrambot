from dotenv import load_dotenv
import os
import tempfile
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("No se encontró TELEGRAM_BOT_TOKEN en .env")

# URL del backend
BACKEND_URL = "https://telegrambot-eljv.onrender.com/process-file"

# Estados de conversación
WAITING_CONFIRMATION = 1
pending_files = {}


async def safe_delete(path: str):
    """Elimina archivo temporal si existe."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida"""
    await update.message.reply_text(
        "Bot operativo. Envía un archivo PDF o MP3 para subirlo.\n\n"
        "Si el archivo ya existe podrás responder con los botones:\n"
        "• si – Sobrescribir\n"
        "• pasar – Omitir\n"
        "• cancelar – Cancelar"
    )


def upload_to_backend(file_path, file_name, overwrite=False):
    """Envía archivo al backend."""
    with open(file_path, "rb") as f:
        files = {"file": (file_name, f)}
        data = {"source": "bot"}
        if overwrite:
            data["overwrite"] = "true"
        return requests.post(BACKEND_URL, files=files, data=data, timeout=120)


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe un archivo desde Telegram, lo guarda y lo envía al backend."""
    document = update.message.document
    await update.message.reply_text(f"📄 Recibí tu archivo: {document.file_name}\nProcesando...")

    temp_path = None
    try:
        # Descargar a archivo temporal
        telegram_file = await document.get_file()
        suffix = os.path.splitext(document.file_name)[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
        await telegram_file.download_to_drive(custom_path=temp_path)

        # Subida al backend (bloqueante, en hilo aparte)
        from asyncio import to_thread
        resp = await to_thread(upload_to_backend, temp_path, document.file_name, False)

        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status")

            if status == "duplicate":
                # Guardamos archivo pendiente para preguntar acción
                pending_files[update.effective_chat.id] = (temp_path, document.file_name)

                keyboard = [["si", "pasar", "cancelar"]]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True
                )

                await update.message.reply_text(
                    f"⚠️ El archivo ya existe:\n{result.get('file_key')}\n\n"
                    "¿Qué deseas hacer?",
                    reply_markup=reply_markup
                )
                return WAITING_CONFIRMATION

            elif status == "processed":
                await update.message.reply_text("✅ Archivo procesado correctamente.")
                await safe_delete(temp_path)
            else:
                await update.message.reply_text("⚠️ Respuesta inesperada del backend.")
                await safe_delete(temp_path)
        else:
            await update.message.reply_text(
                f"❌ Error del backend ({resp.status_code}): {resp.text}"
            )
            await safe_delete(temp_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Error al procesar el archivo: {e}")
        await safe_delete(temp_path)


async def confirm_overwrite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestión de archivos duplicados: sobrescribir, pasar o cancelar."""
    decision = update.message.text.strip().lower()
    chat_id = update.effective_chat.id

    if chat_id not in pending_files:
        await update.message.reply_text("No hay archivos pendientes para procesar.")
        return ConversationHandler.END

    file_path, file_name = pending_files.pop(chat_id)

    try:
        from asyncio import to_thread
        if decision == "si":
            await update.message.reply_text("Sobrescribiendo archivo, espera...")
            resp = await to_thread(upload_to_backend, file_path, file_name, True)
            if resp.status_code == 200:
                await update.message.reply_text("✅ Archivo sobrescrito con éxito.")
            else:
                await update.message.reply_text(
                    f"❌ Error al sobrescribir ({resp.status_code}): {resp.text}"
                )

        elif decision == "pasar":
            await update.message.reply_text("Archivo omitido.")

        elif decision == "cancelar":
            await update.message.reply_text("Operación cancelada.")

        else:
            # Opción inválida → vuelve a preguntar
            await update.message.reply_text(
                "Respuesta no válida. Usa los botones o escribe: si, pasar o cancelar."
            )
            pending_files[chat_id] = (file_path, file_name)
            return WAITING_CONFIRMATION

    except Exception as e:
        await update.message.reply_text(f"❌ Error durante la operación: {e}")
    finally:
        await safe_delete(file_path)

    return ConversationHandler.END


def main():
    print("Iniciando Telegram Bot...")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL, handle_file)],
        states={
            WAITING_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_overwrite)
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        per_chat=True,
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    # La forma correcta en v20 (NO usar asyncio.run())
    app.run_polling()


if __name__ == "__main__":
    main()