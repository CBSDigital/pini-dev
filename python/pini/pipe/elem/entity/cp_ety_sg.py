"""Tools for managing entities in a shotgrid-based pipeline."""

import collections
import logging

from pini.utils import last, CacheOutdatedError

from . import cp_ety_base

_LOGGER = logging.getLogger(__name__)


class CPEntitySG(cp_ety_base.CPEntityBase):
    """Represents an entity in a shotgrid-based pipelined."""

    _sg_entity = None

    @property
    def id_(self):
        """Obtain shotgrid asset id.

        Returns:
            (int): asset id
        """
        return self.sg_entity.id_

    @property
    def sg_entity(self):
        """Obtain shotgrid cache entity for this entity.

        Returns:
            (SGCEntity): shotgrid cache entity
        """
        if not self._sg_entity:
            _LOGGER.debug('SG ENTITY %s', self)
            self._sg_entity = self.sg_proj.find_entity(
                type_=self.profile.capitalize(), entity_type=self.entity_type,
                name=self.name, omitted=False, catch=True)
        return self._sg_entity

    @property
    def sg_proj(self):
        """Obtain shotgrid cache project for this entity.

        Returns:
            (SGCProj): shotgrid cache project
        """
        return self.job.sg_proj

    def _read_outputs(self, force=False):
        """Read outputs in this entity.

        Args:
            force (bool): force update shotgrid cache

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('READ OUTPUTS')

        # Build output objects
        _outs = {}  # Accomodate many pubs with same path (just use latest)
        for _sg_pub_file in self.sg_entity.find_pub_files(
                validated=True, omitted=False, force=force):
            _LOGGER.debug(' - PUB FILE %s', _sg_pub_file)
            assert _sg_pub_file.validated

            # Find template for this output
            _tmpl = self.job.find_template_by_pattern(
                _sg_pub_file.template, catch=True)
            if not _tmpl:
                _LOGGER.error(
                    'FAILED TO MATCH TEMPLATE %s', _sg_pub_file.template)
                _LOGGER.error('JOB CFG NAME %s', self.job.cfg_name)
                raise CacheOutdatedError(self)

            # Build output
            _LOGGER.debug('   - TMPL %s', _sg_pub_file.template)
            _out = pipe.to_output(
                _sg_pub_file.path, template=_tmpl, entity=self)
            _out.sg_pub_file = _sg_pub_file
            _out.status = _sg_pub_file.status
            _LOGGER.debug('   - OUT %s', _out)
            _outs[_out.path] = _out

        _outs = sorted(_outs.values())

        # Read + apply latest
        _latest_map = collections.defaultdict(list)
        for _out in _outs:
            _latest_map[_out.sg_pub_file.stream].append(_out)
        _latest_map = dict(_latest_map)
        for _stream in _latest_map.values():
            _stream.sort()
            for _latest, _out in last(_stream):
                _LOGGER.debug(' - APPLY LATEST %d %s', _latest, _out)
                _out.set_latest(_latest)

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
            if not (_task.step and _task.name):
                continue
            _LOGGER.debug(' - STEP/TASK %s %s', _task.step, _task)
            _path = _tmpl.format(task=_task.name, step=_task.step)
            _LOGGER.debug('   - PATH %s', _path)
            _work_dir = _class(_path, template=_tmpl, entity=self)
            _LOGGER.debug('   - WORK DIR %s ', _work_dir)
            _work_dirs.append(_work_dir)

        return _work_dirs

    def flush(self, force=False):
        """Flush the contents of this entity.

        Args:
            force (bool): remove contents without confirmation
        """
        _LOGGER.info('FLUSH %s %s', self, self.sg_entity.id_)
        from pini import qt, testing
        from pini.pipe import shotgrid

        assert self in (testing.TMP_ASSET, testing.TMP_SHOT)
        assert 'tmp' in self.name.lower()
        super().flush(force=force)

        # Delete all pub file entries
        _sg = shotgrid.to_handler()
        _results = _sg.find(
            'PublishedFile', fields=['entity', 'name'],
            filters=[self.sg_entity.to_filter()])
        _LOGGER.info(' - FOUND %d RESULTS', len(_results))
        for _result in qt.progress_bar(
                _results, 'Deleting {:d} tmp entries',
                stack_key='DeletePublishedFiles'):
            _LOGGER.info('DELETE %s %s', _result['name'], _result)
            assert _result['entity']['id'] == self.sg_entity.id_
            _sg.delete(entity_type='PublishedFile', entity_id=_result['id'])

        self.sg_entity.find_pub_files(force=True)
