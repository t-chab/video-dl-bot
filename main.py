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
import urllib.request
import uuid

import pycountry as pycountry
import validators
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
    update.message.reply_text("""Available commands : 
                                 - Download video : /dl [url]
                                 - Download video using a proxy to bypass geo-restriction : /dlp [url]
                                 - Update proxy : /proxy [country_code]
                                 - Make gif from video : /gif [url]
                                 - Get mp3 from video : /mp3 [url]
                                 """)


@run_async
def download(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    telegram_chat = update.message.chat_id
    url = args[0]
    download_url(bot, telegram_chat, url)


@run_async
def download_with_proxy(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    telegram_chat = update.message.chat_id
    url = args[0]
    download_url(bot, telegram_chat, url, with_proxy=True)


@run_async
def gif(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    telegram_chat = update.message.chat_id
    url = args[0]
    download_url(bot, telegram_chat, url, output_gif=True)


@run_async
def mp3(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    telegram_chat = update.message.chat_id
    url = args[0]
    download_url(bot, telegram_chat, url, output_type='mp3')


@run_async
def proxy(bot, update, args):
    logger.info('%s - args: "%s"', sys._getframe().f_code.co_name, args)
    country = pycountry.countries.lookup(args[0]) or 'FR'
    request = urllib.request.urlopen('http://'
                                     + PROXY_WS_HOST
                                     + ':' + str(PROXY_WS_PORT)
                                     + '/update?country=' + country.alpha_2)
    new_proxy = request.read().decode(request.headers.get_content_charset())
    bot.sendMessage(chat_id=update.message.chat_id, text=new_proxy)


def download_url(bot, telegram_chat, url, output_gif=False, output_type='mp4', with_proxy=False):
    if not validators.url(url):
        bot.sendMessage(chat_id=telegram_chat, text='Please, stop sending shit.')
        return
    current_proxy = ''
    if with_proxy:
        current_proxy = get_proxy()
        logger.info('Proxy selected: %s', current_proxy)
    file_prefix = VIDEO_DL_DIR + VIDEO_FILE_PREFIX
    encoded_chat_id = bytes(str(telegram_chat), 'ascii')
    video_file = file_prefix + base64.urlsafe_b64encode(encoded_chat_id).decode('ascii') \
                 + '_' \
                 + str(uuid.uuid4())
    gif_ext = ''
    if output_gif:
        gif_ext = '.output_gif'
    video_file = video_file + gif_ext + '.' + output_type
    output_mp3 = (output_type == 'mp3')
    try:
        ydl_opts = ytdl_config(video_file, is_gif=output_gif,
                               is_mp3=output_mp3, dl_proxy=current_proxy)
        ytdl_download(url, video_file=video_file, ydl_opts=ydl_opts)
    except Exception as e:
        proxy_info = ''
        if with_proxy:
            proxy_info = 'through proxy ' + str(current_proxy)
        logger.fatal('Download %s failed: %s', proxy_info, e)
        error_msg = 'Sorry, download failed due to error : ' + str(e)
        bot.sendMessage(chat_id=telegram_chat, text=error_msg)


def get_proxy():
    http_request = urllib.request.urlopen('http://'
                                          + PROXY_WS_HOST
                                          + ':' + str(PROXY_WS_PORT)
                                          + '/')
    the_proxy = http_request.read().decode(http_request.headers.get_content_charset())
    return the_proxy


def ytdl_download(url, video_file, ydl_opts):
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        logger.info('Downloading video from "%s"', url)
        ydl.extract_info(url, download=True)
        logger.info('Video successfully downloaded to "%s"', video_file)
        final_name = get_finished_name(video_file)
        os.rename(video_file, final_name)
        logger.info('Video file renamed to "%s"', final_name)


def ytdl_config(video_file, is_gif=False, is_mp3=False, dl_proxy=''):
    ffmpeg_cmd = "ffmpeg -i {} -y -vcodec libx264 -crf 23 -vprofile baseline " \
                 + "-b:v 500k -maxrate 500k -bufsize 800k -vf scale=-2:480 -level 3.0 " \
                 + "-threads 0 -pix_fmt yuv420p -codec:a aac -ac 2 -strict experimental " \
                 + "-ab 128k -movflags +faststart " + video_file
    if is_gif:
        ffmpeg_cmd = "ffmpeg -i {} -y -vcodec libx264 -crf 23 -vprofile baseline " \
                     + "-b:v 500k -maxrate 500k -bufsize 800k -vf scale=-2:480 -level 3.0 " \
                     + "-threads 0 -pix_fmt yuv420p -an -strict experimental " \
                     + "-movflags +faststart " + video_file
    if is_mp3:
        ffmpeg_cmd = "ffmpeg -i {} -y -vn -ac 2 -f mp3 " + video_file
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': VIDEO_DL_DIR + '%(id)s',
        # Workaround for https://github.com/rg3/youtube-dl/issues/11348
        'postprocessor_args': ['-bsf:a', 'aac_adtstoasc'],
        'postprocessors': [{
            'key': 'ExecAfterDownload',
            # see https://ffmpeg.org/ffmpeg-filters.html#scale
            # for explanation on -2 choice for scale filter
            'exec_cmd': ffmpeg_cmd
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
    path = VIDEO_DL_DIR + VIDEO_FILE_PREFIX + '*_' + FINISHED_PATTERN + '*.mp?'
    logger.debug('Checking for new files to upload from %s', path)
    for file in glob.glob(path):
        encoded_chat = file.split('_')[1]
        chat = int(base64.b64decode(encoded_chat).decode('ascii'))
        try:
            logger.info('Uploading "%s" to chat "%s"', file, chat)
            if file.endswith('.mp3'):
                bot.sendAudio(chat_id=chat, audio=open(file, 'rb'), timeout=UPLOAD_TIMEOUT)
            else:
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
    dp.add_handler(CommandHandler("dlp", download_with_proxy, pass_args=True))
    dp.add_handler(CommandHandler("proxy", proxy, pass_args=True))
    dp.add_handler(CommandHandler("gif", gif, pass_args=True))
    dp.add_handler(CommandHandler("mp3", mp3, pass_args=True))

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
