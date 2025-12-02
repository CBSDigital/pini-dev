"""Tools for managing the base maya render handler."""

import logging

from maya_pini import open_maya as pom
from maya_pini.utils import find_cams

from .. import rh_base

_LOGGER = logging.getLogger(__name__)


class CMayaRenderHandler(rh_base.CRenderHandler):
    """Base class for any maya render handler."""

    # def build_ui(self):
    #     """Build basic render interface into the given layout."""
    #     super().build_ui(add_range='Frames', add_snapshot=False)

    def find_cams(self):
        """Find cameras in the current scene.

        Returns:
            (CCamera list): cameras
        """
        _cams = find_cams(orthographic=False)
        _cam = pom.find_render_cam(catch=True)
        if not _cam:
            _r_cams = find_cams(renderable=True, orthographic=False)
            if _r_cams:
                _cam = _r_cams[0]
        if not _cam:
            _cam = _cams[0]
        return _cams, _cam
