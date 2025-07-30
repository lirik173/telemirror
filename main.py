import logging

from telemirror.mirroring import Telemirror


async def serve_health_endpoint(host: str, port: int) -> None:
    """
    Start http health endpoint at /.

    Some PaaS providers require a health endpoint to verify that the service has started successfully.
    """
    from aiohttp import web

    async def health(_):
        return web.Response(status=204)

    app = web.Application()
    app.add_routes([web.get("/", health)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()


def configure_logging(logger_name: str, log_level: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    if not logger.handlers:
        import sys

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)-5s %(asctime)s [%(filename)s:%(lineno)d]:%(name)s: %(message)s"
            )
        )

        logger.addHandler(handler)

    return logger


async def run_telemirror(
    api_id: str,
    api_hash: str,
    session_string: str,
    chat_mapping: dict,
    logger: logging.Logger,
    host: str,
    port: int,
    proxy=None,
):
    await serve_health_endpoint(host=host, port=port)

    telemirror = Telemirror(
        api_id=api_id,
        api_hash=api_hash,
        session_string=session_string,
        chat_mapping=chat_mapping,
        logger=logger,
        proxy=proxy,
    )
    await telemirror.run()


def main():
    import asyncio
    import sys

    from config import (
        API_HASH,
        API_ID,
        CHAT_MAPPING,
        HOST,
        LOG_LEVEL,
        PORT,
        SESSION_STRING,
        build_proxy_config,
    )

    if sys.platform == "win32":
        # Set event loop policy for Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        import uvloop
        uvloop.install()

    proxy_config = build_proxy_config()

    asyncio.run(
        run_telemirror(
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING,
            chat_mapping=CHAT_MAPPING,
            logger=configure_logging("telemirror", LOG_LEVEL),
            host=HOST,
            port=PORT,
            proxy=proxy_config,
        )
    )


if __name__ == "__main__":
    main()
