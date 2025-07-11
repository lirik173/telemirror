from abc import abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, NamedTuple, Optional, Protocol

from psycopg import AsyncCursor, errors
from psycopg.rows import class_row
from psycopg_pool import AsyncConnectionPool

from .misc.lrucache import LRUCache


class MirrorMessage(NamedTuple):
    """
    Mirror message class contains id message mappings:

    `original_message_id` <-> `mirror_message_id`

    Args:
        original_id (`int`): Original message ID
        original_channel (`int`): Source channel ID
        mirror_id (`int`): Mirror message ID
        mirror_channel (`int`): Mirror channel ID
    """

    original_id: int
    original_channel: int
    mirror_id: int
    mirror_channel: int


class RepeatedMessage(NamedTuple):
    """
    Repeated message class contains message repeat info:

    Args:
        id (`Optional[int]`): Database ID (None for new records)
        original_id (`int`): Original message ID
        original_channel (`int`): Source channel ID
        message_data (`Dict[str, Any]`): Serialized message data
        target_configs (`Dict[str, Any]`): Target configuration data
        next_repeat_time (`datetime`): Next repeat time
        repeat_count (`int`): Current repeat count
        max_repeats (`Optional[int]`): Maximum number of repeats
        created_at (`Optional[datetime]`): Creation timestamp
    """

    id: Optional[int]
    original_id: int
    original_channel: int
    message_data: Dict[str, Any]
    target_configs: Dict[str, Any]
    next_repeat_time: datetime
    repeat_count: int
    max_repeats: Optional[int]
    created_at: Optional[datetime] = None


