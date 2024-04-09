"""Tools for rendering sequencer in unreal."""

import logging
import sys

_LOGGER = logging.getLogger(__name__)


def _setup_logging():
    """Setup logging with a generic handler."""
    _logger = logging.getLogger()
    _logger.setLevel(logging.INFO)

    # Flush existing handlers
    while _logger.handlers:
        _handler = _logger.handlers[0]
        _LOGGER.debug(' - REMOVE HANDLER %s', _handler)
        _logger.removeHandler(_handler)

    # Create default handler
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter(
        '- %(name)s: %(message)s')
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)


def _setup_pini():
    """Setup pini tools."""
    _LOGGER.info('SETUP PINI py=%d', sys.version_info.major)

    _paths = [
    ]
    for _path in _paths:
        if _path not in sys.path:
            sys.path.insert(0, _path)

    import pini_startup
    pini_startup.init()


def _init_unreal_render():
    """Initiate unreal render tools."""
    _LOGGER.info(' - INIT UNREAL RENDER TOOLS')

    _args = list(sys.argv)
    _args.pop(0)
    _LOGGER.info(' - ARGS %s', _args)

    if not _args:
        raise NotImplementedError


if __name__ == '__main__':
    _setup_logging()
    _setup_pini()
    _init_unreal_render()
