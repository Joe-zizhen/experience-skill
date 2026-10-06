import httpx

from . import config


def send_webhook(url, payload):
    response = httpx.post(url, json=payload, timeout=config.WEBHOOK_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.status_code
