#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Simple Bot to fetch video and upload them to telegram.
Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import base64
import glob
import logging
import os
import sys
import urllib
import uuid

import pycountry as pycountry
import tenacity
import youtube_dl
from telegram.ext import Updater, CommandHandler, run_async

# Name of the environment variable which defines the bot token
TOKEN_ENV_NAME = 'VIDEO_DL_BOT_TOKEN'

# Default download location
VIDEO_DL_DIR = '/tmp/'

# Default video files prefix
VIDEO_FILE_PREFIX = 'tgbot_'

# File suffix to indicate it's finished
FINISHED_PATTERN = 'tgok'

# Proxy Web service which provide useable open proxy addresses
PROXY_WS_HOST = '127.0.0.1'
PROXY_WS_PORT = 5000

UPLOAD_TIMEOUT = 999

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def show_help(bot, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Usage /dl [url]')


@run_async
def download(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    url = args[0]
    file_prefix = VIDEO_DL_DIR + VIDEO_FILE_PREFIX
    encoded_chat_id = bytes(str(update.message.chat_id), 'ascii')
    video_file = file_prefix + base64.urlsafe_b64encode(encoded_chat_id).decode('ascii') \
                 + '_' \
                 + str(uuid.uuid4()) \
                 + '.mp4'
    try:
        ydl_opts = ytdl_config(video_file, dl_proxy='')
        ytdl_download(url, video_file=video_file, ydl_opts=ydl_opts)
    except Exception as e:
        logger.fatal('Download failed: %s, retrying with proxy ...', e)
        ytdl_with_proxy(url, video_file)


@run_async
def proxy(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    country = pycountry.countries.lookup(args[0]) or 'FR'
    result = urllib.request.urlopen('http://'
                                    + PROXY_WS_HOST
                                    + ':' + str(PROXY_WS_PORT)
                                    + '/update?country=' + country.alpha_2).read()
    bot.sendMessage(chat_id=update.message.chat_id, text=str(result))


def get_proxy_country_code():
    return urllib.request.urlopen('http://'
                                  + PROXY_WS_HOST
                                  + ':' + str(PROXY_WS_PORT)
                                  + '/').read()


@tenacity.retry
def ytdl_with_proxy(url, video_file):
    country_code = get_proxy_country_code()
    logger.info('New proxy selected: %s', country_code)
    ydl_opts = ytdl_config(video_file, dl_proxy=country_code)
    ytdl_download(url, video_file, ydl_opts)


def ytdl_download(url, video_file, ydl_opts):
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        logger.info('Downloading video from "%s"', url)
        ydl.extract_info(url, download=True)
        logger.info('Video successfully downloaded to "%s"', video_file)
        final_name = get_finished_name(video_file)
        os.rename(video_file, final_name)
        logger.info('Video file renamed to "%s"', final_name)


def ytdl_config(video_file, dl_proxy=''):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': VIDEO_DL_DIR + '%(id)s',
        # Workaround for https://github.com/rg3/youtube-dl/issues/11348
        'postprocessor_args': ['-bsf:a', 'aac_adtstoasc'],
        'postprocessors': [{
            'key': 'ExecAfterDownload',
            # see https://ffmpeg.org/ffmpeg-filters.html#scale
            # for explanation on -2 choice for scale filter
            'exec_cmd': "ffmpeg -i {} -y -vcodec libx264 -crf 23 -vprofile baseline "
                        "-b:v 500k -maxrate 500k -bufsize 800k -vf scale=-2:480 -level 3.0 "
                        "-threads 0 -pix_fmt yuv420p -codec:a aac -ac 2 -strict experimental "
                        "-ab 128k -movflags +faststart " + video_file
        }],
        'addmetadata': True,
        'xattrs': True,
        'proxy': dl_proxy,
        'geo_bypass': True,
        'continuedl': True,
        'fragment_retries': 10,
        'verbose': True
    }

    return ydl_opts


def get_finished_name(filename):
    name, ext = os.path.splitext(filename)
    return "{name}_{ok}{ext}".format(name=name, ok=FINISHED_PATTERN, ext=ext)


def send_file(bot, job):
    # check if there is files to send
    path = VIDEO_DL_DIR + VIDEO_FILE_PREFIX + '*_' + FINISHED_PATTERN + '*.mp4'
    logger.debug('Checking for new files to upload from %s', path)
    for file in glob.glob(path):
        encoded_chat = file.split('_')[1]
        chat = int(base64.b64decode(encoded_chat).decode('ascii'))
        try:
            logger.info('Uploading "%s" to chat "%s"', file, chat)
            bot.sendVideo(chat_id=chat, video=open(file, 'rb'), timeout=UPLOAD_TIMEOUT)
            logger.info('File "%s" sent successfully !', file)
            clean(file)
        except Exception as e:
            logger.error('Error "%s" sending file "%s"', e, file)


def clean(file):
    try:
        os.remove(file)
    except OSError as e:
        logger.error('Error "%s" removing file "%s"', e, file)


def error(bot, update, err):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, err)


def main():
    # Create the Updater and pass it your bot's token.
    token = os.environ.get(TOKEN_ENV_NAME)
    if token is None:
        logger.fatal('Can\'t find bot token in environment variable "%s"', TOKEN_ENV_NAME)
        return 1

    updater = Updater(token, workers=32)

    # Get the job queues, to send files every 30s if needed
    jobs = updater.job_queue
    jobs.run_repeating(send_file, interval=15, first=0)
    logger.info('Finished Job queue initialization')

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Map commands
    dp.add_handler(CommandHandler("help", show_help))
    dp.add_handler(CommandHandler("dl", download, pass_args=True))
    dp.add_handler(CommandHandler("proxy", proxy, pass_args=True))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Block until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
