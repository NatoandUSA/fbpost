"""Stable boundary for GPM start/attach/teardown lifecycle."""
from utils import launch_browser as _launch_browser, close_browser as _close_browser


def launch(account, playwright, api_url=None):
    return _launch_browser(account, playwright, api_url)


def close(browser_or_context, account=None, api_url=None):
    return _close_browser(browser_or_context, account, api_url)
