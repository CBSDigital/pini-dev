"""Tools for managing entities in a shotgrid-based pipeline."""

import logging

from . import cp_ety_base

_LOGGER = logging.getLogger(__name__)


class CPEntitySG(cp_ety_base.CPEntityBase):
    """Represents an entity in a shotgrid-based pipelined."""

    _sg_entity = None

    @property
    def sg_entity(self):
        """Obtain shotgrid cache entity for this entity.

        Returns:
            (SGCEntity): shotgrid cache entity
        """
        if not self._sg_entity:
            self._sg_entity = self.sg_proj.find_entity(
                type_=self.profile.capitalize(), entity_type=self.entity_type,
                name=self.name)
        return self._sg_entity

    @property
    def sg_proj(self):
        """Obtain shotgrid cache project for this entity.

        Returns:
            (SGCProj): shotgrid cache project
        """
        return self.job.sg_proj

    def _read_outputs(self):
        """Read outputs in this entity.

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('READ OUTPUTS')
        _outs = []
        for _sg_pub_file in self.sg_entity.find_pub_files(validated=True):
            _LOGGER.debug(' - PUB FILE %s', _sg_pub_file)
            assert _sg_pub_file.validated
            assert _sg_pub_file.latest is not None
            _tmpl = self.job.find_template_by_pattern(_sg_pub_file.template)
            _LOGGER.debug('   - TMPL %s', _sg_pub_file.template)
            _out = pipe.to_output(
                _sg_pub_file.path, template=_tmpl, entity=self,
                latest=_sg_pub_file.latest)
            _LOGGER.debug('   - OUT %s', _out)
            _outs.append(_out)
        return _outs

    def _read_work_dirs(self, class_=None):
        """Read work dirs within this entity.

        Args:
            class_ (class): override work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        from pini import pipe

        _LOGGER.debug('READ WORK DIRS')
        _class = class_ or pipe.CPWorkDir

        _LOGGER.debug('READ WORK DIRS SG %s', self)

        _tmpl = self.find_template('work_dir')
        _tmpl = _tmpl.apply_data(entity_path=self.path)
        _LOGGER.debug(' - TMPL %s', _tmpl)

        _work_dirs = []
        for _task in self.sg_entity.tasks:
            _path = _tmpl.format(task=_task.name, step=_task.step)
            _work_dir = _class(_path, template=_tmpl, entity=self)
            _LOGGER.debug('     - WORK DIR %s ', _work_dir)
            _work_dirs.append(_work_dir)

        return _work_dirs

    def flush(self, force=False):
        """Flush the contents of this entity.

        Args:
            force (bool): remove contents without confirmation
        """
        from pini import qt

        super().flush(force=force)

        # Omit pub files in shotgrid
        _sg_pubs = self.sg_entity.find_pub_files(entity=self)
        assert isinstance(_sg_pubs, list)
        for _sg_pub in qt.progress_bar(_sg_pubs, 'Updating {:d} output{}'):
            _sg_pub.set_status('omt')
        self.sg_entity.find_pub_files(force=True)
