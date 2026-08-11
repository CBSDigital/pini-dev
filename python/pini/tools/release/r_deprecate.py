"""Tools for managing code deprecation.

The implementation has moved to pini.utils.apply_deprecation so that low-level
modules (eg. maya_pini.open_maya, pini.utils) can flag deprecations without
importing the pini.tools.release package. This re-export is retained for
backwards compatibility.
"""

# pylint: disable=unused-import

from pini.utils import apply_deprecation
