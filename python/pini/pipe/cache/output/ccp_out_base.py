"""Tools for managing cacheable output objects."""

import logging

from pini import pipe
from pini.utils import single, Seq, is_pascal, File, EMPTY

from . import ccp_out_ghost
from ..ccp_utils import pipe_cache_on_obj
from ... import elem

_LOGGER = logging.getLogger(__name__)

OUTPUT_MEDIA_CONTENT_TYPES = ['Render', 'Blast', 'Plate', 'Video']


class CCPOutputBase(elem.CPOutputBase):
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

        _cache_extn = 'yml' if pipe.VERSION <= 4 else 'pkl'
        return (
            f'{self.dir}/.pini/pipe_{pipe.VERSION:d}/'
            f'{self.base}_{self.extn}_{{func}}.{_cache_extn}')

    @property
    def content_type(self):  # pylint: disable=too-many-branches,too-many-statements
        """Obtain content type for this output (eg. ShadersMa, RigMa, Video).

        (NOTE: content type should be pascal)

        Returns:
            (str): content type name
        """
        _content_type = self.metadata.get('content_type')
        if _content_type:
            return _content_type

        _pub_type = self.metadata.get('publish_type')
        _handler = self.metadata.get('handler')

        if self.extn in ('abc', 'fbx'):
            _type = _handler or self.metadata.get('type')   # Legacy 18/10/24
            _extn_type = self.extn.capitalize()
            if _type == 'CPCacheableCam':
                _c_type = f'Camera{_extn_type}'
            elif _type == 'CPCacheableRef':
                _c_type = f'Pipe{_extn_type}'
            else:
                _c_type = _extn_type

        elif self.extn == 'ma':
            if 'vrmesh' in self.metadata:
                _c_type = 'VrmeshMa'
            elif 'shd_yml' in self.metadata:
                _c_type = 'ShadersMa'
            elif _handler == 'CMayaModelPublish':
                _c_type = 'ModelMa'
            elif _handler == 'CMayaBasicPublish' and self.pini_task == 'rig':
                _c_type = 'RigMa'
            else:
                _c_type = 'BasicMa'

        elif self.extn == 'mb':
            if _handler == 'CMayaCurvesCache':
                _c_type = 'CurvesMb'
            else:
                _c_type = 'BasicMb'

        elif self.extn == 'rs':
            _c_type = 'RedshiftProxy'

        elif isinstance(self, Seq):
            if self.extn == 'obj':
                _c_type = 'ObjSeq'
            elif self.extn == 'vdb':
                _c_type = 'VdbSeq'
            elif self.basic_type == 'blast':
                _c_type = 'Blast'
            elif self.basic_type == 'render':
                _c_type = 'Render'
            elif self.basic_type == 'plate':
                _c_type = 'Plate'
            elif self.basic_type == 'texture':
                _c_type = 'Texture'
            else:
                raise ValueError(self.path, _pub_type, self.basic_type)

        elif self.extn in ('mov', 'mp4'):
            _c_type = 'Video'
        elif self.extn in ('jpg', 'exr') and isinstance(self, File):
            _c_type = 'Image'
        elif self.extn == 'gz' and self.filename.endswith('.ass.gz'):
            _c_type = 'AssArchive'
        else:
            _c_type = self.extn.capitalize()

        assert is_pascal(_c_type) or _c_type[0].isdigit()
        return _c_type

    @property
    def handler(self):
        """Obtain export handler for this output.

        Returns:
            (str): export handler (eg. CMayaModelPublish/CPCacheableRef)
        """
        return (
            self.metadata.get('handler') or
            self.metadata.get('type'))  # Legacy 18/10/24 (from Cache)

    @property
    def range_(self):
        """Obtain range for this output.

        Returns:
            (tuple|None): range (if any)
        """
        return self.metadata.get('range')

    @property
    def src(self):
        """Obtain source work file for this output.

        Returns:
            (str): path to source work file
        """
        return self.metadata.get('src')

    @property
    def src_ref(self):
        """Obtain source reference path for this output.

        eg. path to rig for an abc

        Returns:
            (str): source reference path
        """
        return (
            self.metadata.get('src_ref') or
            self.metadata.get('asset'))  # Legacy 18/10/24 (from Cache)

    @property
    def stream(self):
        """Obtain stream path for this output.

        This is the path to version zero of this output.

        Returns:
            (str): version zero path
        """
        return self.to_stream()

    @property
    def updated_at(self):
        """Obtain time when this output was last updated.

        Returns:
            (float): update time (in seconds since epoch)
        """
        return self.metadata.get('mtime')

    @property
    def updated_by(self):
        """Obtain owner of this output.

        Returns:
            (str): output owner
        """
        return self.metadata.get('owner') or self.owner()  # pylint: disable=no-member

    @pipe_cache_on_obj
    def get_metadata(self, data=None, force=False):
        """Get metadata for this output.

        Args:
            data (dict): force apply metadata
                (update cache with this data)
            force (bool): force reread from disk

        Returns:
            (dict): metadata
        """
        _LOGGER.debug('GET METADATA %s', self)
        return data or super().get_metadata()

    def set_metadata(self, data, force=True, **kwargs):
        """Set metadata for this output.

        Args:
            data (dict): metadata to apply
            force (bool): replace existing metadata without confirmation
        """
        super().set_metadata(data, force=force, **kwargs)
        self.get_metadata(force=True)

    def find_rep(self, task=None, catch=True, **kwargs):
        """Find alternative representations of this output.

        Args:
            task (str): filter by task
            catch (bool): no error if fail to match a single rep

        Returns:
            (CPOutput): alternative representation
        """
        _reps = self.find_reps(task=task, **kwargs)
        return single(_reps, catch=catch)

    def find_reps(self, task=None, **kwargs):
        """Find different representation of this reference.

        eg. model ma publish <=> lookdev ass.gz standin

        These are other outputs which this output can be swapped with.

        Args:
            task (str): filter by task

        Returns:
            (CPOutput list): representations
        """
        _LOGGER.debug('FIND REPS %s', self)
        _reps = []
        for _rep in self._read_reps():
            if not pipe.passes_filters(_rep, task=task, **kwargs):
                continue
            _reps.append(_rep)
        return _reps

    @pipe_cache_on_obj
    def _read_reps(self):
        """Find different representations of this outputs.

        eg. model ma publish <=> lookdev ass.gz standin

        These are other outputs which this output can be swapped with.

        Returns:
            (CPOutput list): representations
        """
        _LOGGER.debug('READ REPS %s', self)
        _LOGGER.debug(' - TASK %s', self.task)
        _LOGGER.debug(' - EXTN %s', self.extn)

        _reps = []
        _reps += self._read_reps_alt_tasks()
        _reps += self._read_reps_alt_fmts()

        # Add ass.gz
        if self.pini_task in ('model', 'rig'):
            _LOGGER.debug(
                ' - CHECKING FOR AssArchive tag=%s ety=%s', self.tag,
                self.entity)
            _ass = self.entity.find_output(
                content_type='AssArchive', ver_n='latest', tag=self.tag,
                catch=True)
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

    def _read_reps_alt_tasks(self):
        """Read alternative task reps.

        Returns:
            (CPOutput list): task reps
        """
        _reps = []
        if (
                self.profile == 'asset' and
                self.extn in ('ma', 'mb', 'gz', 'abc', 'fbx')):
            _LOGGER.debug(' - LOOKING FOR PUBLISHES')
            for _task in ['model', 'rig']:
                if _task in (self.task, self.pini_task):
                    continue
                _pub_g = self.entity.find_publish(
                    ver_n='latest', tag=self.tag, versionless=False,
                    task=_task, extn='ma', catch=True)
                _LOGGER.debug(' - CHECKING PUBLISH task=%s %s', _task, _pub_g)
                if _pub_g:
                    _pub = pipe.CACHE.obt(_pub_g)
                    _reps.append(_pub)
        return _reps

    def _read_reps_alt_fmts(self):
        """Read alternative format reps.

        Returns:
            (CPOutput list): format reps
        """
        _LOGGER.debug(' - READ REPS ALT FMTS')
        _reps = []
        if (
                self.profile == 'asset' and
                self.extn in ('ma', 'mb', 'gz', 'abc', 'fbx')):
            if self.pini_task == 'model':
                _LOGGER.debug(' - CHECKING FOR EXTNS')
                for _extn in ('abc', 'fbx', 'ma'):
                    if _extn == self.extn:
                        continue
                    for _dcc in (self.dcc_, None, EMPTY):
                        _pub = self.entity.find_output(
                            ver_n=self.ver_n, tag=self.tag, versionless=False,
                            task=self.task, extn=_extn, dcc_=_dcc, catch=True)
                        _LOGGER.debug('   - EXTN %s %s', _extn, _pub)
                        if _pub:
                            _reps.append(_pub)
                            break
        return _reps

    @pipe_cache_on_obj
    def find_work(self):
        """Find this output's work file.

        Returns:
            (CCPWork): source work file
        """
        _work = super().find_work()
        if not _work:
            return None
        return pipe.CACHE.obt_work(_work, catch=True)

    def is_media(self):
        """Test whether this output is media.

        Returns:
            (bool): whether media (eg. render/blast)
        """
        return self.content_type in OUTPUT_MEDIA_CONTENT_TYPES

    def set_latest(self, latest: bool):
        """Set whether this output is the latest in its version stream.

        Args:
            latest (bool): whether this is latest version
        """
        self._latest = latest

    def to_file(self, **kwargs):
        """Map this output to a file with the same attributes.

        Returns:
            (File): file
        """
        raise NotImplementedError

    def to_ghost(self):
        """Obtain ghost representation of this output for caching.

        The ghost object contains all output metadata but has no hooks
        to allow interaction with the pipeline.

        Returns:
            (CCPOutputGhost): ghost output for caching
        """
        # pylint: disable=no-member
        _LOGGER.debug('TO GHOST %s', self.path)
        return ccp_out_ghost.CCPOutputGhost(
            self.path, latest=self._latest, updated_at=self.updated_at,
            template=self.template.source.pattern, type_=self.type_,
            task=self.task, pini_task=self.pini_task, ver_n=self.ver_n,
            step=self.step, output_name=self.output_name, shot=self.shot,
            sequence=self.sequence, asset=self.asset, dcc_=self.dcc_,
            updated_by=self.updated_by, asset_type=self.asset_type,
            content_type=self.content_type, job=self.job.name,
            output_type=self.output_type, tag=self.tag,
            basic_type=self.basic_type, profile=self.profile, ver=self.ver,
            range_=self.range_, submittable=self.submittable,
            src=self.src, src_ref=self.src_ref, handler=self.handler,
            stream=self.to_stream(), status=self.status)
