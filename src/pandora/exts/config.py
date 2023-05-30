# -*- coding: utf-8 -*-

from os import getenv
from os.path import join

from appdirs import user_config_dir

USER_CONFIG_DIR = getenv('USER_CONFIG_DIR', user_config_dir('Pandora-ChatGPT'))
DATABASE_URI = getenv(
    'DATABASE_URI',
    f"sqlite:///{join(USER_CONFIG_DIR, 'pandora-chatgpt.db')}?check_same_thread=False",
)
