"""
Loads environment(.env)/config.yaml config
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from decouple import AutoConfig, Csv, RepositoryEnv

from telemirror.messagefilters import (
    CompositeMessageFilter,
    EmptyMessageFilter,
    MessageFilter,
    UrlMessageFilter,
)


class RepositoryMultilineEnv(RepositoryEnv):
    """
    Retrieves option keys from .env files with fall back to os.environ.
    Multiline values are supported with '' or "" quoted strings.
    """

    def __init__(self, source, encoding=...):
        self.data = {}
        multiline_key = None
        multiline_quote_sign = None
        with open(source, encoding=encoding) as file_:
            for line in file_:
                if multiline_key:
                    k = multiline_key
                    v = line.rstrip()
                    if v and v[-1] == multiline_quote_sign:
                        v = v[:-1]
                        multiline_key = None
                        multiline_quote_sign = None

                    self.data[k] += f"\n{v}"
                    continue

                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if len(v) >= 2 and (
                    (v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"')
                ):
                    v = v[1:-1]
                elif v and (
                    (v[0] == "'" and (len(v) < 2 or v[-1] != "'"))
                    or (v[0] == '"' and (len(v) < 2 or v[-1] != '"'))
                ):
                    multiline_key = k
                    multiline_quote_sign = v[0]
                    v = v[1:]

                self.data[k] = v

        if multiline_key:
            raise ValueError(
                f"Unterminated multiline env string value for key = {multiline_key}, "
                f"expected {multiline_quote_sign} at end"
            )


class Config(AutoConfig):
    def __init__(self, search_path=None):
        super().__init__(search_path)
        self.SUPPORTED[".env"] = RepositoryMultilineEnv


config = Config()

# telegram app id
API_ID: str = config("API_ID")
# telegram app hash
API_HASH: str = config("API_HASH")
# auth session string: can be obtain by run login.py
SESSION_STRING: str = config("SESSION_STRING")

# proxy settings
PROXY_TYPE: Optional[str] = config("PROXY_TYPE", default=None)  # socks4, socks5, http
PROXY_HOST: Optional[str] = config("PROXY_HOST", default=None)
PROXY_PORT: Optional[int] = config("PROXY_PORT", default=None, cast=lambda x: int(x) if x is not None else None)
PROXY_USERNAME: Optional[str] = config("PROXY_USERNAME", default=None)
PROXY_PASSWORD: Optional[str] = config("PROXY_PASSWORD", default=None)

def build_proxy_config():
    """Build proxy configuration for TelegramClient"""
    if not PROXY_TYPE or not PROXY_HOST or not PROXY_PORT:
        return None
    
    # Telethon supports different proxy formats
    # Using the new dict format (recommended)
    proxy_config = {
        'proxy_type': PROXY_TYPE.lower(),  # 'socks4', 'socks5', 'http'
        'addr': PROXY_HOST,
        'port': PROXY_PORT,
        'rdns': True  # use remote DNS resolution
    }
    
    if PROXY_USERNAME and PROXY_PASSWORD:
        proxy_config['username'] = PROXY_USERNAME
        proxy_config['password'] = PROXY_PASSWORD
    
    return proxy_config

LOG_LEVEL: str = config("LOG_LEVEL", default="INFO").upper()

# Application local host, defaults to 0.0.0.0
HOST: str = config("HOST", default="0.0.0.0")
# Application local port, defaults to 8000
PORT: int = config("PORT", default=8000, cast=int)

###############Channel mirroring config#################

YAML_CONFIG_ENV: Optional[str] = config("YAML_CONFIG_ENV", default=None)
YAML_CONFIG_FILE = "./.configs/mirror.config.yml"

# source and target chats mapping
CHAT_MAPPING: Dict[int, Dict[int, List["DirectionConfig"]]] = {}


@dataclass(frozen=True)
class DirectionConfig:
    filters: MessageFilter
    from_topic_id: Optional[int] = None
    to_topic_id: Optional[int] = None
    mode: Literal["copy", "forward"] = "forward"  # Changed default from "copy" to "forward"
    repeat_interval: Optional[int] = None  # repeat interval in seconds
    drop_author: bool = False              # hide forward author (can help with premium emojis)
    preserve_premium_emojis: bool = True   # preserve premium emojis during forwarding

    def __repr__(self) -> str:
        return (
            f"mode: {self.mode}, "
            f"{f'from_topic_id: {self.from_topic_id}, ' if self.from_topic_id else ''}"
            f"{f'to_topic_id: {self.to_topic_id}, ' if self.to_topic_id else ''}"
            f"{f'repeat_interval: {self.repeat_interval}s, ' if self.repeat_interval else ''}"
            f"drop_author: {self.drop_author}, "
            f"preserve_premium_emojis: {self.preserve_premium_emojis}, "
            f"filters: {self.filters}"
        )


# Load mirror config from config.yml
# otherwise from .env or environment
if YAML_CONFIG_ENV or os.path.exists(YAML_CONFIG_FILE):
    from importlib import import_module
    from types import ModuleType

    import yaml

    filters_module: ModuleType = import_module("telemirror.messagefilters")

    yaml_config: dict = None

    if YAML_CONFIG_ENV:
        yaml_config = yaml.load(
            YAML_CONFIG_ENV.replace("\\n", "\n"), Loader=yaml.FullLoader
        )
    else:
        with open(YAML_CONFIG_FILE, encoding="utf8") as file:
            yaml_config = yaml.load(file, Loader=yaml.FullLoader)

    def build_filters(
        filter_config: Optional[dict], default: MessageFilter
    ) -> MessageFilter:
        if not filter_config:
            return default

        filters: List[MessageFilter] = []
        for filter in filter_config:
            filter_name, filter_args = (
                list(filter.items())[0] if isinstance(filter, dict) else (filter, {})
            )
            filter_class = getattr(filters_module, filter_name)
            filters.append(filter_class(**filter_args))

        return CompositeMessageFilter(filters) if (len(filters) > 1) else filters[0]

    default_filters = build_filters(
        yaml_config.get("filters", None), EmptyMessageFilter()
    )

    for direction in yaml_config["directions"]:
        sources: list = direction["from"]
        targets: list = direction["to"]

        for source in sources:
            source_topic_id = None
            if isinstance(source, str):
                if "#" in source:
                    source, source_topic_id = map(int, source.split("#"))
                else:
                    source = int(source)

            for target in targets:
                target_topic_id = None
                if isinstance(target, str):
                    if "#" in target:
                        target, target_topic_id = map(int, target.split("#"))
                    else:
                        target = int(target)

                CHAT_MAPPING.setdefault(source, {}).setdefault(target, []).append(
                    DirectionConfig(
                        filters=build_filters(
                            direction.get("filters", None), default_filters
                        ),
                        from_topic_id=source_topic_id,
                        to_topic_id=target_topic_id,
                        mode=direction.get("mode", yaml_config.get("mode", "forward")),
                        repeat_interval=direction.get(
                            "repeat_interval", yaml_config.get("repeat_interval", None)
                        ),
                        drop_author=direction.get(
                            "drop_author", yaml_config.get("drop_author", False)
                        ),
                        preserve_premium_emojis=direction.get(
                            "preserve_premium_emojis", yaml_config.get("preserve_premium_emojis", True)
                        ),
                    )
                )

else:
    # Mirror config thru environment vars
    from functools import partial

    def build_mapping_from_env(
        filters: MessageFilter, 
        repeat_interval: Optional[int],
        mode: Literal["copy", "forward"],
        env_str: str
    ) -> Dict[int, Dict[int, List[DirectionConfig]]]:
        mapping: Dict[int, Dict[int, List[DirectionConfig]]] = {}

        if not env_str:
            return mapping

        import re

        matches = re.findall(
            r"\[?((?:-?\d+(?:#\d+)?,?)+):((?:-?\d+(?:#\d+)?,?)+)\]?",
            env_str,
            re.MULTILINE,
        )

        for sources, targets in matches:
            for source in sources.split(","):
                source = source.strip()
                if not source:
                    continue
                    
                source_topic_id = None
                if "#" in source:
                    source, source_topic_id = map(int, source.split("#"))
                else:
                    source = int(source)

                for target in targets.split(","):
                    target = target.strip()
                    if not target:
                        continue
                        
                    target_topic_id = None
                    if "#" in target:
                        target, target_topic_id = map(int, target.split("#"))
                    else:
                        target = int(target)

                    mapping.setdefault(source, {}).setdefault(target, []).append(
                        DirectionConfig(
                            filters=filters,
                            from_topic_id=source_topic_id,
                            to_topic_id=target_topic_id,
                            mode=mode,
                            repeat_interval=repeat_interval,
                            drop_author=False,  # Default False for env configuration
                            preserve_premium_emojis=True, # Default True for env configuration
                        )
                    )

        return mapping

    # remove urls from messages
    REMOVE_URLS: bool = config("REMOVE_URLS", cast=bool, default=False)
    # remove urls whitelist
    REMOVE_URLS_WHITELIST: set = config(
        "REMOVE_URLS_WL", cast=Csv(post_process=set), default=""
    )
    # remove urls only this URLs
    REMOVE_URLS_LIST: set = config(
        "REMOVE_URLS_LIST", cast=Csv(post_process=set), default=""
    )
    
    # repeat settings
    REPEAT_INTERVAL: Optional[int] = config("REPEAT_INTERVAL", cast=int, default=None)
    
    # mode setting - forward or copy
    MODE: Literal["copy", "forward"] = config("MODE", default="forward")

    if REMOVE_URLS:
        message_filter = UrlMessageFilter(
            blacklist=REMOVE_URLS_LIST, whitelist=REMOVE_URLS_WHITELIST
        )
    else:
        message_filter = EmptyMessageFilter()

    cast_env_chat_mapping = partial(
        build_mapping_from_env,
        message_filter,
        REPEAT_INTERVAL,
        MODE,
    )

    CHAT_MAPPING = config("CHAT_MAPPING", cast=cast_env_chat_mapping, default="")

    if not CHAT_MAPPING:
        raise Exception(
            "The chat mapping configuration is incorrect. "
            "Please provide valid non-empty CHAT_MAPPING environment variable."
        )
