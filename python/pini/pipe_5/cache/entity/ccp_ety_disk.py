"""Tools for managing cacheable entities on a disk-based pipeline."""

import logging
import time

from pini.utils import single, Dir

from ..ccp_utils import pipe_cache_on_obj, pipe_cache_to_file
from . import ccp_ety_base

_LOGGER = logging.getLogger(__name__)


class CCPEntityDisk(ccp_ety_base.CCPEntityBase):
    """Represents a cacheable entity on a disk-based pipeline."""

    def find_output_seq_dirs(self, force=False, **kwargs):
        """Find output sequence directories in this entity.

        Args:
            force (bool): reread from disk

        Returns:
            (CCPOutputSeqDir list): output sequence directories
        """
        if force:
            self._update_outputs_cache()
        return super().find_output_seq_dirs(**kwargs)

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

    @pipe_cache_on_obj
    def _read_output_globs(self, force=False):
        """Read output glob data.

        Args:
            force (bool): reread from disk

        Returns:
            (dict): template: path list dict
        """
        _start = time.time()
        _globs = super()._read_output_globs()
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
        _seq_dirs = super()._build_output_seq_dirs(
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
        return super()._build_output_files(
            globs=globs,
            file_class=file_class or cache.CCPOutputFile,
            video_class=video_class or cache.CCPOutputVideo)

    def _update_outputs_cache(self, force=True):
        """Update outputs cache.

        First the globs are cached as this is the main disk read. Then
        the sequences dir objects and output files are rebuilt using the
        updated globs cache.

        Args:
            force (int): rebuild level
                1 - simple disk read of all outputs
                2 - read outputs + reread all seq frame caches
        """

        # Reread outputs
        _globs = self._read_output_globs(force=True)
        _seq_dirs = self._build_output_seq_dirs(force=True)
        _files = self._build_output_files(force=True)
        _LOGGER.info('UPDATED OUTPUTS CACHE globs=%d seq_dirs=%d files=%d',
                     len(_globs), len(_seq_dirs), len(_files))

        # Update all sequence ranges
        if force > 1:
            _LOGGER.info('REREADING ALL SEQ DIRS %s', self)
            from pini import qt
            for _seq_dir in qt.progress_bar(
                    self.find_output_seq_dirs(),
                    'Checking {:d} seq{}', stack_key='RereadSeqDirs'):
                _seq_dir.find_outputs(force=True)

    @pipe_cache_to_file
    def _read_publishes(self, force=False):
        """Read all publishes in this entity.

        Args:
            force (bool): rebuild disk cache

        Returns:
            (CPOutput list): all publishes
        """
        _LOGGER.debug('READ PUBLISHES force=%d %s', force, self)

        _work_dirs = self.find_work_dirs(force=force)
        _LOGGER.debug(' - FOUND %d WORK DIRS', len(_work_dirs))

        # Search work dirs for outputs
        _outs = []
        _streams = {}
        for _work_dir in _work_dirs:
            for _out in _work_dir.find_outputs(type_='publish'):
                _LOGGER.debug(' - CHECK OUT %s', _out)
                _stream = _out.to_stream()
                _LOGGER.debug('   - STREAM %s', _stream)
                _outs.append((_out, _stream))
                _streams[_stream] = _out
        _LOGGER.debug(' - FOUND %d WORK DIR OUTPUTS', len(_outs))

        # Apply version numbers
        _pubs = []
        for _out, _stream in _outs:
            _LOGGER.debug(' - TEST PUB %s', _out)
            if not _out.ver_n:
                _latest = True
            else:
                _latest = _streams[_stream] == _out
                _LOGGER.debug('   - STREAM %s', _stream)
            _LOGGER.debug('   - LATEST %d', _latest)
            _pub = _out.to_ghost()
            _LOGGER.debug('   - PUB %s', _pub)
            _pubs.append(_pub)
        _LOGGER.debug(' - FOUND %d PUBS', len(_pubs))

        return _pubs

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
            return single([
                _work_dir for _work_dir in self.work_dirs
                if _work_dir == match],
                catch=catch,
                error='Failed to find work dir '+match.path)
        raise NotImplementedError

    # @pipe_cache_on_obj
    # def _read_work_dirs(self, class_=None, force=False):
    #     """Read all work dirs for this entity.

    #     Args:
    #         class_ (class): override work dir class
    #         force (bool): rebuild cache

    #     Returns:
    #         (CCPWorkDir): work dirs
    #     """
    #     from ... import cache
    #     _LOGGER.debug('READ WORK DIRS %s %s', nice_id(self), self)
    #     if class_:
    #         raise NotImplementedError
    #     _work_dirs = super()._read_work_dirs(class_=cache.CCPWorkDir)
    #     _LOGGER.debug(' - FOUND %d WORK DIRS %s', len(_work_dirs), _work_dirs)
    #     return _work_dirs
