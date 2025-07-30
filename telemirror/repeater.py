import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from dataclasses import dataclass

from telethon import TelegramClient

from config import DirectionConfig
from telemirror.hints import EventMessage
from telemirror._patch.sending import send_message, send_file


@dataclass
class RepeatTask:
    """
    Simple repeat task stored in memory
    """
    original_id: int
    original_channel: int
    target_chat: int
    message_text: str
    message_raw_text: str
    has_media: bool
    media_type: Optional[str]
    repeat_interval: int
    base_repeat_interval: int
    to_topic_id: Optional[int]
    mode: str
    next_repeat_time: datetime
    repeat_count: int = 0


class MessageRepeater:
    """
    Simple message repeater with infinite retries and no database dependency
    
    Manages scheduling, execution and tracking of repeated messages in memory
    """
    
    def __init__(
        self,
        client: TelegramClient,
        logger: logging.Logger,
        check_interval: int = 30,  # check every 30 seconds
        randomize_percent: int = 20  # randomize interval ±20%
    ):
        """
        Initialize MessageRepeater
        
        Args:
            client: Telegram client for sending messages
            logger: Logger
            check_interval: Check interval in seconds
            randomize_percent: Percentage of interval randomization (1-50)
        """
        self.client = client
        self.logger = logger
        self.check_interval = check_interval
        self.randomize_percent = max(1, min(50, randomize_percent))  # limit 1-50%
        self.running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # In-memory storage for repeat tasks
        self._repeat_tasks: Dict[str, RepeatTask] = {}
        self._channel_tasks: Dict[int, Set[str]] = {}  # track tasks per channel
    
    def _randomize_interval(self, base_interval: int) -> int:
        """
        Add randomness to base interval
        
        Args:
            base_interval: Base interval in seconds
            
        Returns:
            Randomized interval
        """
        if base_interval <= 0:
            return base_interval
            
        # Calculate random deviation (±randomize_percent%)
        variation = int(base_interval * self.randomize_percent / 100)
        random_offset = random.randint(-variation, variation)
        
        # Ensure interval is at least 60 seconds
        randomized_interval = max(60, base_interval + random_offset)
        
        return randomized_interval
    
    def _get_task_key(self, original_channel: int, target_chat: int) -> str:
        """Generate unique task key for channel->target mapping"""
        return f"{original_channel}:{target_chat}"
    
    async def schedule_repeat(
        self,
        message: EventMessage,
        config: DirectionConfig,
        target_chat: int
    ) -> None:
        """
        Schedule message repetition (infinite retries)
        
        Args:
            message: Message to repeat
            config: Direction configuration
            target_chat: Target chat ID
        """
        if not config.repeat_interval or config.repeat_interval <= 0:
            return
        
        # Stop previous repeats for this channel->target before creating new one
        self._stop_previous_repeats(message.chat_id, target_chat)
        
        # Randomize interval for initial repeat
        randomized_interval = self._randomize_interval(config.repeat_interval)
        
        # Calculate next repeat time with randomized interval
        next_repeat_time = datetime.now() + timedelta(seconds=randomized_interval)
        
        # Create repeat task
        task_key = self._get_task_key(message.chat_id, target_chat)
        repeat_task = RepeatTask(
            original_id=message.id,
            original_channel=message.chat_id,
            target_chat=target_chat,
            message_text=message.text or "",
            message_raw_text=message.raw_text or "",
            has_media=message.media is not None,
            media_type=message.media.__class__.__name__ if message.media else None,
            repeat_interval=randomized_interval,
            base_repeat_interval=config.repeat_interval,
            to_topic_id=config.to_topic_id,
            mode=config.mode,
            next_repeat_time=next_repeat_time,
            repeat_count=0
        )
        
        # Store in memory
        self._repeat_tasks[task_key] = repeat_task
        self._channel_tasks.setdefault(message.chat_id, set()).add(task_key)
        
        self.logger.info(
            f"Scheduled infinite repeat for message {message.id} from chat {message.chat_id} "
            f"to chat {target_chat}, next repeat at {next_repeat_time} "
            f"(interval: {randomized_interval}s, base: {config.repeat_interval}s)"
        )
    
    def _stop_previous_repeats(self, original_channel: int, target_chat: int) -> None:
        """
        Stop previous repeats for given channel and target chat
        
        Args:
            original_channel: Original channel ID
            target_chat: Target chat ID
        """
        task_key = self._get_task_key(original_channel, target_chat)
        
        if task_key in self._repeat_tasks:
            del self._repeat_tasks[task_key]
            
            # Clean up channel tracking
            channel_tasks = self._channel_tasks.get(original_channel, set())
            channel_tasks.discard(task_key)
            if not channel_tasks:
                self._channel_tasks.pop(original_channel, None)
            
            self.logger.info(
                f"Stopped previous repeat for channel {original_channel} -> {target_chat}"
            )
    
    async def process_pending_repeats(self) -> None:
        """
        Process all messages that need repetition
        """
        if not self._repeat_tasks:
            return
        
        now = datetime.now()
        pending_tasks = [
            task for task in self._repeat_tasks.values()
            if task.next_repeat_time <= now
        ]
        
        if not pending_tasks:
            return
        
        self.logger.info(f"Processing {len(pending_tasks)} pending repeat messages")
        
        for task in pending_tasks:
            await self._process_single_repeat(task)
    
    async def _process_single_repeat(self, task: RepeatTask) -> None:
        """
        Process single repeated message
        
        Args:
            task: Repeat task to process
        """
        try:
            # If message has media, try to get original message first
            if task.has_media:
                try:
                    # Get original message with media
                    original_message = await self.client.get_messages(
                        entity=task.original_channel,
                        ids=task.original_id
                    )
                    
                    if original_message and original_message.media:
                        # Send with media
                        await send_file(
                            self.client,
                            entity=task.target_chat,
                            file=original_message.media,
                            caption=task.message_raw_text or task.message_text,
                            reply_to=task.to_topic_id,
                        )
                    else:
                        # Media not found, send text only
                        self.logger.warning(
                            f"Media not found for repeated message {task.original_id}, "
                            f"sending text only"
                        )
                        await send_message(
                            self.client,
                            entity=task.target_chat,
                            message=task.message_raw_text or task.message_text,
                            reply_to=task.to_topic_id,
                        )
                        
                except Exception as media_error:
                    self.logger.error(
                        f"Error getting media for repeated message {task.original_id}: {media_error}, "
                        f"sending text only"
                    )
                    # If failed to get media, send text only
                    await send_message(
                        self.client,
                        entity=task.target_chat,
                        message=task.message_raw_text or task.message_text,
                        reply_to=task.to_topic_id,
                    )
            else:
                # Send regular text message
                await send_message(
                    self.client,
                    entity=task.target_chat,
                    message=task.message_raw_text or task.message_text,
                    reply_to=task.to_topic_id,
                )
            
            new_repeat_count = task.repeat_count + 1
            
            self.logger.info(
                f"Repeated message {task.original_id} from chat {task.original_channel} "
                f"to chat {task.target_chat}, repeat #{new_repeat_count} (infinite mode)"
            )
            
            # Schedule next repeat with new randomized interval (infinite retries)
            randomized_interval = self._randomize_interval(task.base_repeat_interval)
            next_repeat_time = datetime.now() + timedelta(seconds=randomized_interval)
            
            # Update task for next repeat
            task.repeat_count = new_repeat_count
            task.repeat_interval = randomized_interval
            task.next_repeat_time = next_repeat_time
            
            self.logger.info(
                f"Scheduled next infinite repeat for message {task.original_id} "
                f"at {next_repeat_time} (interval: {randomized_interval}s, base: {task.base_repeat_interval}s)"
            )
                
        except Exception as e:
            self.logger.error(
                f"Error processing repeat for message {task.original_id}: {e}",
                exc_info=True
            )
            
            # In case of error, try again later with randomized interval
            retry_interval = self._randomize_interval(300)  # 5 minutes ± random
            next_retry_time = datetime.now() + timedelta(seconds=retry_interval)
            task.next_repeat_time = next_retry_time
            
            self.logger.info(f"Rescheduled failed repeat for {retry_interval}s")
    
    async def start_scheduler(self) -> None:
        """
        Start repeat scheduler
        """
        if self.running:
            self.logger.warning("Repeat scheduler is already running")
            return
        
        self.running = True
        self.logger.info(f"Starting infinite repeat scheduler with {self.check_interval}s interval")
        
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop_scheduler(self) -> None:
        """
        Stop repeat scheduler
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
        
        # Clear all repeat tasks
        self._repeat_tasks.clear()
        self._channel_tasks.clear()
    
    async def _scheduler_loop(self) -> None:
        """
        Main scheduler loop
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