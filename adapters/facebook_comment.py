"""Stable boundary for exact-post comment resolution."""
from fb_comment import comment_on_post as _comment_on_post


def resolve_and_comment(post_url, comment_content, **kwargs):
    return _comment_on_post(post_url, comment_content, **kwargs)
