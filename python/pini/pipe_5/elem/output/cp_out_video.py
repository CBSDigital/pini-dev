"""Tools for managing output videos."""

import logging

from pini.utils import clip

from . import cp_out_file, cp_out_base

_LOGGER = logging.getLogger(__name__)


class CPOutputVideo(cp_out_file.CPOutputFile, clip.Video):
    """Represents an output video file (eg. mov/mp4)."""

    yaml_tag = '!CPOutputVideo'
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

    @classmethod
    def to_yaml(cls, dumper, data):
        """Convert this output to yaml.

        Args:
            cls (class): output class
            dumper (Dumper): yaml dumper
            data (CPOutput): output being exported

        Returns:
            (str): output as yaml
        """
        return dumper.represent_scalar(cls.yaml_tag, data.path)
