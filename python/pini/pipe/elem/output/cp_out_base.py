"""Tools for managing the base class for all outputs."""

# pylint: disable=too-many-instance-attributes,too-many-public-methods

import copy
import logging

import lucidity

from pini import dcc
from pini.utils import EMPTY, single, strftime

from ..entity import to_entity
from ... import cp_utils

_LOGGER = logging.getLogger(__name__)

OUTPUT_FILE_TYPES = ('publish', 'cache', 'ass_gz', 'texture')
OUTPUT_VIDEO_TYPES = ('blast_mov', 'mov', 'render_mov', 'plate_mov')
OUTPUT_SEQ_TYPES = (
    'render', 'plate', 'blast', 'cache_seq', 'publish_seq', 'texture_seq')
OUTPUT_SEQ_CACHE_EXTNS = ('rs', 'vdb', 'ifd', 'obj')

STATUS_ORDER = ('cmpt', 'apr', 'lapr')


class CPOutputBase:
    """Base class for any output.

    This provides features shared between File outputs and Seq outputs.
    """

    dir = None
    path = None
    filename = None
    extn = None

    job = None
    entity = None

    _work_dir = None
    _tested_for_work_dir = False
    _cmp_key = None
    _latest = None

    profile = None
    asset_type = None
    asset = None
    shot = None
    sequence = None

    task = None
    user = None
    tag = None
    step = None
    task = None
    output_type = None
    output_name = None
    ver = None
    ver_n = None

    status = None
    dcc_ = None
    data = None
    template = None

    sg_pub_file = None

    def __init__(
            self, job=None, entity=None, work_dir=None, templates=None,
            template=None, types=None, latest=None):
        """Constructor.

        Args:
            job (CPJob): force parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            types (str list): override list of template types to test for
            latest (bool): apply static latest status of this output
        """

        # Setup job
        self.job = job
        if not self.job and entity:
            self.job = entity.job
        if not self.job and work_dir:
            self.job = work_dir.job

        # Setup entity
        self.entity = entity
        if not self.entity and work_dir:
            self.entity = work_dir.entity
        if not self.entity:
            self.entity = to_entity(self.path, job=job)
            if not self.job:
                self.job = self.entity.job
        self.profile = self.entity.profile
        assert self.job

        # Setup work dir
        self._work_dir = work_dir
        if self._work_dir:
            self.task = self._work_dir.task

        self._init_extract_data_from_templates(
            types=types or OUTPUT_FILE_TYPES,
            templates=templates, template=template)
        self._latest = latest

    def _init_extract_data_from_templates(
            self, types, templates=None, template=None, task=None):
        """Match path with a template and extract data.

        Args:
            types (str list): template types to check
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            task (str): apply task (if known)
        """
        _LOGGER.log(9, ' - EXTRACT DATA FROM TEMPLATES %s', self.path)

        # Apply templates to data. Apply single template alone to get better
        # error on fail. NOTE: sometimes the templates can fail due to data
        # not represented in the repr, eg. tokens fail to validate.
        _tmpls = self._init_extract_data_find_output_templates(
            template=template, templates=templates, types=types)
        if len(_tmpls) == 1:
            self.template = single(_tmpls)
            _LOGGER.log(9, ' - TMPL %s %s', self.template, self.template.anchor)
            _LOGGER.log(9, ' - PATH %s', self.path)
            try:
                self.data = self.template.parse(self.path)
            except lucidity.ParseError as _exc:
                _LOGGER.log(9, ' - ERROR %s', _exc)
                raise ValueError(_exc) from _exc
        else:
            try:
                self.data, self.template = lucidity.parse(self.path, _tmpls)
            except lucidity.ParseError as _exc:
                _LOGGER.log(9, ' - PATH "%s"', self.path)
                _LOGGER.log(9, ' - ERROR %s', _exc)
                raise ValueError(
                    'No output templates matched path ' + self.path) from _exc
        _LOGGER.log(9, ' - TEMPLATE %d %s', _tmpls.index(self.template),
                    self.template)

        cp_utils.validate_tokens(self.data, job=self.job)

        # Set task
        self.task = task or self.data.get('task', self.template.task)
        if not self.task:
            if self.work_dir:
                self.task = self.work_dir.task
            else:
                self.task = self.data.get('work_dir')

        # Set step
        self.step = self.data.get('step')
        if not self.step and self.work_dir:
            self.step = self.work_dir.step

        self.output_name = self.data.get('output_name')
        self.tag = self.data.get('tag')
        self.user = self.data.get('user')

        # Transfer attrs from entity
        for _attr in [
                'asset_type', 'asset', 'sequence', 'shot', 'entity_type']:
            _val = getattr(self.entity, _attr)
            self.data[_attr] = _val
            setattr(self, _attr, _val)

        self.ver = self.data.get('ver')
        self.ver_n = int(self.ver) if self.ver else None

        self.output_type = self.data.get('output_type')
        self.dcc_ = self.data.get('dcc') or self.template.dcc

    def _init_extract_data_find_output_templates(
            self, template, templates, types):
        """Find output templates to match with this output.

        Args:
            template (CPTemplate): force template to use
            templates (CPTemplate list): force list of templates to check
            types (str list): template types to check

        Returns:
            (CPTemplate list): templates to test
        """

        # Build dict of data to apply to template
        _data = {}
        _data['asset'] = self.entity.asset
        _data['asset_type'] = self.entity.asset_type
        _data['shot'] = self.entity.shot
        _data['sequence'] = self.entity.sequence
        _data['entity'] = self.entity.name
        _data['entity_path'] = self.entity.path
        _data['extn'] = self.extn
        if self.work_dir:
            _data['work_dir'] = self.work_dir.path
            _data['task'] = self.work_dir.task
            _data['step'] = self.work_dir.step
        _LOGGER.log(9, ' - DATA %s', _data)

        # Get list of templates to test
        if template:
            _tmpls = [template]
        elif templates:
            _tmpls = templates
        else:
            _tmpls = self._find_templates(types=types)
        _tmpls = [_tmpl.apply_data(**_data) for _tmpl in _tmpls]

        # Log data
        _LOGGER.log(9, ' - MATCHED %d TEMPLATES: %s', len(_tmpls), _tmpls)
        for _idx, _tmpl in enumerate(_tmpls):
            _LOGGER.log(9, ' - TEMPLATES[%d] %s', _idx, _tmpl)

        return _tmpls

    @property
    def cmp_key(self):
        """Key to use for sorting/comparison.

        Makes sure that outputs without tags are always sorted first.

        Sort by entity -> task -> dir -> tag -> filename

        Returns:
            (tuple): sort key
        """
        if not self._cmp_key:
            self._cmp_key = tuple(self._build_cmp_key())
        return self._cmp_key

    @property
    def pini_task(self):
        """Obtain mapped/pini task.

        This accomodates for different task labelling at different sites.

        eg. a surf/dev task is identified in pini as lookdev

        Returns:
            (str): pini task
        """
        from pini import pipe
        return pipe.map_task(task=self.task, step=self.step)

    @property
    def pini_ver(self):
        """Obtain which pini version this output was generated with.

        If none was written at export time, zero version is returned.

        Returns:
            (PRVersion): pini version
        """
        from pini.tools import release
        _ver = self.metadata.get('pini')
        if not _ver:
            return release.ZERO_VER
        return release.PRVersion(_ver)

    @property
    def task_label(self):
        """Obtain task label for this output.

        Returns:
            (str): task label (eg. surf/dev, modelling, plate)
        """
        if self.step:
            return f'{self.step}/{self.task}'
        if self.task:
            return self.task
        return self.type_

    def _build_cmp_key(self):
        """Build key to use for sorting/comparison.

        Returns:
            (tuple): sort key
        """
        _stream = self.to_stream()
        if self.status in STATUS_ORDER:
            _status_idx = 1 + STATUS_ORDER.index(self.status)
        else:
            _status_idx = 0
        return [_stream, _status_idx, self.ver_n]

    @property
    def metadata(self):
        """Obtain this output's metadata.

        Returns:
            (dict): metadata
        """
        _LOGGER.debug('METADATA %s', self)
        return self.get_metadata()

    @property
    def metadata_yml(self):
        """Obtain metadata yaml file for this output.

        Returns:
            (File): metadata yaml
        """
        return self.to_file(dir_=self.dir + '/.pini', extn='yml')

    @property
    def basic_type(self):
        """Obtain basic type name for this template.

        This is the template type in a simple, readable form.

        eg. render -> render
            cache_seq -> cache
            blast_mov -> blast
            mov -> render

        Returns:
            (str): nice type
        """
        return cp_utils.to_basic_type(self.type_)

    @property
    def submittable(self):
        """Test whether this output is submittable.

        ie. whether it can be submitted to shotgrid.

        Returns:
            (bool): submittable
        """
        return self._read_submittable()

    @property
    def type_(self):
        """Obtain type of this output (eg. publish/cache).

        Returns:
            (str): type name
        """
        return self.template.type_

    @property
    def work_dir(self):
        """Obtain this output's work dir (if any).

        Returns:
            (CPWorkDir|None): work dir
        """
        from pini import pipe
        if not self._work_dir and not self._tested_for_work_dir:
            try:
                self._work_dir = pipe.CPWorkDir(self.path, entity=self.entity)
            except ValueError:
                self._work_dir = None
            self._tested_for_work_dir = True
        return self._work_dir

    def add_metadata(self, **kwargs):
        """Add the given data to this output's metadata.

        eg. _out.add_metadata(fps=24, submitted=True)

        The kwargs are added to the existing metadata dict.
        """
        _LOGGER.debug('ADD METADATA %s', kwargs)
        self.set_metadata(kwargs, mode='add')

    def get_metadata(self):
        """Obtain this output's metadata.

        Returns:
            (dict): metadata
        """
        _LOGGER.debug('GET METADATA %s', self)
        _LOGGER.debug(' - METADATA YML %s', self.metadata_yml)
        _data = self.metadata_yml.read_yml(catch=True) or {}
        return _data

    def _find_templates(self, types):
        """Find templates of the given list of types.

        Args:
            types (str list): list of template types to match

        Returns:
            (CPTemplate list): matching templates
        """
        _tmpls = []
        for _type in types:
            _tmpls += self.job.find_templates(_type, profile=self.profile)
        return _tmpls

    def create_ref(self):
        """Create reference of this output in the current scene.

        Returns:
            (any): reference instance
        """
        _LOGGER.info('CREATE REF %s', self)
        if self.type_ == 'publish':
            _ns_base = self.entity.name
            _LOGGER.info(' - NAMESPACE BASE %s', _ns_base)
            _ns = dcc.get_next_namespace(base=_ns_base)
        elif self.type_ in ('cache', 'render', 'plate'):
            _ns = self.output_name
        else:
            raise ValueError(self.path)
        _LOGGER.info(' - NAMESPACE %s', _ns)
        return dcc.create_ref(self, namespace=_ns)

    def find_latest(self, catch=False):
        """Find latest version of this output.

        Args:
            catch (bool): no error if no versions found

        Returns:
            (CPOutput): latest
        """
        _vers = [_ver for _ver in self.find_vers() if _ver.ver_n]
        if not _vers:
            if catch:
                return None
            raise ValueError('No versions found ' + self.path)
        return _vers[-1]

    def find_next(self):
        """Get next unused version.

        Returns:
            (CPOutputBase): next version
        """
        _latest = self.find_latest(catch=True)
        if not _latest:
            _ver_n = 1
        else:
            _ver_n = _latest.ver_n + 1
        return self.to_output(ver_n=_ver_n)

    def find_ver(self, ver_n):
        """Find the given version.

        Args:
            ver_n (int): match version number

        Returns:
            (CPOutput): matching output version
        """
        return single(self.find_vers(ver_n=ver_n))

    def find_vers(self, ver_n=EMPTY):
        """Find versions of this output.

        Args:
            ver_n (int): filter by version number

        Returns:
            (CPOutput list): versions
        """
        _LOGGER.debug('FIND VERS %s', self)
        from pini import pipe

        _kwargs = {'output_type': self.output_type,
                   'output_name': self.output_name,
                   'tag': self.tag,
                   'type_': self.type_,
                   'extn': self.extn,
                   'stream': self.to_stream(),
                   'ver_n': ver_n}
        _LOGGER.debug(' - KWARGS %s', _kwargs)

        # Try as work dir output
        try:
            _work_dir = self.work_dir or pipe.CPWorkDir(self.path)
        except ValueError:
            _ety = self.entity or pipe.to_entity(self.path)
            _LOGGER.debug(' - ENTITY SEARCH %s', _ety)
            _vers = _ety.find_outputs(task=self.task, **_kwargs)
        else:
            _LOGGER.debug(' - WORK DIR SEARCH %s', _work_dir)
            _vers = _work_dir.find_outputs(**_kwargs)

        return sorted(_vers, key=ver_sort)

    def find_work(self):
        """Find this output's work file.

        Returns:
            (CPWork): source work file
        """
        from pini import pipe
        _src = self.metadata.get('src')
        if not _src:
            return None
        return pipe.to_work(_src)

    def is_latest(self):
        """Check whether this is the latest version.

        Returns:
            (bool): whether latest
        """
        _LOGGER.debug('IS LATEST %s', self)
        if self.ver_n is None:
            return True
        if self._latest is not None:
            return self._latest
        _vers = [_ver for _ver in self.find_vers() if _ver.ver_n]
        if not _vers:
            return False
        _latest = _vers[-1]
        _LOGGER.debug(' - LATEST %s', _latest)
        return self == _latest

    def _read_submittable(self):
        """Test whether this output is submittable.

        ie. whether it can be submitted to shotgrid.

        Returns:
            (bool): submittable
        """
        from pini import pipe
        _LOGGER.debug('SUBMITTABLE %s', self)
        if not pipe.SUBMIT_AVAILABLE:
            _LOGGER.debug(' - SUBMIT NOT AVALIABLE')
            return False
        if isinstance(self, pipe.CPOutputVideo):
            _LOGGER.debug(' - IS VIDEO')
            return True
        _LOGGER.debug(' - TYPE %s', self.type_)
        return self.type_ in ['render', 'plate', 'blast']

    def set_latest(self, latest):
        """Set latest status of this output.

        Args:
            latest (bool): latest status
        """
        assert isinstance(latest, bool)
        self._latest = latest

    def set_metadata(self, data, mode='replace', bkp=False, force=True):
        """Set metadata for this output.

        Args:
            data (dict): metadata to apply
            mode (str): how to set the metadata
                replace - overwrite existing metadata
                add - update existing metadata with this metadata
            bkp (bool): backup metadata file on save
            force (bool): replace existing metadata without confirmation
        """
        _LOGGER.debug('SET METADATA mode=%s', mode)
        if bkp:
            self.metadata_file.bkp()
        if mode == 'replace':
            _data = data
        elif mode == 'add':
            _data = self.metadata
            _data.update(data)
        else:
            raise ValueError(mode)
        _LOGGER.debug(' - APPLIED METADATA', _data)
        self.metadata_yml.write_yml(_data, force=True)

    def strftime(self, fmt=None):
        """Get mtime as formatted string.

        Args:
            fmt (str): format to apply

        Returns:
            (str): formatted time string
        """
        return strftime(fmt=fmt, time_=self.updated_at)  # pylint: disable=no-member

    def to_file(self, **kwargs):
        """Map this output to a file with the same attributes.

        Returns:
            (File): file
        """
        raise NotImplementedError

    def to_output(self, template=None, **kwargs):
        """Map to a new output object overriding the given parameters.

        Args:
            template (CPTemplate): override template

        Returns:
            (CPOutput): output
        """
        from pini import pipe

        _LOGGER.debug('TO OUTPUT tmpl=%s kwargs=%s', template, kwargs)

        # Obtain template
        _tmpl = template or self.template.source
        if isinstance(_tmpl, str):
            _has_key = {'tag': bool('tag' in kwargs or self.tag)}
            if 'output_name' in kwargs:
                _has_key['output_name'] = bool(kwargs['output_name'])
            _LOGGER.debug(' - HAS KEY %s', _has_key)
            _tmpl = self.entity.find_template(
                _tmpl, dcc_=kwargs.get('dcc_', self.dcc_),
                has_key=_has_key)
        assert isinstance(_tmpl, pipe.CPTemplate)
        _LOGGER.debug(' - TEMPLATE %s', _tmpl)

        # Build data
        _data = copy.copy(self.data)
        _data.update(kwargs)
        if self.work_dir:
            _work_dir = self.work_dir.to_work_dir(**kwargs)
            _data['work_dir'] = _work_dir.path
            _LOGGER.debug(' - WORK DIR %s', _work_dir)
        if 'ver_n' in _data:
            _ver_pad = self.job.cfg['tokens']['ver']['len']
            _data['ver'] = str(_data.pop('ver_n')).zfill(_ver_pad)
        if 'entity_path' not in _data:
            _data['entity_path'] = self.entity.path
        _LOGGER.debug(' - DATA %s', _data)

        _path = _tmpl.format(**_data)
        _LOGGER.debug(' - PATH %s', _path)
        _out = pipe.to_output(_path)
        return _out

    def to_stream(self):
        """Obtain path to stream.

        This is the path to version zero on this output's stream.

        eg. test_blah_v010 -> test_blah_v000

        Returns:
            (str): path to stream version zero
        """
        _data = copy.copy(self.data)
        if 'ver' in _data:
            _data['ver'] = '0' * len(_data['ver'])
        return self.template.format(_data)

    def to_work(self, dcc_=None, user=None, tag=None, extn=EMPTY, catch=True):
        """Map this output to a work file.

        Args:
            dcc_ (str): override dcc
            user (str): override user
            tag (str): override tag
            extn (str): override work file extension
            catch (bool): no error if no valid work file created

        Returns:
            (CPWork): work file
        """
        try:
            return self.entity.to_work(
                dcc_=dcc_, task=self.task, tag=tag or self.tag,
                ver_n=self.ver_n, user=user, step=self.step,
                extn=extn)
        except ValueError as _exc:
            if not catch:
                raise _exc
            return None

    def __eq__(self, other):
        _LOGGER.debug('EQ %s', other)
        if hasattr(other, 'cmp_key'):
            _LOGGER.debug(' - USING CMP KEY %s %s', self.cmp_key, other.cmp_key)
            return self.cmp_key == other.cmp_key
        if hasattr(other, 'path'):
            _LOGGER.debug(' - USING PATH %s %s', self.path, other.path)
            return self.path == other.path
        if isinstance(other, str):
            return self.path == other
        return False

    def __lt__(self, other):
        if hasattr(other, 'cmp_key'):
            return self.cmp_key < other.cmp_key
        if hasattr(other, 'path'):
            return self.path < other.path
        raise ValueError(other)


def ver_sort(out):
    """Sort versions with versionless version last.

    Args:
        out (CPOutput): version to sort

    Returns:
        (int): output key
    """
    if not out.ver_n:
        return 100000
    return out.ver_n
