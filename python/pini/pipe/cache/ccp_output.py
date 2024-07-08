"""Tools for managing cacheable output objects."""

import logging
import operator
import sys

from pini.utils import (
    single, register_custom_yaml_handler, Seq, is_pascal, File, EMPTY)

from .ccp_utils import pipe_cache_to_file, pipe_cache_on_obj
from ..cp_output import (
    CPOutput, CPOutputSeq, CPOutputVideo, CPOutputBase, CPOutputSeqDir)

_LOGGER = logging.getLogger(__name__)


class CCPOutputBase(CPOutputBase):
    """Base class for any caching output object."""

    base = None
    dir = None
    extn = None

    @property
    def cache_fmt(self):
        """Build cache path format string.

        Returns:
            (str): cache format
        """
        return '{dir}/.pini/{base}_{extn}_{{func}}.yml'.format(
            dir=self.dir, base=self.base, extn=self.extn)

    @property
    def content_type(self):  # pylint: disable=too-many-branches
        """Obtain content type for this output (eg. ShadersMa, RigMa, Video).

        (NOTE: content type should be pascal)

        Returns:
            (str): content type name
        """
        _content_type = self.metadata.get('content_type')
        if _content_type:
            return _content_type

        _pub_type = self.metadata.get('publish_type')
        if self.extn == 'ma':
            if 'vrmesh' in self.metadata:
                _c_type = 'VrmeshMa'
            elif 'shd_yml' in self.metadata:
                _c_type = 'ShadersMa'
            elif _pub_type == 'CMayaModelPublish':
                _c_type = 'ModelMa'
            elif _pub_type == 'CMayaBasicPublish' and self.pini_task == 'rig':
                _c_type = 'RigMa'
            else:
                _c_type = 'BasicMa'
        elif self.extn == 'mb':
            _c_type = 'BasicMb'
        elif self.extn == 'rs':
            _c_type = 'RedshiftProxy'
        elif isinstance(self, Seq):
            if self.extn == 'obj':
                _c_type = 'ObjSeq'
            elif self.nice_type == 'blast':
                _c_type = 'Blast'
            elif self.nice_type == 'render':
                _c_type = 'Render'
            else:
                raise ValueError(self.path, _pub_type, self.nice_type)
        elif self.extn in ('mov', 'mp4'):
            _c_type = 'Video'
        else:
            _c_type = self.extn.capitalize()
        assert is_pascal(_c_type) or _c_type[0].isdigit()
        return _c_type

    @pipe_cache_on_obj
    def get_metadata(self, force=False, data=None):
        """Get metadata for this output.

        Args:
            force (bool): force reread from disk
            data (dict): force apply metadata
                (update cache with this data)

        Returns:
            (dict): metadata
        """
        _LOGGER.log(9, 'GET METADATA %s', self)
        return data or super(CCPOutputBase, self).get_metadata()

    def set_metadata(self, data, mode='replace', force=True):
        """Set metadata for this output.

        Args:
            data (dict): metadata to apply
            mode (str): update mode (replace/add)
            force (bool): replace existing metadata without confirmation
        """
        super(CCPOutputBase, self).set_metadata(data, mode=mode, force=force)
        self.get_metadata(force=True)

    def find_rep(self, task=None, content_type=None, extn=None, catch=True):
        """Find alternative representations of this output.

        Args:
            task (str): filter by task
            content_type (str): filter by content type
            extn (str): filter by extension
            catch (bool): no error if fail to match a single rep

        Returns:
            (CPOutput): alternative representation
        """
        _reps = self.find_reps(task=task, extn=extn, content_type=content_type)
        return single(_reps, catch=catch)

    def find_reps(self, task=None, content_type=None, extn=None):
        """Find different representation of this reference.

        eg. model ma publish <=> lookdev ass.gz standin

        These are other outputs which this output can be swapped with.

        Args:
            task (str): filter by task
            content_type (str): filter by content type
            extn (str): filter by extension

        Returns:
            (CPOutput list): representations
        """
        _reps = []
        for _rep in self._read_reps():
            if extn and _rep.extn != extn:
                continue
            if task and task not in (_rep.task, _rep.pini_task):
                continue
            if content_type and _rep.content_type != content_type:
                continue
            _reps.append(_rep)
        return _reps

    def _read_reps(self):
        """Find different representations of this outputs.

        eg. model ma publish <=> lookdev ass.gz standin

        These are other outputs which this output can be swapped with.

        Returns:
            (CPOutput list): representations
        """
        _LOGGER.debug('FIND REPS %s', self)
        _LOGGER.debug(' - TASK %s', self.task)
        _LOGGER.debug(' - EXTN %s', self.extn)

        _reps = []

        # Add model/rig publishes
        if self.extn in ('ma', 'mb', 'gz'):
            _LOGGER.debug(' - LOOKING FOR PUBLISHES')
            for _task in ['model', 'rig']:
                if _task in (self.task, self.pini_task):
                    continue
                _pub = self.entity.find_publish(
                    ver_n='latest', tag=self.tag, versionless=False,
                    task=_task, catch=True)
                _LOGGER.debug(' - CHECKING PUBLISH task=%s %s', _task, _pub)
                if _pub:
                    _reps.append(_pub)

        # Add ass.gz for model refs
        if self.pini_task in ('model', 'rig'):
            _ass = self.entity.find_output(
                type_='ass_gz', ver_n='latest', tag=self.tag, catch=True)
            if _ass:
                _reps.append(_ass)

        # Add vrmesh
        if self.pini_task in ('model', ):
            _vrm = self.entity.find_output(
                extn='ma', tag=self.tag, type_='publish', ver_n='latest',
                content_type='VrmeshMa', catch=True)
            if _vrm:
                _LOGGER.debug(' - FOUND VRMESH %s', _vrm)
                _reps.append(_vrm)

        if self.content_type == 'VrmeshMa':
            _shds = self.entity.find_output(
                extn='ma', tag=self.tag, type_='publish', ver_n=self.ver_n,
                content_type='ShadersMa', catch=True)
            if _shds:
                _reps.append(_shds)

        return _reps

    def to_file(self, **kwargs):
        """Map this output to a file with the same attributes.

        Returns:
            (File): file
        """
        raise NotImplementedError


