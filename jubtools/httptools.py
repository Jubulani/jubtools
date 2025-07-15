import csv
import logging
from enum import Enum
from typing import Any

import httpx

from jubtools import misctools

logger = logging.getLogger(__name__)


class ResponseFormat(str, Enum):
    BYTES = "BYTES"
    CSV = "CSV"
    JSON = "JSON"


async def get(
    url: str, params: dict[str, Any] = {}, response_format: ResponseFormat = ResponseFormat.JSON
):
    logger.info(f"HTTP GET {url} (params {params})")
    try:
        status = None
        reason = None
        with misctools.Timer() as timer:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                status = resp.status_code
                reason = resp.reason_phrase
                resp.raise_for_status()

            match response_format:
                case ResponseFormat.BYTES:
                    logger.info(f"Response text: {resp.text}")
                    return resp.text
                case ResponseFormat.CSV:
                    return list(csv.DictReader(resp.text.splitlines(), delimiter=";"))
                case ResponseFormat.JSON:
                    logger.info(f"Response JSON: {resp.json()}")
                    return resp.json()
    finally:
        logger.info(f"HTTP GET {url} {status} {reason} ({timer.elapsed:.2f}ms)")
