"""Sets up pini tools in maya.

This dir should be added to $PYTHONPATH for maya to run this file on launch.
"""

import inspect
import logging

from pini import install

from maya import cmds

_LOGGER = logging.getLogger('pini/userSetup.py')


def _run_pini_install():
    """Install pini tools."""
    if install.INSTALLER:
        install.INSTALLER.run()


if __name__ == '__main__':

    _file = inspect.getfile(_run_pini_install)
    _LOGGER.info('SOURCING %s', _file)
    cmds.evalDeferred(_run_pini_install, lowPriority=True)