class CCPOutput(CPOutput, CCPOutputBase):
    """Represents an output on disk with built in caching."""

    get_metadata = CCPOutputBase.get_metadata
    set_metadata = CCPOutputBase.set_metadata
    _exists = True

    yaml_tag = '!CCPOutput'

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
        from pini import pipe

        _LOGGER.debug('FROM YAML cls=%s loader=%s node=%s', cls, loader, node)
        del loader  # for linter
        _path = pipe.map_path(node.value)
        _LOGGER.debug(' - PATH %s', _path)

        # Allocate work dir
        _work_dir_c = None
        _work_dir = pipe.to_work_dir(_path)
        if _work_dir:
            _work_dir_c = pipe.CACHE.obt_work_dir(_work_dir)
        _LOGGER.debug(' - WORK DIR %s', _work_dir_c)

        # Allocate entity
        _ety_c = None
        if _work_dir_c:
            _ety_c = _work_dir_c.entity
        else:
            _ety = pipe.to_entity(_path)
            _ety_c = pipe.CACHE.obt_entity(_ety)
        _LOGGER.debug(' - ENTITY %s', _ety_c)

        _out_c = cls(_path, work_dir=_work_dir_c, entity=_ety_c)
        _LOGGER.debug(' - OUT %s', _out_c)
        return _out_c

    def delete(self, force=False):  # pylint: disable=arguments-differ
        """Delete this output file and update parent caches.

        Args:
            force (bool): delete without confirmation
        """
        CPOutput.delete(self, force=force)
        _parent = self.work_dir or self.entity
        _parent.find_outputs(force=True)
        self._exists = False

    def exists(self, force=False):  # pylint: disable=arguments-differ
        """Test whether this output exists.

        Args:
            force (bool): force read exists from disk

        Returns:
            (bool): whether exists
        """
        if force:
            self._exists = File(self).exists()
        return self._exists

    def find_lookdev_shaders(self, tag=EMPTY):
        """Find matching lookdev for this output.

        This is used to find a lookdev publish to attach to an abc export.
        Any lookdev publish in the same asset should be allowed to attach to
        to this output.

        Lookdevs are matched in this order:
         - matching tag
         - default tag
         - any tag

        Args:
            tag (str): force tag to attach

        Returns:
            (CPOutput): matching lookdev
        """
        from pini import pipe
        _LOGGER.debug('FIND LOOKDEV %s', self)

        # Ignore ouputs without lookdev
        _pub_type = self.metadata.get('publish_type')
        _LOGGER.debug(' - PUB TYPE %s', _pub_type)
        if _pub_type in ('CMayaLookdevPublish', ):
            return None
        _out_type = self.metadata.get('type')
        if _out_type in ('CPCacheableCam', ):
            return None

        # Find asset
        _asset = _out = None
        if self.profile == 'asset':
            _out = self
            _asset = self.entity
        if not _asset:
            _asset_path = pipe.map_path(self.metadata.get('asset'))
            if _asset_path:
                _out = pipe.to_output(_asset_path)
                _out = pipe.CACHE.obt(_out)
                _asset = _out.entity
        if not _asset:
            _LOGGER.debug(' - NO ASSET FOUND')
            return None
        _LOGGER.debug(' - ASSET %s', _asset)

        # Find lookdevs
        _lookdevs = _out.entity.find_publishes(
            content_type='ShadersMa', tag=tag, ver_n='latest')
        _LOGGER.debug(' - LOOKDEVS %d %s', len(_lookdevs), _lookdevs)
        if not _lookdevs:
            return None

        # Match to tag
        _tags = sorted(
            {_lookdev.tag for _lookdev in _lookdevs}, key=pipe.tag_sort)
        _default_tag = self.job.cfg['tokens']['tag']['default']
        if _out.tag in _tags:
            _tag = _out.tag
        elif _default_tag in _tags:
            _tag = _default_tag
        else:
            _tag = _tags[0]
        _LOGGER.debug(' - APPLY TAG FILTER %s %s', _tag, _tags)
        _lookdevs = [_lookdev for _lookdev in _lookdevs if _lookdev.tag == _tag]
        _LOGGER.debug(' - LOOKDEVS %d %s', len(_lookdevs), _lookdevs)
        if len(_lookdevs) == 1:
            return single(_lookdevs)

        # Return most recent
        _LOGGER.debug(' - APPLYING DATE SORT')
        _lookdevs.sort(key=operator.methodcaller('mtime'))
        _recent = _lookdevs[-1]
        _LOGGER.debug(' - RECENT %s', _recent)

        return _recent


