"""Tools for managing cacheable entity elements."""

import functools
import logging
import time

from pini.utils import nice_id, single, Dir

from .ccp_utils import (
    pipe_cache_result, pipe_cache_on_obj, pipe_cache_to_file)
from ..cp_sequence import CPSequence
from ..cp_entity import CPEntity
from ..cp_asset import CPAsset
from ..cp_shot import CPShot

_LOGGER = logging.getLogger(__name__)


class CCPSequence(CPSequence):
    """Cacheable version of the sequence object."""

    @property
    def shots(self):
        """Get list of shots in this sequence.

        Returns:
            (CCPShot list): shots
        """
        return self.find_shots()

    def create(self, *args, **kwargs):
        """Create a new sequence in this job.

        Args:
            force (bool): create without confirmation dialog
        """
        super(CCPSequence, self).create(*args, **kwargs)
        self.job.find_sequences(force=True)

    def find_shots(self, force=False, **kwargs):
        """Find shots within this sequence.

        Args:
            force (bool): force reread shots from disk

        Returns:
            (CCPShot list): matching shots
        """
        from pini import pipe
        if force:
            if pipe.MASTER == 'disk':
                self._read_shots(force=True)
            elif pipe.MASTER == 'shotgrid':
                self.job.read_shots_sg(force=True)
            else:
                raise ValueError
        return super(CCPSequence, self).find_shots(**kwargs)

    @pipe_cache_on_obj
    def _read_shots(self, class_=None, force=False):
        """Read shots in the given sequence.

        Args:
            class_ (class): override shot class
            force (bool): force reread from disk

        Returns:
            (CCPShot list): shots in sequence
        """
        _class = class_ or CCPShot
        return super(CCPSequence, self)._read_shots(class_=_class)


