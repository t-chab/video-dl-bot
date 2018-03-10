#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Micro service to fetch a proxy IP matching given country code
"""

import asyncio
import logging
import os

from proxybroker import Broker
from quart import Quart, request

# Name of the environment variable which defines the default proxy country code
PROXY_COUNTRY_ENV_NAME = 'PROXY_COUNTRY'

# Default country code if not specified by environment variable
DEFAULT_COUNTRY_CODE = 'FR'

# Global var to store fetched proxy value
GEO_BLOCK_PROXY = ['']

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

app = Quart(__name__)


async def update_proxy(proxies):
    while True:
        proxy = await proxies.get()
        if proxy is None:
            break
        GEO_BLOCK_PROXY[0] = proxy.host + ':' + str(proxy.port)
        logger.info('Found following proxy : %s', GEO_BLOCK_PROXY[0])


def fill_proxy(country_code):
    loop = asyncio.get_event_loop()
    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)
    asyncio.gather(
        broker.find(types=['HTTP', 'HTTPS', 'CONNECT:80'],
                    countries=[country_code], limit=1),
        update_proxy(proxies))


@app.route('/')
def get_proxy():
    if not GEO_BLOCK_PROXY[0]:
        logger.info('Waiting for application to init ...')
    return GEO_BLOCK_PROXY[0]


@app.route('/update')
async def fetch_new_proxy():
    country = request.args.get('country') or get_country_code()
    fill_proxy(country)
    return 'Proxy address will be updated soon with country code ' + country


def get_country_code():
    return os.environ.get(PROXY_COUNTRY_ENV_NAME) or DEFAULT_COUNTRY_CODE


if __name__ == '__main__':
    code = get_country_code()
    logger.info('Proxy list initialization, using country_code=%s', code)
    fill_proxy(code)
    app.run()