class CCPOutputVideo(CPOutputVideo, CCPOutput):  # pylint: disable=too-many-ancestors
    """Represents an output video on disk with built in caching."""

    get_metadata = CCPOutput.get_metadata
    set_metadata = CCPOutput.set_metadata
    delete = CCPOutput.delete
    exists = CCPOutput.exists


class CCPOutputSeqDir(CPOutputSeqDir):
    """Represents an output sequence directory.

    This object is used to avoid reread long lists of frames. The first
    time the dir is searched for sequences, the result is cached and
    is only reread if the cache is rebuilt

    Rebuilding is triggered by the CCPWorkFile.find_outputs list being
    force refreshed (since this object is not easily accessible).
    """

    @property
    def cache_fmt(self):
        """Obtain cache format string for storing image dir data.

        Returns:
            (str): cache format
        """
        return self.to_file('.pini/{func}_%s.pkl' % sys.platform).path

    def find_outputs(self, force=False):
        """Find outputs within this sequence directory.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutputSeq list): outputs
        """
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)
        if force:
            self.find_seqs(force=True)
        _outs = self._read_outputs(force=force)
        _LOGGER.debug(' - FIND OUTPUTS force=%d n_outs=%d %s', force,
                      len(_outs), self)
        return _outs

    @pipe_cache_on_obj
    def _read_outputs(
            self, output_seq_class=None, output_video_class=None, force=False):
        """Read outputs within this sequence directory.

        Args:
            output_seq_class (class): override output seq class
            output_video_class (class): override output video class
            force (bool): force rebuild output objects

        Returns:
            (CCPOutputSeq list): outputs
        """
        _LOGGER.debug('READ OUTPUTS %s', self)
        _output_seq_class = output_seq_class or CCPOutputSeq
        _output_video_class = output_video_class or CCPOutputVideo
        _out_seqs = super(CCPOutputSeqDir, self)._read_outputs(
            output_seq_class=_output_seq_class,
            output_video_class=_output_video_class)
        _LOGGER.debug(' - READ OUTPUTS %s seqs=%d', self, len(_out_seqs))
        return _out_seqs

    @pipe_cache_to_file
    def find_seqs(self, force=False, **kwargs):
        """Find file sequences within this dir.

        Args:
            force (bool): force reread from disk

        Returns:
            (Seq|File list): matching seqs
        """
        assert not kwargs
        _seqs = super(CCPOutputSeqDir, self).find_seqs(
            include_files=True, depth=2)
        _LOGGER.debug('FIND SEQS force=%d n_seqs=%d %s', force,
                      len(_seqs), self)
        return _seqs