class CCPEntity(CPEntity):
    """Cacheable version of the base entity object."""

    @property
    def cache_fmt(self):
        """Build cache path format.

        Returns:
            (str): cache format
        """
        return '{}/.pini/cache/{{func}}.pkl'.format(self.path)

    @property
    def outputs(self):
        """Obtain list of outputs in this entity.

        Returns:
            (CPOutput tuple): all entity-level outputs
        """
        return tuple(self.find_outputs())

    @property
    def work_dirs(self):
        """Access the list of tasks in this entity.

        Returns:
            (str list): tasks
        """
        return tuple(self.find_work_dirs())

    def obt_work_dir(self, match, catch=False):
        """Find a work dir object within this entity.

        Args:
            match (CPWorkDir): work dir to find
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): matching work dir
        """
        from pini import pipe
        if isinstance(match, pipe.CPWorkDir):
            if pipe.MASTER == 'disk':
                _result = single([
                    _work_dir for _work_dir in self.work_dirs
                    if _work_dir == match],
                    catch=catch,
                    error='Failed to find work dir '+match.path)
            elif pipe.MASTER == 'shotgrid':
                _result = self.job.obt_work_dir(match)
            else:
                raise NotImplementedError(pipe.MASTER)
            return _result
        raise NotImplementedError

    def find_work_dirs(self, force=False, **kwargs):
        """Find work dirs.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPWorkDir list): work dirs
        """
        if force:
            self._read_work_dirs(force=True)
        return super(CCPEntity, self).find_work_dirs(**kwargs)

    def _read_work_dirs(self, class_=None, force=False):
        """Read all work dirs for this entity.

        Args:
            class_ (class): override work dir class
            force (bool): rebuild cache

        Returns:
            (CCPWorkDir): work dirs
        """
        from pini import pipe
        _LOGGER.debug('READ WORK DIRS %s %s', nice_id(self), self)
        if class_:
            raise NotImplementedError
        if pipe.MASTER == 'disk':
            _work_dirs = self._read_work_dirs_disk(force=force)
        elif pipe.MASTER == 'shotgrid':
            _work_dirs = sorted(
                self.job.find_work_dirs(entity=self, force=force))
        else:
            raise NotImplementedError
        _LOGGER.debug(' - FOUND %d WORK DIRS %s', len(_work_dirs), _work_dirs)
        return _work_dirs

    @pipe_cache_on_obj
    def _read_work_dirs_disk(self, class_=None, force=False):
        """Find tasks in this entity.

        Args:
            class_ (class): override work dir class
            force (bool): force reread work dirs from disk

        Returns:
            (CCPWorkDir list): work dirs
        """
        from pini.pipe import cache
        if class_:
            raise NotImplementedError
        return super(CCPEntity, self)._read_work_dirs_disk(
            class_=cache.CCPWorkDir)

    def to_work_dir(self, *args, **kwargs):
        """Obtain a work dir object within this entity.

        If an existing work dir is not found, a new one is created.

        Args:
            task (str): work dir task
            dcc_ (str): work dir dcc
            catch (bool): no error if token fail to create valid
                work dir object (just return None)
            class_ (class): override work dir class

        Returns:
            (CCPWorkDir): work dir
        """
        from pini.pipe import cache
        _class = kwargs.pop('class_', None) or cache.CCPWorkDir
        _work_dir = super(CCPEntity, self).to_work_dir(
            *args, class_=_class, **kwargs)
        _existing = single([
            _o_work_dir for _o_work_dir in self.work_dirs
            if _work_dir == _o_work_dir], catch=True)
        if _existing:
            return _existing
        return _work_dir

    @functools.wraps(CPEntity.to_work)
    def to_work(self, **kwargs):
        """Obtain a work object within this entity.

        If a matching one does not exist, a new object is created.

        Returns:
            (CCPWork): work
        """
        from pini.pipe import cache
        _kwargs = kwargs
        _kwargs['class_'] = _kwargs.get('class_', cache.CCPWork)
        return super(CCPEntity, self).to_work(**_kwargs)

    def obt_output(self, match, catch=False, force=False):
        """Obtain output output withing this entity.

        Args:
            match (any): token to match with output
            catch (bool): no error if no output found
            force (bool): reread outputs from disk

        Returns:
            (CPOutput): matching output
        """
        from pini import pipe
        _match = match
        if force:
            self.find_outputs(force=True)
        if isinstance(_match, pipe.CPOutputBase):
            _out = CPEntity.find_output(
                self, output_name=_match.output_name, task=_match.task,
                output_type=_match.output_type, ver_n=_match.ver_n,
                tag=_match.tag, extn=_match.extn, catch=catch)
            return _out
        raise NotImplementedError

    def find_outputs(self, type_=None, force=False, **kwargs):
        """Find outputs in this entity (stored at entity level).

        Args:
            type_ (str): filter by type (eg. cache/render)
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): entity level outputs
        """
        from pini import pipe
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)
        if force:
            if pipe.MASTER == 'disk':
                self._update_outputs_cache()
                if force > 1:
                    _LOGGER.info('REREADING ALL SEQ DIRS %s', self)
                    from pini import qt
                    for _seq_dir in qt.progress_bar(
                            self.find_output_seq_dirs(),
                            'Checking {:d} seq{}', stack_key='RereadSeqDirs'):
                        _seq_dir.find_outputs(force=True)
            elif pipe.MASTER == 'shotgrid':
                self.job.find_outputs(force=True)
            else:
                raise NotImplementedError(pipe.MASTER)
        return super(CCPEntity, self).find_outputs(type_=type_, **kwargs)

    def obt_output_seq_dir(self, dir_, force=False):
        """Obtain an output sequence directory from this entity.

        Args:
            dir_ (str): path to output sequence directory
            force (bool): force reread output sequence directories
                in the parent entity cache

        Returns:
            (CCPOutputSeqDir): output sequence directory
        """
        _dir = Dir(dir_)
        for _seq_dir in self.find_output_seq_dirs(force=force):
            if _seq_dir.path == _dir.path:
                return _seq_dir
        raise ValueError(_dir.path)

    def find_output_seq_dirs(self, force=False, **kwargs):
        """Find output sequence directories in this entity.

        Args:
            force (bool): reread from disk

        Returns:
            (CCPOutputSeqDir list): output sequence directories
        """
        if force:
            self._update_outputs_cache()
        return super(CCPEntity, self).find_output_seq_dirs(**kwargs)

    def _update_outputs_cache(self):
        """Update outputs cache.

        First the globs are cached as this is the main disk read. Then
        the sequences dir objects and output files are rebuilt using the
        updated globs cache.
        """
        _globs = self._read_output_globs(force=True)
        _seq_dirs = self._build_output_seq_dirs(force=True)
        _files = self._build_output_files(force=True)
        _LOGGER.info('UPDATED OUTPUTS CACHE globs=%d seq_dirs=%d files=%d',
                     len(_globs), len(_seq_dirs), len(_files))

    @pipe_cache_on_obj
    def _read_output_globs(self, force=False):
        """Read output glob data.

        Args:
            force (bool): reread from disk

        Returns:
            (dict): template: path list dict
        """
        _start = time.time()
        _globs = super(CCPEntity, self)._read_output_globs()
        _LOGGER.debug('FOUND %d OUTPUT GLOBS IN %s (%.02fs)', len(_globs),
                      self.name, time.time() - _start)
        return _globs

    @pipe_cache_on_obj
    def _build_output_seq_dirs(
            self, globs=None, seq_dir_class=None, force=False):
        """Build outputs sequence directories from glob data.

        Args:
            globs (tuple): override globs data
            seq_dir_class (class): override output sequence class
            force (bool): force rebuild seq dir objects from globs

        Returns:
            (CCPOutputSeqDir list): output sequence directories
        """
        from pini.pipe import cache
        _seq_dir_class = seq_dir_class or cache.CCPOutputSeqDir
        _seq_dirs = super(CCPEntity, self)._build_output_seq_dirs(
            seq_dir_class=_seq_dir_class, globs=globs)
        _LOGGER.debug(' - BUILT %d OUTPUT SEQ DIRS', len(_seq_dirs))
        return _seq_dirs

    @pipe_cache_on_obj
    def _build_output_files(
            self, globs=None, file_class=None, video_class=None, force=False):
        """Build outputs in this entity from glob data.

        Args:
            globs (tuple): override globs data
            file_class (class): override output file class
            video_class (class): override output video class
            force (bool): force rebuild output objects from globs

        Returns:
            (CCPOutput list): shot outputs
        """
        _LOGGER.debug('BUILD OUTPUT FILES')
        from pini.pipe import cache
        return super(CCPEntity, self)._build_output_files(
            globs=globs,
            file_class=file_class or cache.CCPOutput,
            video_class=video_class or cache.CCPOutputVideo)

    @functools.wraps(CPEntity.find_publishes)
    def find_publishes(self, force=False, **kwargs):
        """Find publishes within this entity.

        Publishes are cached to disk a entity level, so a force flag
        is added here.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): publishes
        """
        from pini import pipe
        if force:
            if pipe.MASTER == 'disk':
                self._read_work_dirs_disk(force=True)
                self._read_publishes_disk(force=True)
            elif pipe.MASTER == 'shotgrid':
                self.job.find_publishes(force=True)
            else:
                raise NotImplementedError(pipe.MASTER)
        return super(CCPEntity, self).find_publishes(**kwargs)

    @pipe_cache_to_file
    def _read_publishes_disk(self, force=False):
        """Read publishes within this entity from disk.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): publishes
        """
        return super(CCPEntity, self)._read_publishes_disk()

    def flush(self, force=False):
        """Flush contents of this entity.

        Args:
            force (bool): remove elements without confirmation
        """
        super(CCPEntity, self).flush(force=force)
        self.find_outputs(force=True)


