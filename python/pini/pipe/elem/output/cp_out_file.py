"""Tools for managing output files."""

import logging

from pini.utils import File

from . import cp_out_base

_LOGGER = logging.getLogger(__name__)


class CPOutputFile(File, cp_out_base.CPOutputBase):
    """Represents an output file on disk."""

    __lt__ = cp_out_base.CPOutputBase.__lt__
    get_metadata = cp_out_base.CPOutputBase.get_metadata
    set_metadata = cp_out_base.CPOutputBase.set_metadata
    metadata_yml = cp_out_base.CPOutputBase.metadata_yml

    def __init__(  # pylint: disable=unused-argument
            self, path, job=None, entity=None, work_dir=None, templates=None,
            template=None, types=None, latest=None):
        """Constructor.

        Args:
            path (str): path to file
            job (CPJob): parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            types (str list): override list of template types to test for
            latest (bool): apply static latest status of this output
        """
        super().__init__(path)
        cp_out_base.CPOutputBase.__init__(
            self, job=job, entity=entity, work_dir=work_dir,
            template=template, templates=templates, latest=latest,
            types=types or cp_out_base.OUTPUT_FILE_TYPES)

    @property
    def metadata(self):
        """Obtain this output's metadata.

        Returns:
            (dict): metadata
        """
        _LOGGER.debug('METADATA %s', self)
        return self.get_metadata()
