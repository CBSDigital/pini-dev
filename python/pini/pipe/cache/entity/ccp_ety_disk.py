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

        # Find outputs in this entity
        _outs = self.find_outputs(force=force)
        _pub_outs = sorted([_out for _out in _outs if not _out.is_media()])

        # Sort into streams
        _to_tag = []
        _streams = {}
        for _out in _pub_outs:
            _LOGGER.debug(' - CHECK OUT %s', _out)
            _stream = _out.to_stream()
            _LOGGER.debug('   - STREAM %s', _stream)
            _to_tag.append((_out, _stream))
            _streams[_stream] = _out
        _LOGGER.debug(' - FOUND %d WORK DIR OUTPUTS', len(_outs))

        # Apply version numbers
        _pubs = []
        for _out, _stream in _to_tag:
            _LOGGER.debug(' - TEST PUB %s', _out)
            if not _out.ver_n:
                _latest = True
            else:
                _latest = _streams[_stream] == _out
                _LOGGER.debug('   - STREAM %s', _stream)
            _LOGGER.debug('   - LATEST %d', _latest)
            _out.set_latest(_latest)
            _pub = _out.to_ghost()
            _LOGGER.debug('   - PUB %s', _pub)
            _pubs.append(_pub)
        _LOGGER.debug(' - FOUND %d PUBS', len(_pubs))

        return _pubs

    def _obt_output_cacheable(self, output, catch, force):
        """Obtain cacheable version of the given output.

        Args:
            output (CPOutput): output to convert
            catch (bool): no error if no output found
            force (bool): reread outputs from disk

        Returns:
            (CCPOutput): cacheable output
        """
        from pini import pipe
        from ... import cache

        _LOGGER.debug(' - OBTAINED OUTPUT %s', output)
        assert output.entity == self

        # Find output
        if output.work_dir:  # Work dir output
            _work_dir = self.obt_work_dir(output.work_dir)
            if not _work_dir:
                return None
            _LOGGER.debug(' - WORK DIR %s', _work_dir)
            assert isinstance(_work_dir, cache.CCPWorkDir)
            assert isinstance(_work_dir.entity, cache.CCPEntity)
            _out = _work_dir.obt_output(output, catch=catch, force=force)
        else:  # Must be entity level output
            _LOGGER.debug(' - SEARCHING ENTITY OUTPUTS')
            _out = self.find_output(output, catch=catch)
        _LOGGER.debug(' - FOUND OUTPUT %s', _out)

        # Check output
        if _out:
            assert isinstance(_out, pipe.CPOutputBase)
            assert isinstance(_out, cache.CCPOutputBase)
            assert isinstance(_out.entity, cache.CCPEntity)

        return _out

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
                error='Failed to find work dir ' + match.path)
        raise NotImplementedError
