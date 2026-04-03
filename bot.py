from html import escape
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import DEFAULT_PARSE_LIMIT, REGIONS, get_region_name, require_telegram_token
from database import Export, ParseSession, SessionLocal
from export import ExportManager
from logger import setup_logger
from parser_manager import ParserManager

logger = setup_logger("bot")
LIMIT_OPTIONS = tuple(dict.fromkeys(value for value in (DEFAULT_PARSE_LIMIT, 30, 50, 100) if value > 0))


class ParserBot:
    """Telegram бот для парсинга контактов."""

    def __init__(self):
        self.pm = ParserManager()
        self.em = ExportManager()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню."""
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("Start command: user=%s", user_id)
        self._reset_search_context(context)
        if update.callback_query:
            await update.callback_query.answer()

        await self._reply_or_edit(
            update,
            "👋 <b>Parser Bot</b>\n\n"
            "Поиск контактов и продавцов из 2ГИС и Kaspi.\n\n"
            "Выберите действие:",
            reply_markup=self._main_menu_markup(),
            parse_mode=ParseMode.HTML,
        )

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать краткую справку."""
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("Help command: user=%s", user_id)
        if update.callback_query:
            await update.callback_query.answer()

        help_text = (
            "<b>📖 Справка</b>\n\n"
            "1. Нажмите <b>Новый поиск</b>.\n"
            "2. Выберите источник, город и лимит.\n"
            "3. Отправьте текстовый запрос, например: <code>кафе</code> или <code>электроника</code>.\n"
            "4. После парсинга откройте результаты или выгрузите их в CSV/Excel."
        )

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 В меню", callback_data="back_main")]]
        )
        await self._reply_or_edit(
            update,
            help_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка inline-кнопок."""
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id

        logger.info("Button: %s, user=%s", data, user_id)

        try:
            if data == "help":
                await self.help_cmd(update, context)
            elif data == "new_search":
                await self.show_sources(update, context)
            elif data.startswith("source_"):
                source = data.replace("source_", "", 1)
                context.user_data["source"] = source
                context.user_data["mode"] = None
                context.user_data.pop("region", None)
                context.user_data.pop("limit", None)
                await self.show_regions(update, context)
            elif data == "back_regions":
                context.user_data["mode"] = None
                context.user_data.pop("region", None)
                context.user_data.pop("limit", None)
                await self.show_regions(update, context)
            elif data.startswith("region_"):
                region = data.replace("region_", "", 1)
                context.user_data["region"] = region
                context.user_data["mode"] = None
                context.user_data.pop("limit", None)
                await self.show_limits(update, context)
            elif data == "back_limits":
                context.user_data["mode"] = None
                await self.show_limits(update, context)
            elif data.startswith("limit_"):
                limit = int(data.replace("limit_", "", 1))
                context.user_data["limit"] = limit
                context.user_data["mode"] = "query"
                await self.show_query_prompt(update, context)
            elif data == "view_results":
                await self.show_results(update, context)
            elif data == "export":
                await self.show_export_formats(update, context)
            elif data.startswith("export_"):
                fmt = data.replace("export_", "", 1)
                await self.do_export(update, context, fmt)
            elif data == "back_main":
                await self.start(update, context)
            else:
                await query.answer("Неизвестное действие", show_alert=True)
        except Exception as e:
            logger.error("Button error: %s", e, exc_info=True)
            await query.answer(f"Ошибка: {str(e)[:80]}", show_alert=True)

    async def show_sources(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор источника."""
        self._reset_search_context(context)
        if update.callback_query:
            await update.callback_query.answer()

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("2ГИС", callback_data="source_2gis")],
                [InlineKeyboardButton("Kaspi", callback_data="source_kaspi")],
                [InlineKeyboardButton("Оба источника", callback_data="source_both")],
                [InlineKeyboardButton("🏠 В меню", callback_data="back_main")],
            ]
        )

        await self._reply_or_edit(
            update,
            "Выберите источник:",
            reply_markup=keyboard,
        )

    async def show_regions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор города."""
        if update.callback_query:
            await update.callback_query.answer()

        keyboard_rows = []
        row = []
        for region_key, region_name in REGIONS.items():
            row.append(InlineKeyboardButton(region_name, callback_data=f"region_{region_key}"))
            if len(row) == 2:
                keyboard_rows.append(row)
                row = []

        if row:
            keyboard_rows.append(row)

        keyboard_rows.append([InlineKeyboardButton("◀️ Назад", callback_data="new_search")])

        await self._reply_or_edit(
            update,
            "Выберите город:",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )

    async def show_limits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор лимита результатов."""
        if update.callback_query:
            await update.callback_query.answer()

        source = context.user_data.get("source", "both")
        region = context.user_data.get("region", "almaty")
        selected_limit = context.user_data.get("limit")

        keyboard_rows = []
        row = []
        for limit in LIMIT_OPTIONS:
            label = f"✅ {limit}" if limit == selected_limit else str(limit)
            row.append(InlineKeyboardButton(label, callback_data=f"limit_{limit}"))
            if len(row) == 2:
                keyboard_rows.append(row)
                row = []

        if row:
            keyboard_rows.append(row)

        keyboard_rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back_regions")])

        await self._reply_or_edit(
            update,
            "Выберите лимит результатов:\n"
            f"Источник: <b>{self._format_source(source)}</b>\n"
            f"Город: <b>{get_region_name(region)}</b>\n"
            f"По умолчанию: <b>{DEFAULT_PARSE_LIMIT}</b>",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            parse_mode=ParseMode.HTML,
        )

    async def show_query_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать приглашение к вводу поискового запроса."""
        if update.callback_query:
            await update.callback_query.answer()

        source = context.user_data.get("source", "both")
        region = context.user_data.get("region", "almaty")
        limit = self._get_selected_limit(context)

        await self._reply_or_edit(
            update,
            f"Источник: <b>{self._format_source(source)}</b>\n"
            f"Город: <b>{get_region_name(region)}</b>\n"
            f"Лимит: <b>{limit}</b>\n\n"
            "Введите запрос:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("◀️ Назад", callback_data="back_limits")]]
            ),
            parse_mode=ParseMode.HTML,
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка поискового запроса."""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        mode = context.user_data.get("mode")

        logger.info("Text from user=%s: mode=%s, len=%s", user_id, mode, len(text))

        if mode != "query" or len(text) < 2:
            await update.message.reply_text(
                "Нажмите /start, выберите источник, город и лимит, затем отправьте запрос."
            )
            return

        source = context.user_data.get("source", "both")
        region = context.user_data.get("region", "almaty")
        region_name = get_region_name(region)
        limit = self._get_selected_limit(context)

        status_message = await update.message.reply_text(
            f"⏳ Ищу данные...\n"
            f"Запрос: {text}\n"
            f"Источник: {self._format_source(source)}\n"
            f"Город: {region_name}\n"
            f"Лимит: {limit}"
        )

        db = SessionLocal()
        try:
            parse_session = self.pm.parse(
                db=db,
                query=text,
                source=source,
                city=region,
                user_id=user_id,
                limit=limit,
            )

            if parse_session.status != "completed":
                raise RuntimeError(parse_session.error_message or "Парсинг завершился с ошибкой")

            context.user_data.update(
                {
                    "mode": None,
                    "last_parse_session_id": parse_session.id,
                    "last_query": text,
                    "last_source": source,
                    "last_region": region,
                    "last_limit": limit,
                }
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📊 Посмотреть результаты", callback_data="view_results")],
                    [
                        InlineKeyboardButton("📄 CSV", callback_data="export_csv"),
                        InlineKeyboardButton("📊 Excel", callback_data="export_xlsx"),
                    ],
                    [InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search")],
                ]
            )

            await status_message.edit_text(
                "✅ <b>Поиск завершён</b>\n"
                f"Запрос: <b>{escape(text)}</b>\n"
                f"Источник: {self._format_source(source)}\n"
                f"Город: {region_name}\n"
                f"Лимит: {limit}\n"
                f"Найдено записей: <b>{parse_session.results_count}</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )

            logger.info(
                "Parse completed for user=%s: session_id=%s, results=%s",
                user_id,
                parse_session.id,
                parse_session.results_count,
            )
        except Exception as e:
            logger.error("Parse error: %s", e, exc_info=True)
            await status_message.edit_text(f"❌ Ошибка: {str(e)[:120]}")
        finally:
            db.close()

    async def show_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать результаты последней сессии пользователя."""
        await update.callback_query.answer()

        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            parse_session = self._get_user_session(db, user_id, context)
            if not parse_session:
                await self._reply_or_edit(update, "📭 У вас пока нет завершённых сессий.")
                return

            companies = self.pm.get_session_results(db, parse_session.id, limit=10)
            if not companies:
                await self._reply_or_edit(update, "📭 В последней сессии нет данных для показа.")
                return

            lines = [
                "📊 <b>Последняя сессия</b>",
                f"Запрос: <b>{escape(parse_session.query or '')}</b>",
                f"Источник: {self._format_source(parse_session.source)}",
                f"Город: {parse_session.region}",
                f"Всего записей: <b>{parse_session.results_count}</b>",
                "",
            ]

            for index, company in enumerate(companies, start=1):
                lines.append(f"{index}. <b>{escape(company.name or '')}</b>")
                if company.phone:
                    lines.append(escape(company.phone))
                if company.city:
                    lines.append(escape(company.city))
                lines.append("")

            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⬇️ Экспорт", callback_data="export")],
                    [InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search")],
                    [InlineKeyboardButton("🏠 В меню", callback_data="back_main")],
                ]
            )

            await self._reply_or_edit(
                update,
                "\n".join(lines).strip(),
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        finally:
            db.close()

    async def show_export_formats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать доступные форматы экспорта."""
        await update.callback_query.answer()

        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            parse_session = self._get_user_session(db, user_id, context)
            if not parse_session:
                await update.callback_query.answer("Сначала выполните поиск", show_alert=True)
                return

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("📄 CSV", callback_data="export_csv"),
                        InlineKeyboardButton("📊 Excel", callback_data="export_xlsx"),
                    ],
                    [InlineKeyboardButton("◀️ К результатам", callback_data="view_results")],
                ]
            )

            await self._reply_or_edit(
                update,
                "Выберите формат экспорта:\n"
                f"Запрос: {parse_session.query}\n"
                f"Записей: {parse_session.results_count}",
                reply_markup=keyboard,
            )
        finally:
            db.close()

    async def do_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE, fmt: str):
        """Экспортировать данные последней сессии."""
        await update.callback_query.answer()

        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            parse_session = self._get_user_session(db, user_id, context)
            if not parse_session:
                await update.callback_query.answer("Нет данных для экспорта", show_alert=True)
                return

            companies = self.pm.get_session_results(db, parse_session.id)
            if not companies:
                await update.callback_query.answer("Нет данных для экспорта", show_alert=True)
                return

            filename = f"session_{parse_session.id}_{fmt}_{parse_session.started_at.strftime('%Y%m%d_%H%M%S')}.{fmt}"
            if fmt == "csv":
                filepath = self.em.export_to_csv(companies, filename=filename)
            else:
                filepath = self.em.export_to_excel(companies, filename=filename)

            db.add(
                Export(
                    user_id=user_id,
                    filename=filepath.name,
                    format=fmt,
                    records_count=len(companies),
                )
            )
            db.commit()

            with open(filepath, "rb") as file:
                await update.effective_chat.send_document(
                    document=file,
                    filename=filepath.name,
                    caption=(
                        f"✅ Экспорт готов\n"
                        f"Запрос: {parse_session.query}\n"
                        f"Формат: {fmt.upper()}\n"
                        f"Записей: {len(companies)}"
                    ),
                )

            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📊 К результатам", callback_data="view_results")],
                    [InlineKeyboardButton("🏠 В меню", callback_data="back_main")],
                ]
            )
            await self._reply_or_edit(
                update,
                f"✅ Файл <b>{filepath.name}</b> отправлен.",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Export error: %s", e, exc_info=True)
            await update.callback_query.answer("Не удалось выполнить экспорт", show_alert=True)
        finally:
            db.close()

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик ошибок."""
        logger.error("Unhandled error: %s", context.error, exc_info=True)

    def _get_user_session(
        self,
        db,
        user_id: int,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> Optional[ParseSession]:
        """Получить последнюю сессию пользователя, сначала из контекста, затем из БД."""
        session_id = context.user_data.get("last_parse_session_id")
        if session_id:
            parse_session = db.query(ParseSession).filter(
                ParseSession.id == session_id,
                ParseSession.user_id == user_id,
            ).first()
            if parse_session:
                return parse_session

        parse_session = self.pm.get_latest_session(db, user_id)
        if parse_session:
            context.user_data["last_parse_session_id"] = parse_session.id
        return parse_session

    async def _reply_or_edit(
        self,
        update: Update,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = None,
    ):
        """Единая точка для ответа сообщением или редактирования callback-сообщения."""
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return

        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    def _main_menu_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔍 Новый поиск", callback_data="new_search")],
                [InlineKeyboardButton("📊 Результаты", callback_data="view_results")],
                [InlineKeyboardButton("⬇️ Экспорт", callback_data="export")],
                [InlineKeyboardButton("ℹ️ Справка", callback_data="help")],
            ]
        )

    def _get_selected_limit(self, context: ContextTypes.DEFAULT_TYPE) -> int:
        value = context.user_data.get("limit", DEFAULT_PARSE_LIMIT)
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return DEFAULT_PARSE_LIMIT
        return limit if limit > 0 else DEFAULT_PARSE_LIMIT

    def _reset_search_context(self, context: ContextTypes.DEFAULT_TYPE):
        for key in ("source", "region", "limit"):
            context.user_data.pop(key, None)
        context.user_data["mode"] = None

    def _format_source(self, source: str) -> str:
        labels = {
            "2gis": "2ГИС",
            "kaspi": "Kaspi",
            "both": "2ГИС + Kaspi",
        }
        return labels.get(source, source)


def main():
    """Запуск бота."""
    token = require_telegram_token()
    logger.info("Bot starting...")

    app = Application.builder().token(token).build()
    bot = ParserBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    app.add_error_handler(bot.error_handler)

    logger.info("Bot ready")
    print("Бот запущен.\n")
    logger.info("Entering polling loop")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception:
        logger.exception("Polling loop failed")
        raise
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()
