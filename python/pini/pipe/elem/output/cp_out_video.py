"""Tools for managing output videos."""

import logging

from pini.utils import clip

from . import cp_out_file, cp_out_base

_LOGGER = logging.getLogger(__name__)


class CPOutputVideo(cp_out_file.CPOutputFile, clip.Video):
    """Represents an output video file (eg. mov/mp4)."""

    to_frame = clip.Video.to_frame

    def __init__(
            self, path, job=None, entity=None, work_dir=None, templates=None,
            template=None, types=None, latest=None):
        """Constructor.

        Args:
            path (str): path to file
            job (CPJob): force parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            types (str list): override list of template types to test for
            latest (bool): apply static latest status of this output
        """
        super().__init__(
            path, job=job, entity=entity, work_dir=work_dir,
            template=template, templates=templates, latest=latest,
            types=types or cp_out_base.OUTPUT_VIDEO_TYPES)

    def view(self, viewer=None):
        """View this clip.

        Args:
            viewer (str): force viewer
        """
        _LOGGER.debug('VIEW %s', self)
        _start_frame = None
        _rng = self.metadata.get('range')
        if _rng:
            _start_frame = _rng[0]
            _LOGGER.debug(' - APPLY START FRAME %s', _start_frame)
        super().view(start_frame=_start_frame, viewer=viewer)
