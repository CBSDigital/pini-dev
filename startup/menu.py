"""Sets up pini tools in nuke.

This dir should be added to $NUKE_PATH for it to be executed on startup.
"""

import inspect
import logging

_LOGGER = logging.getLogger('pini/menu.py')


def _run_pini_install():
    """Install pini."""

    # Setup pini
    import pini_startup
    pini_startup.init()

    # Run installer
    from pini import install, testing
    testing.setup_logging()
    _file = inspect.getfile(_run_pini_install)
    _LOGGER.info('RUNNING %s', _file)
    install.INSTALLER.run()


if __name__ == '__main__':
    try:
        _run_pini_install()
    except Exception as _exc:  # pylint: disable=broad-exception-caught
        _LOGGER.info('FAILED TO INSTALL PINI %s', _exc)
