"""Tools for managing entities in a shotgrid-based pipeline."""

import logging

from . import cp_ety_base

_LOGGER = logging.getLogger(__name__)


class CPEntitySG(cp_ety_base.CPEntityBase):
    """Represents an entity in a shotgrid-based pipelined."""

    def _read_outputs(self):
        """Read outputs in this entity.

        Returns:
            (CPOutput list): outputs
        """
        _LOGGER.debug('READ OUTPUTS')
        _outs = self.job.find_outputs(entity=self)
        return _outs

    def _read_work_dirs(self, class_=None):
        """Read work dirs within this entity.

        Args:
            class_ (class): override work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        from pini import pipe
        from ... import shotgrid

        _LOGGER.debug('READ WORK DIRS')
        _class = class_ or pipe.CPWorkDir

        _LOGGER.debug('READ WORK DIRS SG %s', self)

        _tmpl = self.find_template('work_dir')
        _tmpl = _tmpl.apply_data(entity_path=self.path)
        _LOGGER.debug(' - TMPL %s', _tmpl)

        _work_dirs = []
        for _work_dir in shotgrid.find_tasks(self):
            _work_dir = _class(_work_dir.path, template=_tmpl, entity=self)
            _LOGGER.debug('     - WORK DIR %s ', _work_dir)
            _work_dirs.append(_work_dir)

        return _work_dirs

    def flush(self, force=False):
        """Flush the contents of this entity.

        Args:
            force (bool): remove contents without confirmation
        """
        from pini import qt
        from ... import shotgrid

        super().flush(force=force)

        # Omit pub files in shotgrid
        _sg_job = shotgrid.SGC.find_job(self.job)
        _sg_pubs = _sg_job.find_pub_files(entity=self)
        assert isinstance(_sg_pubs, list)
        for _sg_pub in qt.progress_bar(_sg_pubs, 'Updating {:d} output{}'):
            _sg_pub.set_status('omt')
        _sg_job.find_pub_files(force=True)
