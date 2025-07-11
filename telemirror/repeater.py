import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Optional

from telethon import TelegramClient

from config import DirectionConfig
from telemirror.hints import EventMessage
from telemirror.storage import Database, RepeatedMessage
from telemirror._patch.sending import send_message, send_file


class MessageRepeater:
    """
    Клас для управління повтореннями повідомлень
    
    Керує плануванням, виконанням та відстеженням повторюваних повідомлень
    """
    
    def __init__(
        self,
        database: Database,
        client: TelegramClient,
        logger: logging.Logger,
        check_interval: int = 30,  # check every 30 seconds
        randomize_percent: int = 20  # рандомізація інтервалу ±20%
    ):
        """
        Ініціалізація MessageRepeater
        
        Args:
            database: База даних для зберігання повторюваних повідомлень
            client: Telegram клієнт для відправки повідомлень
            logger: Логгер
            check_interval: Check interval in seconds
            randomize_percent: Відсоток рандомізації інтервалу (1-50)
        """
        self.database = database
        self.client = client
        self.logger = logger
        self.check_interval = check_interval
        self.randomize_percent = max(1, min(50, randomize_percent))  # обмежуємо 1-50%
        self.running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    def _randomize_interval(self, base_interval: int) -> int:
        """
        Додає рандомність до базового інтервалу
        
        Args:
            base_interval: Base interval in seconds
            
        Returns:
            Рандомізований інтервал
        """
        if base_interval <= 0:
            return base_interval
            
        # Обчислюємо рандомний відхил (±randomize_percent%)
        variation = int(base_interval * self.randomize_percent / 100)
        random_offset = random.randint(-variation, variation)
        
        # Ensure interval is at least 60 seconds
        randomized_interval = max(60, base_interval + random_offset)
        
        return randomized_interval
    
    async def schedule_repeat(
        self,
        message: EventMessage,
        config: DirectionConfig,
        target_chat: int
    ) -> None:
        """
        Планування повторення повідомлення
        
        Args:
            message: Повідомлення для повторення
            config: Конфігурація направлення
            target_chat: ID цільового чату
        """
        if not config.repeat_interval or config.repeat_interval <= 0:
            return
        
        # Stop previous repeats for this channel before creating new one
        await self._stop_previous_repeats(message.chat_id, target_chat)
        
        # Рандомізуємо інтервал для початкового повторення
        randomized_interval = self._randomize_interval(config.repeat_interval)
        
        # Серіалізуємо дані повідомлення
        message_data = {
            "text": message.text or "",
            "raw_text": message.raw_text or "",
            "has_media": message.media is not None,
            "media_type": message.media.__class__.__name__ if message.media else None,
            "original_message_id": message.id,
            "original_chat_id": message.chat_id,
        }
        
        # Серіалізуємо конфігурацію
        target_config = {
            "target_chat": target_chat,
            "mode": config.mode,
            "to_topic_id": config.to_topic_id,
            "repeat_interval": randomized_interval,  # використовуємо рандомізований інтервал
            "base_repeat_interval": config.repeat_interval,  # зберігаємо базовий для наступних ітерацій
        }
        
        # Обчислюємо час наступного повторення з рандомізованим інтервалом
        next_repeat_time = datetime.now() + timedelta(seconds=randomized_interval)
        
        # Створюємо запис для повторення
        repeated_message = RepeatedMessage(
            id=None,
            original_id=message.id,
            original_channel=message.chat_id,
            message_data=message_data,
            target_configs=target_config,
            next_repeat_time=next_repeat_time,
            repeat_count=0,
            max_repeats=config.repeat_count,
            created_at=None
        )
        
        # Зберігаємо в базі даних
        repeated_id = await self.database.insert_repeated_message(repeated_message)
        
        self.logger.info(
            f"Scheduled repeat for message {message.id} from chat {message.chat_id} "
            f"to chat {target_chat}, next repeat at {next_repeat_time} "
            f"(interval: {randomized_interval}s, base: {config.repeat_interval}s), "
            f"repeat_id: {repeated_id}"
        )
    
    async def _stop_previous_repeats(self, original_channel: int, target_chat: int) -> None:
        """
        Зупиняє попередні повторення для даного каналу та цільового чату
        
        Args:
            original_channel: ID оригінального каналу
            target_chat: ID цільового чату
        """
        try:
            # Отримуємо всі активні повторення для цього каналу
            active_repeats = await self.database.get_active_repeated_messages_for_channel(
                original_channel, target_chat
            )
            
            if active_repeats:
                self.logger.info(
                    f"Stopping {len(active_repeats)} previous repeats for "
                    f"channel {original_channel} -> {target_chat}"
                )
                
                # Видаляємо старі повторення
                for repeat in active_repeats:
                    await self.database.delete_repeated_message(repeat.id)
                    self.logger.debug(
                        f"Stopped repeat {repeat.id} for message {repeat.original_id}"
                    )
                    
        except AttributeError:
            # Якщо метод get_active_repeated_messages_for_channel не реалізований
            # (для зворотної сумісності), пропускаємо цей крок
            self.logger.debug(
                "Database doesn't support get_active_repeated_messages_for_channel, "
                "skipping previous repeats cleanup"
            )
        except Exception as e:
            self.logger.error(f"Error stopping previous repeats: {e}", exc_info=True)
    
    async def process_pending_repeats(self) -> None:
        """
        Обробка всіх повідомлень, які потребують повторення
        """
        try:
            pending_messages = await self.database.get_pending_repeated_messages()
            
            if not pending_messages:
                return
            
            self.logger.info(f"Processing {len(pending_messages)} pending repeat messages")
            
            for repeated_msg in pending_messages:
                await self._process_single_repeat(repeated_msg)
                
        except Exception as e:
            self.logger.error(f"Error processing pending repeats: {e}", exc_info=True)
    
    async def _process_single_repeat(self, repeated_msg: RepeatedMessage) -> None:
        """
        Обробка одного повторюваного повідомлення
        
        Args:
            repeated_msg: Повторюване повідомлення для обробки
        """
        try:
            target_config = repeated_msg.target_configs
            target_chat = target_config["target_chat"]
            message_data = repeated_msg.message_data
            
            # Якщо повідомлення має медіа, спочатку отримуємо оригінальне повідомлення
            if message_data.get("has_media", False):
                try:
                    # Отримуємо оригінальне повідомлення з медіа
                    original_message = await self.client.get_messages(
                        entity=message_data["original_chat_id"],
                        ids=message_data["original_message_id"]
                    )
                    
                    if original_message and original_message.media:
                        # Відправляємо з медіа
                        await send_file(
                            self.client,
                            entity=target_chat,
                            file=original_message.media,
                            caption=message_data["raw_text"] or message_data["text"],
                            reply_to=target_config.get("to_topic_id"),
                        )
                    else:
                        # Медіа не знайдено, відправляємо тільки текст
                        self.logger.warning(
                            f"Media not found for repeated message {repeated_msg.original_id}, "
                            f"sending text only"
                        )
                        await send_message(
                            self.client,
                            entity=target_chat,
                            message=message_data["raw_text"] or message_data["text"],
                            reply_to=target_config.get("to_topic_id"),
                        )
                        
                except Exception as media_error:
                    self.logger.error(
                        f"Error getting media for repeated message {repeated_msg.original_id}: {media_error}, "
                        f"sending text only"
                    )
                    # Якщо не вдалося отримати медіа, відправляємо тільки текст
                    await send_message(
                        self.client,
                        entity=target_chat,
                        message=message_data["raw_text"] or message_data["text"],
                        reply_to=target_config.get("to_topic_id"),
                    )
            else:
                # Відправляємо звичайне текстове повідомлення
                await send_message(
                    self.client,
                    entity=target_chat,
                    message=message_data["raw_text"] or message_data["text"],
                    reply_to=target_config.get("to_topic_id"),
                )
            
            new_repeat_count = repeated_msg.repeat_count + 1
            
            self.logger.info(
                f"Repeated message {repeated_msg.original_id} from chat {repeated_msg.original_channel} "
                f"to chat {target_chat}, repeat #{new_repeat_count}"
            )
            
            # Перевіряємо, чи потрібно планувати наступне повторення
            max_repeats = repeated_msg.max_repeats
            if max_repeats is None or new_repeat_count < max_repeats:
                # Плануємо наступне повторення з новим рандомізованим інтервалом
                base_interval = target_config.get("base_repeat_interval", 
                                                target_config.get("repeat_interval", 3600))
                randomized_interval = self._randomize_interval(base_interval)
                next_repeat_time = datetime.now() + timedelta(seconds=randomized_interval)
                
                # Оновлюємо конфігурацію з новим рандомізованим інтервалом
                updated_target_config = target_config.copy()
                updated_target_config["repeat_interval"] = randomized_interval
                
                updated_msg = repeated_msg._replace(
                    repeat_count=new_repeat_count,
                    next_repeat_time=next_repeat_time,
                    target_configs=updated_target_config
                )
                
                await self.database.update_repeated_message(updated_msg)
                
                self.logger.info(
                    f"Scheduled next repeat for message {repeated_msg.original_id} "
                    f"at {next_repeat_time} (interval: {randomized_interval}s, base: {base_interval}s)"
                )
            else:
                # Досягнуто максимальну кількість повторень
                await self.database.delete_repeated_message(repeated_msg.id)
                
                self.logger.info(
                    f"Completed all repeats for message {repeated_msg.original_id} "
                    f"(total: {new_repeat_count})"
                )
                
        except Exception as e:
            self.logger.error(
                f"Error processing repeat for message {repeated_msg.original_id}: {e}",
                exc_info=True
            )
            
            # У випадку помилки, можемо спробувати пізніше з рандомізованим інтервалом
            retry_interval = self._randomize_interval(300)  # 5 minutes ± random
            next_retry_time = datetime.now() + timedelta(seconds=retry_interval)
            updated_msg = repeated_msg._replace(next_repeat_time=next_retry_time)
            
            try:
                await self.database.update_repeated_message(updated_msg)
                self.logger.info(f"Rescheduled failed repeat for {retry_interval}s")
            except Exception as retry_error:
                self.logger.error(f"Failed to reschedule failed repeat: {retry_error}")
    
    async def start_scheduler(self) -> None:
        """
        Запуск планувальника повторень
        """
        if self.running:
            self.logger.warning("Repeat scheduler is already running")
            return
        
        self.running = True
        self.logger.info(f"Starting repeat scheduler with {self.check_interval}s interval")
        
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop_scheduler(self) -> None:
        """
        Зупинка планувальника повторень
        """
        if not self.running:
            return
        
        self.running = False
        self.logger.info("Stopping repeat scheduler")
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
    
    async def _scheduler_loop(self) -> None:
        """
        Основний цикл планувальника
        """
        while self.running:
            try:
                await self.process_pending_repeats()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval) 