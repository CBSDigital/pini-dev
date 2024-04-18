"""Tools for managing sections in pyui interfaces."""

import logging

from pini.utils import basic_repr

_LOGGER = logging.getLogger(__name__)


def set_section(name, collapse=False):
    """Set section within a file.

    This means that all functions below this statement will be included
    in a folding section of the ui with this name, unless there is another
    set_section statement below it.

    In the pyui file this function is just a placeholder. This function is
    then called again by the ui builder whilst parsing the python. The
    section name is extracted from the ast data which the ui is compiled.

    Args:
        name (str): name of section to apply
        collapse (bool): collapse state of section
    """
    _sect = PUSection(name, collapse=collapse)
    _LOGGER.debug('SET SECTION %s collapse=%d', _sect, _sect.collapse)
    return _sect


class PUSection(object):
    """Used to tell the ui builder that a section has been declared."""

    def __init__(self, name, collapse=False):
        """Constructor.

        Args:
            name (str): section name
            collapse (bool): collapse state of section
        """
        self.name = name
        self.collapse = collapse

    def __repr__(self):
        return basic_repr(self, self.name)
