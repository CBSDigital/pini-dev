"""Tools for managing output files."""

import logging

from pini.utils import File

from . import cp_out_base

_LOGGER = logging.getLogger(__name__)


class CPOutput(File, cp_out_base.CPOutputBase):
    """Represents an output file on disk."""

    __lt__ = cp_out_base.CPOutputBase.__lt__
    yaml_tag = '!CPOutput'

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

    @classmethod
    def from_yaml(cls, loader, node):
        """Build output object from yaml.

        Args:
            cls (class): output class
            loader (Loader): yaml loader
            node (Node): yaml data

        Returns:
            (CPOutput): output
        """
        del loader  # for linter
        return cls(node.value)

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
        _tag = '!'+type(data).__name__
        _LOGGER.debug('TO YAML %s %s', cls.yaml_tag, _tag)
        return dumper.represent_scalar(_tag, data.path)