class CCPAsset(CCPEntity, CPAsset):
    """Cacheable version of the asset object."""

    def create(self, **kwargs):
        """Create this asset."""
        _LOGGER.debug('[CCPAsset] CREATED %s (ready for discard)',
                      nice_id(self))
        super(CCPAsset, self).create(**kwargs)

        assert self.exists()

        # Update caches
        self.job.find_asset_types(force=True)
        self.job.read_type_assets(asset_type=self.asset_type, force=True)

        assert self.asset_type in self.job.asset_types
        assert self in self.job.assets
        _LOGGER.debug(' - CREATE COMPLETE %s', nice_id(self))


class CCPShot(CCPEntity, CPShot):
    """Cacheable version of the shot object."""

    def create(self, **kwargs):
        """Create this shot."""
        from pini import pipe

        _LOGGER.debug('CREATE SHOT')
        super(CCPShot, self).create(**kwargs)

        # Update cache on parent
        _seq = self.to_sequence()
        _LOGGER.debug(' - UPDATING SEQUENCE CACHE %s', _seq)
        if isinstance(_seq, pipe.CPSequence):
            _shots = _seq.find_shots(force=True)
            assert self in _shots
            assert self in _seq.shots
            assert self.job.uses_sequence_dirs
        else:
            self.job.find_shots(force=True)

        assert self in self.job.shots

    @pipe_cache_result
    def to_sequence(self):
        """Obtain this shot's corresponding sequence object.

        Returns:
            (CCPSequence): sequence
        """
        if not self.job.uses_sequence_dirs:
            return self.sequence
        try:
            return self.job.find_sequence(self.sequence)
        except ValueError:
            return CCPSequence(self.path, job=self.job)
