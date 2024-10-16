"""Tools for managing cacheable work objects."""

import functools
import logging
import sys

from pini.utils import nice_id, File, nice_size

from .ccp_utils import pipe_cache_result, pipe_cache_to_file
from ..elem import CPWork

_LOGGER = logging.getLogger(__name__)


class CCPWork(CPWork):
    """Cacheable version of the work object."""

    _exists = True

    @property
    def cache_fmt(self):
        """Obtain cache format string for storing work dir data.

        Returns:
            (str): cache format
        """
        return self.work_dir.to_file(
            '.pini/cache/%s_%s_{func}.pkl' % (self.base, sys.platform)).path

    @property
    def outputs(self):
        """Get list of outputs belonging to this work file.

        Returns:
            (CPOutput|CPOutputSeq list): outputs
        """
        return tuple(self.find_outputs())

    @pipe_cache_result
    def _read_metadata(self, force=False):
        """Read work metadata.

        Args:
            force (bool): force reread from disk

        Returns:
            (dict): metadata
        """
        return super()._read_metadata()

    def exists(self):  # pylint: disable=arguments-differ
        """Test whether this work file exists.

        Returns:
            (bool): whether exists
        """
        return self._exists

    def set_exists(self, exists):
        """Set file exists cache.

        Args:
            exists (bool): value to apply
        """
        self._exists = exists

    def find_next(self, user=None, class_=None):
        """Find next version of this work file.

        Args:
            user (str): override user
            class_ (class): override work file class

        Returns:
            (CCPWork): next version
        """
        _next = super().find_next(
            class_=class_ or CCPWork, user=user)
        _next.set_exists(False)
        assert not _next.exists()
        return _next

    def find_outputs(self, *args, **kwargs):
        """Find outputs generated from this work file.

        Args:
            force (bool): force reread from disk

        Returns:
            (CPOutput list): outputs
        """
        _force = kwargs.pop('force', None)
        _LOGGER.log(9, 'FIND OUTPUTS force=%d %s', _force, self)
        if _force:
            self._read_outputs(force=True)
            _LOGGER.debug(' - UPDATED CACHE %s', self)
        return super().find_outputs(*args, **kwargs)

    @pipe_cache_to_file
    def _read_outputs(self, match_metadata=True, force=False):
        """Read outputs generated from this work file.

        Args:
            match_metadata (bool): ignore output without this file
                marked as their source in their metadata
            force (bool): force reread from disk

        Returns:
            (CPOutputGhost list): outputs
        """
        _LOGGER.debug('READ OUTPUTS force=%d %s', force, self)
        # _LOGGER.debug(' - CACHE FMT %s', self.cache_fmt)
        if force:
            self._update_outputs_cache()
        _outs = super()._read_outputs()
        _LOGGER.debug(' - FOUND %d OUTPUTS %s', len(_outs), self)
        if match_metadata:
            _outs = [
                _out for _out in _outs
                if _out.metadata.get('src') == self.path]
            _LOGGER.debug(' - APPLY METADATA MATCH -> %d OUTPUTS', len(_outs))
        _out_gs = [_out.to_ghost() for _out in _outs]
        # asdasd
        return _out_gs

    def _update_outputs_cache(self):
        """Rebuild outputs cache."""
        from pini import pipe
        _LOGGER.debug(' - UPDATING CACHE')
        if pipe.MASTER == 'disk':
            _LOGGER.debug(' - REREAD ENTITY/WORK_DIR CACHES')
            self.entity.find_outputs(force=True)
            self.work_dir.find_outputs(force=True)
            _LOGGER.debug(' - REREAD ENTITY/WORK_DIR CACHES COMPLETE')

            # Update seq disk caches
            _seq_dirs = self.entity.find_output_seq_dirs(
                ver_n=self.ver_n, tag=self.tag, task=self.task)
            _LOGGER.debug(
                ' - FOUND %d VERSION OUTPUT SEQ DIRS %s', len(_seq_dirs),
                self.entity)
            for _seq_dir in _seq_dirs:
                _LOGGER.debug(' - CHECKING %s', _seq_dir)
                _out_seqs = _seq_dir.find_outputs(force=True)
                _LOGGER.debug(
                    ' - FOUND %d SEQS %s', len(_out_seqs), _seq_dir)
            _LOGGER.debug(' - UPDATED CACHES %s', self)
        elif pipe.MASTER == 'shotgrid':
            self.entity.find_outputs(force=True)
        else:
            raise ValueError(pipe.MASTER)

    def find_vers(self, force=False):
        """Find version of this work file.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPWork list): versions
        """
        if force:
            self.work_dir.find_works(force=True)
        return super().find_vers()

    def mtime(self):
        """Obtain save time from this work's metadata.

        Returns:
            (int): save time
        """
        return self.metadata.get('mtime')

    def nice_size(self, catch=False):
        """Obtain readable size for this work file.

        Args:
            catch (bool): no error on missing file

        Returns:
            (str): readable size
        """
        return nice_size(self.metadata.get('size', 0))

    @pipe_cache_result
    def obt_image(self, force=False):
        """Obtain image for this work file.

        Args:
            force (bool): recache image

        Returns:
            (File|None): image (if any)
        """
        if self.image.exists():
            return self.image
        return None

    def owner(self):
        """Obtain owner of this file.

        Returns:
            (str): owner
        """
        return (
            self._owner_from_user() or
            self.metadata.get('owner') or
            self.metadata.get('user'))

    @functools.wraps(CPWork.save)
    def save(self, result='this', update_outputs=True, **kwargs):
        """Save this work.

        Args:
            result (str): what result to return
                this - this work file (CPWork)
                bkp - backup file (CPWorkBkp)
            update_outputs (bool): update workfile outputs on save (disable
                for save preceeding a publish)

        Returns:
            (CPWork): work file
        """
        _LOGGER.info('SAVE %s result=%s', self, result)
        from pini import pipe
        from .. import cache

        # Check whether entity + work_dir need updating
        assert isinstance(self.work_dir, cache.CCPWorkDir)
        _new_ety = self.entity not in self.job.entities
        _new_work_dir = self.work_dir not in self.entity.work_dirs
        _LOGGER.debug('SAVE new_entity=%d new_work_dir=%d %s',
                      _new_ety, _new_work_dir, self)
        _LOGGER.debug(' - ENTITY new=%d %s', _new_ety, self.entity)
        _LOGGER.debug(' - WORK DIR new=%d %s', _new_work_dir, self.work_dir)

        _bkp = super().save(**kwargs)
        self._exists = True
        assert File(self).exists()
        assert self.exists()
        self._read_metadata(force=True)

        # Update entity + work dir
        if _new_ety:
            self.entity = self.job.obt_entity(self.entity)
            _LOGGER.debug(
                ' - UPDATED ENTITY %s %s', self.entity, nice_id(self.entity))
        _LOGGER.debug(' - CUR ETY %s', pipe.CACHE.cur_entity)
        _LOGGER.debug(' - THIS ETY %s', self.entity)
        if _new_work_dir:
            self.work_dir = self.entity.obt_work_dir(self.work_dir)
            _LOGGER.debug(
                ' - UPDATED WORK DIR %s %s', self.work_dir, [
                    nice_id(_work_dir)
                    for _work_dir in self.entity.work_dirs])
        _LOGGER.debug(' - CUR WORK DIR %s', pipe.CACHE.cur_work_dir)

        # Update cache on work dir
        assert isinstance(self.work_dir, cache.CCPWorkDir)
        _works = self.work_dir.find_works(force=True)
        _LOGGER.debug(' - WORKS %d %s', len(_works), _works)
        assert self in _works
        _this_work = self.work_dir.obt_work(self)
        _LOGGER.debug(' - THIS WORK %s', _this_work)
        _LOGGER.debug(' - CUR WORK %s', pipe.CACHE.cur_work)

        # Reread outputs
        if update_outputs:
            self.find_outputs(force=True)

        # Return result
        if result == 'this':
            _val = _this_work
        elif result == 'bkp':
            _val = _bkp
        else:
            raise ValueError(result)
        return _val

    def set_metadata(self, data):
        """Set work file metadata.

        Args:
            data (dict): metadata to apply
        """
        super().set_metadata(data)
        self._read_metadata(force=True)

    def update_outputs(self, update_helper=True):
        """To be called when outputs are added.

        If the PiniHelper is active then this is updated (which updates the
        disk cache), otherwise the disk cache is just updated directly.

        Args:
            update_helper (bool): switch helper back to work tab to
                show new outputs
        """
        from pini.tools import helper
        _LOGGER.info('UPDATE OUTPUTS %s image=%d', self, self.image.exists())

        self._read_outputs(force=True)
        if self.image.exists():
            _LOGGER.info(' - REREADING IMAGE %s', self.image)
            helper.obt_pixmap(self.image, force=True)

        # Update helper
        if helper.is_active():
            _helper = helper.DIALOG
            _helper.ui.WWorks.redraw(force=True)
            if update_helper:
                _helper.jump_to(self)
