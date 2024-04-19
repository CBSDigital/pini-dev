"""Test for pyui."""

import logging

from maya import cmds

from pini import icons
from pini.tools import pyui

_LOGGER = logging.getLogger(__name__)

PYUI_COL = "RoyalBlue"
PYUI_TITLE = 'Test PYUI'


pyui.set_section('Create', collapse=True)


def create_sphere():
    """Create sphere."""
    _LOGGER.info("CREATE SPHERE")
    cmds.polySphere()


def create_cube():
    """Create cube."""
    _LOGGER.info("CREATE CUBE")
    cmds.polyCube()


def create_cylinder():
    """Create cylinder."""
    _LOGGER.info("CREATE CYLINDER")
    cmds.polyCylinder()


pyui.set_section('Advanced')


@pyui.install(label='Print "SOMETHING"', icon=icons.find('Tennis'))
def print_something(something='test'):
    """Print something."""
    _LOGGER.info(something)


@pyui.install(
    clear=['none_test'], browser=['path_test'],
    choices={'choices_test': ['Apple', 'Cherry', 'Banana']})
def args_test(
        bool_test=True, str_test='hello', int_test=1, none_test=None,
        path_test='', choices_test='choice'):
    """Test for args.

    Args:
        bool_test (bool): test bool
        str_test (str): test str
    """
    _LOGGER.info("ARGS TEST")
    _LOGGER.info(" - BOOL %d", bool_test)
    _LOGGER.info(" - STR %s", str_test)
    _LOGGER.info(" - INT %s", int_test)
    _LOGGER.info(" - NONE %s", none_test)
    _LOGGER.info(" - PATH %s", path_test)
    _LOGGER.info(" - CHOICES %s", choices_test)


pyui.set_section('Dev', collapse=False)


def test():
    print("TEST")