class Database(Protocol):
    """
    Base database class

    Provides two user functions that work messages mapping data:
    - Add new `MirrorMessage` object to database
    - Get `MirrorMessage` object from database by original message ID
    """

    @abstractmethod
    async def _async__init__(self: "Database") -> "Database":
        """Async initializer"""
        raise NotImplementedError

    def __await__(self):
        return self._async__init__().__await__()

    @abstractmethod
    async def insert(self: "Database", entity: MirrorMessage) -> None:
        """Inserts `MirrorMessage` object into database

        Args:
            entity (`MirrorMessage`): `MirrorMessage` object
        """
        raise NotImplementedError

    @abstractmethod
    async def insert_batch(self: "Database", entity: List[MirrorMessage]) -> None:
        """Inserts `MirrorMessage` objects into database

        Args:
            entity (`List[MirrorMessage]`): List of `MirrorMessage` objects
        """
        raise NotImplementedError

    @abstractmethod
    async def get_messages(
        self: "Database", original_id: int, original_channel: int
    ) -> List[MirrorMessage]:
        """
        Finds `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID

        Returns:
            List[MirrorMessage]
        """
        raise NotImplementedError

    @abstractmethod
    async def get_messages_batch(
        self: "Database", original_ids: List[int], original_channel: int
    ) -> List[MirrorMessage]:
        """
        Finds `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_ids (`List[int]`): Original message IDs
            original_channel (`int`): Source channel ID

        Returns:
            List[MirrorMessage]
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_messages(
        self: "Database", original_id: int, original_channel: int
    ) -> None:
        """
        Deletes `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_messages_batch(
        self: "Database", original_ids: List[int], original_channel: int
    ) -> None:
        """
        Deletes `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_ids (`List[int]`): Original message IDs
            original_channel (`int`): Source channel ID
        """
        raise NotImplementedError

    # Repeated messages methods
    @abstractmethod
    async def insert_repeated_message(self: "Database", entity: RepeatedMessage) -> int:
        """Inserts `RepeatedMessage` object into database

        Args:
            entity (`RepeatedMessage`): `RepeatedMessage` object

        Returns:
            int: Inserted record ID
        """
        raise NotImplementedError

    @abstractmethod
    async def get_pending_repeated_messages(self: "Database") -> List[RepeatedMessage]:
        """Gets all repeated messages that are due for processing

        Returns:
            List[RepeatedMessage]: List of pending repeated messages
        """
        raise NotImplementedError

    @abstractmethod
    async def update_repeated_message(self: "Database", entity: RepeatedMessage) -> None:
        """Updates `RepeatedMessage` object in database

        Args:
            entity (`RepeatedMessage`): `RepeatedMessage` object to update
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_repeated_message(self: "Database", repeated_id: int) -> None:
        """Deletes `RepeatedMessage` object from database

        Args:
            repeated_id (`int`): Repeated message ID
        """
        raise NotImplementedError

    @abstractmethod
    async def get_active_repeated_messages_for_channel(
        self: "Database", 
        original_channel: int, 
        target_chat: int
    ) -> List[RepeatedMessage]:
        """Gets all active repeated messages for specific channel and target chat

        Args:
            original_channel (`int`): Original channel ID
            target_chat (`int`): Target chat ID

        Returns:
            List[RepeatedMessage]: List of active repeated messages
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.__class__.__name__


class InMemoryDatabase(Database):
    """
    In-memory database class messages mapping implementation.

    Provides two user functions that work with 'binding_id' table:
    - Add new `MirrorMessage` object to database
    - Get `MirrorMessage` object from database by original message ID
    """

    MAX_CAPACITY = 100

    def __init__(
        self: "InMemoryDatabase", max_capacity: int = MAX_CAPACITY
    ) -> "InMemoryDatabase":
        self.__storage = LRUCache[str, List[MirrorMessage]](capacity=max_capacity)
        self.__repeated_storage: Dict[int, RepeatedMessage] = {}
        self.__repeated_id_counter = 0

    async def _async__init__(self: "InMemoryDatabase") -> "InMemoryDatabase":
        return self

    async def insert(self: "InMemoryDatabase", entity: MirrorMessage) -> None:
        """Inserts `MirrorMessage` object into database

        Args:
            entity (`MirrorMessage`): `MirrorMessage` object
        """
        self.__storage.setdefault(
            self.__build_message_key(entity.original_id, entity.original_channel), []
        ).append(entity)

    async def insert_batch(
        self: "InMemoryDatabase", entity: List[MirrorMessage]
    ) -> None:
        """Inserts `MirrorMessage` objects into database

        Args:
            entity (`List[MirrorMessage]`): List of `MirrorMessage` objects
        """
        for e in entity:
            self.__storage.setdefault(
                self.__build_message_key(e.original_id, e.original_channel), []
            ).append(e)

    async def get_messages(
        self: "InMemoryDatabase", original_id: int, original_channel: int
    ) -> List[MirrorMessage]:
        """
        Finds `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID

        Returns:
            List[MirrorMessage]
        """
        return self.__storage.get(
            self.__build_message_key(original_id, original_channel), []
        )

    async def get_messages_batch(
        self: "InMemoryDatabase", original_ids: List[int], original_channel: int
    ) -> List[MirrorMessage]:
        """
        Finds `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_ids (`List[int]`): Original message IDs
            original_channel (`int`): Source channel ID

        Returns:
            List[MirrorMessage]
        """
        return [
            msg
            for idx in original_ids
            for msg in self.__storage.get(
                self.__build_message_key(idx, original_channel), []
            )
        ]

    async def delete_messages(
        self: "InMemoryDatabase", original_id: int, original_channel: int
    ) -> None:
        """
        Deletes `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID
        """
        self.__storage.pop(
            self.__build_message_key(original_id, original_channel), None
        )

    async def delete_messages_batch(
        self: "InMemoryDatabase", original_ids: List[int], original_channel: int
    ) -> None:
        """
        Deletes `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_ids (`List[int]`): Original message IDs
            original_channel (`int`): Source channel ID
        """
        for idx in original_ids:
            self.__storage.pop(self.__build_message_key(idx, original_channel), None)

    def __build_message_key(
        self: "InMemoryDatabase", original_id: int, original_channel: int
    ) -> str:
        """
        Builds message key from `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID

        Returns:
            str
        """
        return f"{original_channel}:{original_id}"

    # Repeated messages methods
    async def insert_repeated_message(self: "InMemoryDatabase", entity: RepeatedMessage) -> int:
        """Inserts `RepeatedMessage` object into database

        Args:
            entity (`RepeatedMessage`): `RepeatedMessage` object

        Returns:
            int: Inserted record ID
        """
        self.__repeated_id_counter += 1
        repeated_id = self.__repeated_id_counter
        
        # Create new entity with assigned ID
        new_entity = entity._replace(id=repeated_id, created_at=datetime.now())
        self.__repeated_storage[repeated_id] = new_entity
        
        return repeated_id

    async def get_pending_repeated_messages(self: "InMemoryDatabase") -> List[RepeatedMessage]:
        """Gets all repeated messages that are due for processing

        Returns:
            List[RepeatedMessage]: List of pending repeated messages
        """
        now = datetime.now()
        return [
            msg for msg in self.__repeated_storage.values()
            if msg.next_repeat_time <= now
        ]

    async def update_repeated_message(self: "InMemoryDatabase", entity: RepeatedMessage) -> None:
        """Updates `RepeatedMessage` object in database

        Args:
            entity (`RepeatedMessage`): `RepeatedMessage` object to update
        """
        if entity.id and entity.id in self.__repeated_storage:
            self.__repeated_storage[entity.id] = entity

    async def delete_repeated_message(self: "InMemoryDatabase", repeated_id: int) -> None:
        """Deletes `RepeatedMessage` object from database

        Args:
            repeated_id (`int`): Repeated message ID
        """
        if repeated_id in self.__repeated_storage:
            del self.__repeated_storage[repeated_id]

    async def get_active_repeated_messages_for_channel(
        self: "InMemoryDatabase", 
        original_channel: int, 
        target_chat: int
    ) -> List[RepeatedMessage]:
        """Gets all active repeated messages for specific channel and target chat

        Args:
            original_channel (`int`): Original channel ID
            target_chat (`int`): Target chat ID

        Returns:
            List[RepeatedMessage]: List of active repeated messages
        """
        result = []
        for msg in self.__repeated_storage.values():
            if (msg.original_channel == original_channel and 
                msg.target_configs.get("target_chat") == target_chat):
                result.append(msg)
        return result


class PostgresDatabase(Database):
    """
    Postgres database messages mapping implementation.

    Binding database table:

    ```
    create table binding_id (id serial primary key not null,
                original_id bigint not null,
                original_channel bigint not null,
                mirror_id bigint not null,
                mirror_channel bigint not null)
    ```

    Provides two user functions that work with 'binding_id' table:
    - Add new `MirrorMessage` object to database
    - Get `MirrorMessage` object from database by original message ID

    Args:
        connection_string (`str`): Postgres connection URL
        min_conn (`int`, optional): Min amount of connections. Defaults to MIN_CONN (1).
        max_conn (`int`, optional): Max amount of connections. Defaults to MAX_CONN (10).
    """

    MIN_CONN = 1
    MAX_CONN = 10

    def __init__(
        self,
        connection_string: str,
        min_conn: int = MIN_CONN,
        max_conn: int = MAX_CONN,
        **kwargs: Any,
    ) -> "PostgresDatabase":
        self.__conn_info = connection_string
        self.__min_conn = min_conn
        self.__max_conn = max_conn
        self.__kwargs = kwargs

    async def _async__init__(self: "PostgresDatabase") -> "PostgresDatabase":
        self.connection_pool = AsyncConnectionPool(
            conninfo=self.__conn_info,
            min_size=self.__min_conn,
            max_size=self.__max_conn,
            open=False,
            **self.__kwargs,
        )
        await self.connection_pool.open()
        await self.__create_tables_if_not_exists()
        return self

    async def insert(self: "PostgresDatabase", entity: MirrorMessage) -> None:
        """Inserts `MirrorMessage` object into database

        Args:
            entity (`MirrorMessage`): `MirrorMessage` object
        """
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO binding_id (original_id, original_channel, mirror_id, mirror_channel)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    entity.original_id,
                    entity.original_channel,
                    entity.mirror_id,
                    entity.mirror_channel,
                ),
            )

    async def insert_batch(
        self: "PostgresDatabase", entity: List[MirrorMessage]
    ) -> None:
        """Inserts `MirrorMessage` objects into database

        Args:
            entity (`List[MirrorMessage]`): List of `MirrorMessage` objects
        """
        async with self.__pg_cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO binding_id (original_id, original_channel, mirror_id, mirror_channel)
                VALUES (%s, %s, %s, %s)
                """,
                entity,
            )

    async def get_messages(
        self: "PostgresDatabase", original_id: int, original_channel: int
    ) -> List[MirrorMessage]:
        """
        Finds `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID

        Returns:
            List[MirrorMessage]
        """
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(MirrorMessage)
            await cursor.execute(
                """
                SELECT original_id, original_channel, mirror_id, mirror_channel
                FROM binding_id
                WHERE original_channel = %s
                AND original_id = %s
                """,
                (
                    original_channel,
                    original_id,
                ),
            )
            rows = await cursor.fetchall()
        return rows

    async def get_messages_batch(
        self: "PostgresDatabase", original_ids: List[int], original_channel: int
    ) -> List[MirrorMessage]:
        """
        Finds `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_ids (`List[int]`): Original message IDs
            original_channel (`int`): Source channel ID

        Returns:
            List[MirrorMessage]
        """
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(MirrorMessage)
            await cursor.execute(
                """
                SELECT original_id, original_channel, mirror_id, mirror_channel
                FROM binding_id
                WHERE original_channel = %s
                AND original_id = ANY(%s)
                """,
                (
                    original_channel,
                    original_ids,
                ),
            )
            rows = await cursor.fetchall()
        return rows

    async def delete_messages(
        self: "PostgresDatabase", original_id: int, original_channel: int
    ) -> None:
        """
        Deletes `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_id (`int`): Original message ID
            original_channel (`int`): Source channel ID
        """
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                DELETE FROM binding_id
                WHERE original_channel = %s
                AND original_id = %s
                """,
                (
                    original_channel,
                    original_id,
                ),
            )

    async def delete_messages_batch(
        self: "PostgresDatabase", original_ids: List[int], original_channel: int
    ) -> None:
        """
        Deletes `MirrorMessage` objects with `original_id` and `original_channel` values

        Args:
            original_ids (`List[int]`): Original message IDs
            original_channel (`int`): Source channel ID
        """
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                DELETE FROM binding_id
                WHERE original_channel = %s
                AND original_id = ANY(%s)
                """,
                (
                    original_channel,
                    original_ids,
                ),
            )

    async def __create_tables_if_not_exists(self: "PostgresDatabase"):
        """Create tables if not exists"""
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS binding_id(   
                    id serial primary key not null,
                    original_id bigint not null,
                    original_channel bigint not null,
                    mirror_id bigint not null,
                    mirror_channel bigint not null
                );

                CREATE INDEX IF NOT EXISTS binding_id_original_idx 
                ON binding_id (original_channel, original_id);

                CREATE TABLE IF NOT EXISTS repeated_messages(
                    id serial primary key not null,
                    original_id bigint not null,
                    original_channel bigint not null,
                    message_data jsonb not null,
                    target_configs jsonb not null,
                    next_repeat_time timestamp not null,
                    repeat_count integer default 0,
                    max_repeats integer,
                    created_at timestamp default now()
                );

                CREATE INDEX IF NOT EXISTS repeated_messages_next_time_idx 
                ON repeated_messages (next_repeat_time);
                
                CREATE INDEX IF NOT EXISTS repeated_messages_channel_target_idx 
                ON repeated_messages (original_channel, (target_configs->>'target_chat'));
                """
            )

    # Repeated messages methods
    async def insert_repeated_message(self: "PostgresDatabase", entity: RepeatedMessage) -> int:
        """Inserts `RepeatedMessage` object into database

        Args:
            entity (`RepeatedMessage`): `RepeatedMessage` object

        Returns:
            int: Inserted record ID
        """
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO repeated_messages 
                (original_id, original_channel, message_data, target_configs, 
                 next_repeat_time, repeat_count, max_repeats)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    entity.original_id,
                    entity.original_channel,
                    entity.message_data,
                    entity.target_configs,
                    entity.next_repeat_time,
                    entity.repeat_count,
                    entity.max_repeats,
                ),
            )
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_pending_repeated_messages(self: "PostgresDatabase") -> List[RepeatedMessage]:
        """Gets all repeated messages that are due for processing

        Returns:
            List[RepeatedMessage]: List of pending repeated messages
        """
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(RepeatedMessage)
            await cursor.execute(
                """
                SELECT id, original_id, original_channel, message_data, target_configs,
                       next_repeat_time, repeat_count, max_repeats, created_at
                FROM repeated_messages
                WHERE next_repeat_time <= NOW()
                ORDER BY next_repeat_time ASC
                """,
            )
            rows = await cursor.fetchall()
        return rows

    async def update_repeated_message(self: "PostgresDatabase", entity: RepeatedMessage) -> None:
        """Updates `RepeatedMessage` object in database

        Args:
            entity (`RepeatedMessage`): `RepeatedMessage` object to update
        """
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                UPDATE repeated_messages 
                SET message_data = %s, target_configs = %s, next_repeat_time = %s, 
                    repeat_count = %s, max_repeats = %s
                WHERE id = %s
                """,
                (
                    entity.message_data,
                    entity.target_configs,
                    entity.next_repeat_time,
                    entity.repeat_count,
                    entity.max_repeats,
                    entity.id,
                ),
            )

    async def delete_repeated_message(self: "PostgresDatabase", repeated_id: int) -> None:
        """Deletes `RepeatedMessage` object from database

        Args:
            repeated_id (`int`): Repeated message ID
        """
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                DELETE FROM repeated_messages WHERE id = %s
                """,
                (repeated_id,),
            )

    async def get_active_repeated_messages_for_channel(
        self: "PostgresDatabase", 
        original_channel: int, 
        target_chat: int
    ) -> List[RepeatedMessage]:
        """Gets all active repeated messages for specific channel and target chat

        Args:
            original_channel (`int`): Original channel ID
            target_chat (`int`): Target chat ID

        Returns:
            List[RepeatedMessage]: List of active repeated messages
        """
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(RepeatedMessage)
            await cursor.execute(
                """
                SELECT id, original_id, original_channel, message_data, target_configs,
                       next_repeat_time, repeat_count, max_repeats, created_at
                FROM repeated_messages
                WHERE original_channel = %s 
                AND target_configs->>'target_chat' = %s
                """,
                (
                    original_channel,
                    str(target_chat),
                ),
            )
            rows = await cursor.fetchall()
        return rows

    @asynccontextmanager
    async def __pg_cursor(self: "PostgresDatabase") -> AsyncIterator[AsyncCursor[Any]]:
        """
        Gets connection from pool and yields cursor within current context

        Yields:
            (`psycopg.AsyncCursor`): Cursor
        """
        async with self.connection_pool.connection() as con:
            try:
                async with con.cursor() as cur:
                    yield cur
            except errors.OperationalError as e:
                # If we get an operational error check the pool
                await self.connection_pool.check()
                raise e
            except errors.DatabaseError as e:
                if con is not None:
                    await con.rollback()
                raise e