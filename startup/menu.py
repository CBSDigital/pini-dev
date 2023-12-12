"""Sets up pini tools in nuke.

This dir should be added to $NUKE_PATH for it to be executed on startup.
"""

import inspect
import logging

from pini import install, testing

_LOGGER = logging.getLogger('pini/menu.py')


def _run_pini_install():
    """Install pini."""
    install.INSTALLER.run()


if __name__ == '__main__':
    testing.setup_logging()
    _file = inspect.getfile(_run_pini_install)
    _LOGGER.info('RUNNING %s', _file)
    _run_pini_install()
