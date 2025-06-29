from telethon import Button
from models import ChatService, ConversationService
from .command_handler import CommandHandler

class EventHandler:
    def __init__(self):
        self.command_handler = CommandHandler()
        
    async def menu(self, event):
        buttons = [
            [Button.inline("ប្រចាំថ្ងៃ", "daily_summary")],
            [Button.inline("ប្រចាំសប្តាហ៍", "weekly_summary")],
            [Button.inline("ប្រចាំខែ", "monthly_summary")]
        ]
        await event.respond("ជ្រើសរើសរបាយការណ៍ប្រចាំ:", buttons=buttons)

    async def register(self, event):
        chat_id = event.chat_id
        group_name = event.chat.title
        chat_service = ChatService()
        success, message = chat_service.register_chat_id(chat_id, group_name)
        await event.respond(message)

    async def message(self, event):
        if event.message.text.startswith('/'):
            return

        replied_message = await event.message.get_reply_message()
        if not replied_message:
            return

        chat_id = event.chat_id
        conversation_service = ConversationService()
        question = await conversation_service.get_question_by_message_id(
            chat_id=chat_id,
            message_id=replied_message.id
        )

        
        if question and question.question_type == "date_input": #type: ignore
            await self.command_handler.handle_date_input_response(event, question)
            return

    async def callback(self, event):
        data = event.data.decode()
        if any(data.startswith(prefix) for prefix in ["summary_week_", "summary_month_"]):
            await self.command_handler.handle_period_summary(event, data)
            return

        command_handlers = {
            "menu": self.menu,
            "daily_summary": self.command_handler.handle_daily_summary,
            "weekly_summary": self.command_handler.handle_weekly_summary,
            "monthly_summary": self.command_handler.handle_monthly_summary,
            "other_dates": self.command_handler.handle_other_dates,
        }

        handler = command_handlers.get(data)
        if handler:
            await handler(event)
            return
            
        if data.startswith("summary_of_"):
            await self.command_handler.handle_date_summary(event, data)
            return
            
        await self.command_handler.handle_daily_summary(event)