class CCPOutputSeq(CPOutputSeq, CCPOutputBase):
    """Represents an output sequence on disk with built in caching."""

    get_metadata = CCPOutputBase.get_metadata
    set_metadata = CCPOutputBase.set_metadata

    def delete(self, force=False):  # pylint: disable=arguments-differ
        """Delete this output seq and update caches on parent entity.

        Args:
            force (bool): delete files without confirmation
        """
        from pini import pipe
        from .. import cache
        super(CCPOutputSeq, self).delete(force=force)
        if pipe.MASTER == 'disk':
            self.to_dir().find_seqs(force=True)
            assert isinstance(self.entity, cache.CCPEntity)
            self.entity.find_outputs(force=True)
        elif pipe.MASTER == 'shotgrid':
            from pini.pipe import shotgrid
            _pub_file = shotgrid.SGC.find_pub_file(self)
            _pub_file.omit()
            self.job.find_outputs(force=True)
        else:
            raise ValueError(pipe.MASTER)

    @pipe_cache_on_obj
    def mtime(self):
        """Obtain mtime for this sequence.

        Returns:
            (float): mtime
        """
        _metadata_mtime = self.metadata.get('mtime')
        if _metadata_mtime:
            return _metadata_mtime
        return super(CCPOutputSeq, self).mtime()

    @pipe_cache_on_obj
    def owner(self):
        """Obtain owner of this sequence.

        Returns:
            (str): owner
        """
        _metadata_owner = self.metadata.get('owner')
        if _metadata_owner:
            return _metadata_owner
        return super(CCPOutputSeq, self).owner()

    def _read_frames(self):
        """Read list of frames.

        This is cached and managed by the parent dir.

        Returns:
            (int list): frames
        """
        from pini import pipe
        _LOGGER.info('READ FRAMES %s', self.path)

        # Need to update cache, which is stored on parent dir
        if pipe.MASTER == 'disk':
            _dir = self.to_dir()
            _LOGGER.info(' - DIR %s', _dir.path)
            _seqs = [_path for _path in _dir.find_seqs(force=True)
                     if isinstance(_path, Seq) and
                     _path.path == self.path]
            _LOGGER.info(' - SEQS %d %s', len(_seqs), _seqs)
            if not _seqs:
                raise OSError(
                    'Seq no longer exists (need to update cache on '
                    'parent) '+self.path)
            _seq = single(_seqs)
            _frames = _seq.frames
        elif pipe.MASTER == 'shotgrid':
            _frames = self._read_frames_disk()
        else:
            raise ValueError(pipe.MASTER)
        return _frames

    @pipe_cache_to_file
    def _read_frames_disk(self):
        """Read frames from disk and cache the result.

        (NOTE: this is only used on shotgrid-centric pipelines).

        Returns:
            (int list): frames
        """
        return super(CCPOutputSeq, self)._read_frames()

    def to_dir(self):  # pylint: disable=arguments-differ
        """Obtain this output sequence's parent dir.

        Returns:
            (CCPOutputSeqDir): output sequence dir
        """
        assert self._dir
        assert isinstance(self._dir, CCPOutputSeqDir)
        return self._dir

    @pipe_cache_to_file
    def to_res(self):
        """Obtain res for this image sequence.

        Returns:
            (tuple): width/height
        """
        return super(CCPOutputSeq, self).to_res()


register_custom_yaml_handler(CCPOutput)
