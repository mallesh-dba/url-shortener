import asyncio
import logging

from url_shortener.analytics import run_worker


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
