"""Pixiv API library"""

from .aapi import AppPixivAPI
from .utils import PixivError

__all__ = ("AppPixivAPI", "PixivError")
