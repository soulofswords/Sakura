"""Distinct product identity, with a mode icon inside Companion."""
from pathlib import Path


def icon_path(root, edition, tracking=False):
    name='vtuber' if edition=='vtuber' else 'companion-vtuber' if tracking else 'companion'
    return Path(root)/'launcher'/(name+'.ico')
