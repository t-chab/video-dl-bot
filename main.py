#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Simple Bot to fetch video and upload them to telegram.
This Bot uses the Updater class to handle the bot.
First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import os
import uuid

import youtube_dl
from telegram.ext import Updater, CommandHandler
import logging

# Name of the environment variable which defines the bot token
TOKEN_ENV_NAME = 'VIDEO_DL_BOT_TOKEN'

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def show_help(bot, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Usage /dl [url]')


def download(bot, update, args):
    logger.info('args: "%s"', args)
    url = args[0]
    # youtube-dl setup
    video_dl_location = '/tmp/'
    video_file = video_dl_location + str(uuid.uuid4()) + '.mp4'
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': video_dl_location + '%(id)s',
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
        'verbose': True
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        logger.info('Downloading video from "%s"', url)
        video_info = ydl.extract_info(url, download=True)
        logger.info('Video successfully downloaded to "%s"', video_file)
    bot.sendVideo(chat_id=update.message.chat_id, video=open(video_file, 'rb'),
                  caption=video_info.get('title'))


def error(bot, update, err):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, err)


def main():
    # Create the Updater and pass it your bot's token.
    token = os.environ.get(TOKEN_ENV_NAME)
    if token is None:
        logger.fatal('Can\'t find bot token in environement variable "%s"', TOKEN_ENV_NAME)
        return 1

    updater = Updater(token)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Map commands
    dp.add_handler(CommandHandler("help", show_help))
    dp.add_handler(CommandHandler("dl", download, pass_args=True))

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
