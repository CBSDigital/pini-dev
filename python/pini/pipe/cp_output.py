"""Tools for managing outputs."""

# pylint: disable=too-many-public-methods,too-many-instance-attributes,too-many-lines

import copy
import logging
import subprocess
import time

import lucidity
import six

from pini import dcc, icons
from pini.utils import (
    File, Seq, register_custom_yaml_handler, str_to_ints, ints_to_str,
    clip, Dir, EMPTY, Image, find_exe, single)

from .cp_entity import to_entity
from .cp_utils import validate_tokens

_LOGGER = logging.getLogger(__name__)

RENDER_CALLBACK = None
OUTPUT_TEMPLATE_TYPES = ['publish', 'cache', 'ass_gz']
OUTPUT_VIDEO_TEMPLATE_TYPES = ['blast_mov', 'mov', 'render_mov', 'plate_mov']
OUTPUT_SEQ_TEMPLATE_TYPES = ['render', 'plate', 'blast', 'cache_seq']


class CPOutputBase(object):
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

    data = None
    template = None

    def __init__(
            self, job=None, entity=None, work_dir=None, templates=None,
            template=None, types=None):
        """Constructor.

        Args:
            job (CPJob): force parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            types (str list): override list of template types to test for
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
            types=types or OUTPUT_TEMPLATE_TYPES,
            templates=templates, template=template)

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
                raise ValueError(_exc)
        else:
            try:
                self.data, self.template = lucidity.parse(self.path, _tmpls)
            except lucidity.ParseError as _exc:
                _LOGGER.log(9, ' - PATH "%s"', self.path)
                _LOGGER.log(9, ' - ERROR %s', _exc)
                raise ValueError('No output templates matched path '+self.path)
        _LOGGER.log(9, ' - TEMPLATE %d %s', _tmpls.index(self.template),
                    self.template)

        validate_tokens(self.data, job=self.job)

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

        self.asset_type = self.entity.asset_type
        self.asset = self.entity.asset
        self.sequence = self.entity.sequence
        self.shot = self.entity.shot

        self.ver = self.data.get('ver')
        self.ver_n = int(self.ver) if self.ver else None

        self.output_type = self.data.get('output_type')

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
    def cmp_key(self):
        """Key to use for sorting/comparison.

        Makes sure that outputs without tags are always sorted first.

        Returns:
            (tuple): sort key
        """
        _tag = self.tag or ''  # Use empty string otherwise py3 sorting breaks
        return self.dir, _tag, self.filename

    @property
    def metadata(self):
        """Obtain this output's metadata.

        Returns:
            (dict): metadata
        """
        return self.get_metadata()

    @property
    def metadata_yml(self):
        """Obtain metadata yaml file for this output.

        Returns:
            (File): metadata yaml
        """
        return self.to_file(dir_=self.dir+'/.pini', extn='yml')

    @property
    def nice_type(self):
        """Obtain nice type name for this template.

        This is the template type in a simple, readable form.

        eg. render -> render
            cache_seq -> cache
            blast_mov -> blast
            mov -> render

        Returns:
            (str): nice type
        """
        _type = self.type_
        if _type.endswith('_mov'):
            _type = _type[:-4]
        if _type.endswith('_seq'):
            _type = _type[:-4]
        if _type == 'mov':
            _type = 'render'
        return _type

    @property
    def submittable(self):
        """Test whether this output is submittable.

        ie. whether it can be submitted to shotgrid.

        Returns:
            (bool): submittable
        """
        from pini import pipe
        if not pipe.SUBMIT_AVAILABLE:
            return False
        if isinstance(self, CPOutputVideo):
            return True
        return self.type_ in ['render', 'plate', 'blast']

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
        self.set_metadata(kwargs, mode='add')

    def get_metadata(self):
        """Obtain this output's metadata.

        Returns:
            (dict): metadata
        """
        return self.metadata_yml.read_yml(catch=True)

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
            raise ValueError('No versions found '+self.path)
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
            _ver_n = _latest.ver_n+1
        return self.to_output(ver_n=_ver_n)

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

    def find_rep(self, task=None, extn=None):
        """Find alternative representations of this output.

        Args:
            task (str): filter by task
            extn (str): filter by extension

        Returns:
            (CPOutput): alternative representation
        """
        return single(self.find_reps(task=task, extn=extn))

    def find_reps(self, task=None, extn=None):
        """Find different representation of this reference.

        eg. model ma publish <=> lookdev ass.gz standin

        These are other outputs which this output can be swapped with.

        Args:
            task (str): filter by task
            extn (str): filter by extension

        Returns:
            (CPOutput list): representations
        """
        _reps = []
        for _rep in self._read_reps():
            if extn and _rep.extn != extn:
                continue
            if task and _rep.task != task:
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
        from pini import pipe
        _LOGGER.debug('FIND REPS %s', self)
        _LOGGER.debug(' - TASK %s', self.task)
        _LOGGER.debug(' - EXTN %s', self.extn)

        _reps = []

        # Add model/rig publishes
        if self.extn in ('ma', 'mb', 'gz'):
            _LOGGER.debug(' - LOOKING FOR PUBLISHES')
            for _task in ['model', 'rig']:
                if _task == self.task:
                    continue
                _pub = self.entity.find_publish(
                    ver_n='latest', tag=self.tag, versionless=False,
                    task=_task, catch=True)
                _LOGGER.debug(' - CHECKING PUBLISH task=%s %s', _task, _pub)
                if _pub:
                    _reps.append(_pub)

        # Add ass.gz for model refs
        if pipe.map_task(self.task) in ('model', 'rig'):
            _ass = self.entity.find_output(
                type_='ass_gz', ver_n='latest', tag=self.tag, catch=True)
            if _ass:
                _reps.append(_ass)

        return _reps

    def is_latest(self):
        """Check whether this is the latest version.

        Returns:
            (bool): whether latest
        """
        _LOGGER.debug('IS LATEST %s', self)
        if not self.ver_n:
            return True
        _vers = [_ver for _ver in self.find_vers() if _ver.ver_n]
        if not _vers:
            return False
        _latest = _vers[-1]
        _LOGGER.debug(' - LATEST %s', _latest)
        return self == _latest

    def set_metadata(self, data, mode='replace', force=True):
        """Set metadata for this output.

        Args:
            data (dict): metadata to apply
            mode (str): how to set the metadata
                replace - overwrite existing metadata
                add - update existing metadata with this metadata
            force (bool): replace existing metadata without confirmation
        """
        if mode == 'replace':
            _data = data
        elif mode == 'add':
            _data = self.metadata
            _data.update(data)
        else:
            raise ValueError(mode)
        self.metadata_yml.write_yml(_data, force=True)

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
        _tmpl = template or self.template
        if isinstance(_tmpl, six.string_types):
            _tmpl = self.entity.find_template(
                _tmpl, has_key={'tag': bool('tag' in kwargs or self.tag)})
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
        _out = to_output(_path)
        return _out

    def to_file(self, **kwargs):
        """Map this output to a file with the same attributes.

        Returns:
            (File): file
        """
        raise NotImplementedError

    def to_work(self, dcc_=None, catch=True):
        """Map this output to a work file.

        Args:
            dcc_ (str): override dcc
            catch (bool): no error if no valid work file created

        Returns:
            (CPWork): work file
        """
        try:
            return self.entity.to_work(
                dcc_=dcc_, task=self.task, tag=self.tag, ver_n=self.ver_n)
        except ValueError as _exc:
            if not catch:
                raise _exc
            return None

    def __lt__(self, other):
        if hasattr(other, 'cmp_key'):
            return self.cmp_key < other.cmp_key
        raise ValueError(other)


class CPOutput(File, CPOutputBase):
    """Represents an output file on disk."""

    __lt__ = CPOutputBase.__lt__
    yaml_tag = '!CPOutput'

    def __init__(  # pylint: disable=unused-argument
            self, path, job=None, entity=None, work_dir=None, templates=None,
            template=None, types=None):
        """Constructor.

        Args:
            path (str): path to file
            job (CPJob): parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            types (str list): override list of template types to test for
        """
        super(CPOutput, self).__init__(path)
        CPOutputBase.__init__(
            self, job=job, entity=entity, work_dir=work_dir,
            template=template, templates=templates,
            types=types or OUTPUT_TEMPLATE_TYPES)

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
        del loader  # for linter
        return cls(node.value)

    @classmethod
    def to_yaml(cls, dumper, data):
        """Convert this output to yaml.

        Args:
            cls (class): output class
            dumper (Dumper): yaml dumper
            data (CPOutput): output being exported

        Returns:
            (str): output as yaml
        """
        _tag = '!'+type(data).__name__
        _LOGGER.debug('TO YAML %s %s', cls.yaml_tag, _tag)
        return dumper.represent_scalar(_tag, data.path)


class CPOutputVideo(CPOutput, clip.Video):
    """Represents an output video file (eg. mov/mp4)."""

    yaml_tag = '!CPOutputVideo'
    to_frame = clip.Video.to_frame

    def __init__(
            self, path, job=None, entity=None, work_dir=None, templates=None,
            template=None, types=None):
        """Constructor.

        Args:
            path (str): path to file
            job (CPJob): force parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            types (str list): override list of template types to test for
        """
        super(CPOutputVideo, self).__init__(
            path, job=job, entity=entity, work_dir=work_dir,
            template=template, templates=templates,
            types=types or OUTPUT_VIDEO_TEMPLATE_TYPES)

    @classmethod
    def to_yaml(cls, dumper, data):
        """Convert this output to yaml.

        Args:
            cls (class): output class
            dumper (Dumper): yaml dumper
            data (CPOutput): output being exported

        Returns:
            (str): output as yaml
        """
        return dumper.represent_scalar(cls.yaml_tag, data.path)


class CPOutputSeqDir(Dir):
    """Represents a directory containing output file sequences.

    This is used to facilitate caching.
    """

    def __init__(self, path, entity, template):
        """Constructor.

        Args:
            path (str): path to directory
            entity (CPEntity): parent entity
            template (CPTemplate): seq_dir template
        """
        super(CPOutputSeqDir, self).__init__(path)

        self.template = template
        self.entity = entity

        self.data = self.template.parse(self.path)

        self.task = self.data.get('task')
        self.tag = self.data.get('tag')
        self.ver_n = int(self.data['ver'])

    def find_outputs(self):
        """Find outputs within this directory.

        Returns:
            (CPOutputSeq list): outputs
        """
        return self._read_outputs()

    def _read_outputs(self, output_seq_class=None, output_video_class=None):
        """Read outputs within this directory from disk.

        Args:
            output_seq_class (class): override output seq class
            output_video_class (class): override output video class

        Returns:
            (CPOutputSeq list): outputs
        """
        from pini import pipe
        _LOGGER.debug('[CPOutputSeqDir] READ OUTPUTS %s', self)
        _outs = []
        _output_seq_class = output_seq_class or pipe.CPOutputSeq
        _output_video_class = output_video_class or pipe.CPOutputVideo
        _LOGGER.debug(' - OUTPUT SEQ CLASS %s', _output_seq_class)
        for _path in self.find_seqs():

            _LOGGER.debug(' - TESTING PATH %s', _path)

            # Try as output seq
            if isinstance(_path, Seq):
                try:
                    _out = _output_seq_class(
                        _path.path, frames=_path.frames, dir_=self,
                        entity=self.entity)
                except ValueError:
                    continue

            elif isinstance(_path, File):
                try:
                    _out = _output_video_class(
                        _path.path, entity=self.entity)
                except ValueError:
                    continue

            else:
                raise ValueError(_path)

            _outs.append(_out)

        return _outs


class CPOutputSeq(Seq, CPOutputBase):
    """Represents an output file sequence on disk."""

    _dir = None

    yaml_tag = '!CPOutputSeq'
    to_file = Seq.to_file

    def __init__(  # pylint: disable=unused-argument
            self, path, job=None, entity=None, work_dir=None, templates=None,
            template=None, frames=None, dir_=None, types=None):
        """Constructor.

        Args:
            path (str): path to output file sequence
            job (CPJob): force parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            frames (int list): force frame cache
            dir_ (Dir): parent directory (to facilitate caching)
            types (str list): override list of template types to test for
        """
        _LOGGER.debug('INIT CPOutputSeq %s', path)
        super(CPOutputSeq, self).__init__(path=path, frames=frames)
        CPOutputBase.__init__(
            self, job=job, entity=entity, work_dir=work_dir,
            template=template, templates=templates,
            types=types or OUTPUT_SEQ_TEMPLATE_TYPES)
        self._dir = dir_
        self._thumb = File('{}/.pini/{}_thumb.jpg'.format(self.dir, self.base))

    @classmethod
    def from_yaml(cls, loader, node):
        """Build output seq object from yaml.

        Args:
            cls (class): output class
            loader (Loader): yaml loader
            node (Node): yaml data

        Returns:
            (CPOutputSeq): output seq
        """
        del loader  # for linter
        _path, _frames = node.value
        return CPOutputSeq(_path.value, frames=str_to_ints(_frames.value))

    @classmethod
    def to_yaml(cls, dumper, data):
        """Convert this output seq to yaml.

        Args:
            cls (class): output seq class
            dumper (Dumper): yaml dumper
            data (CPOutput): output seq being exported

        Returns:
            (str): output seq as yaml
        """
        _data = [data.path, ints_to_str(data.frames)]
        return dumper.represent_sequence(cls.yaml_tag, _data)

    def to_thumb(self, force=False):
        """Obtain thumbnail for this image sequence, building it if needed.

        Args:
            force (bool): force rebuild thumb

        Returns:
            (File): thumb
        """
        if force or not self._thumb.exists():
            self._build_thumb()
        return self._thumb

    def _build_thumb(self):
        """Build thumbnail for this image sequence using ffmpeg.

        The middle frame is used.
        """
        _LOGGER.info('BUILD THUMB %s', self._thumb.path)

        _frame = self.frames[len(self.frames)/2]
        _LOGGER.debug(' - FRAME %d', _frame)
        _img = Image(self[_frame])
        _LOGGER.debug(' - IMAGE %s', _img)

        # Get thumb res
        _res = self.to_res()
        assert _res
        _aspect = 1.0*_res[0]/_res[1]
        _out_h = 50
        _out_w = int(_out_h*_aspect)
        _out_res = _out_w, _out_h
        _LOGGER.debug(' - RES %s -> %s', _res, _out_res)
        _out_res_s = '{:d}x{:d}'.format(*_out_res)

        # Build ffmpeg cmds
        _ffmpeg = find_exe('ffmpeg')
        _cmds = [_ffmpeg.path, '-y',
                 '-i', _img.path,
                 '-s', _out_res_s,
                 self._thumb.path]
        _LOGGER.debug(' - CMD %s', ' '.join(_cmds))

        # Execute ffmpeg
        _start = time.time()
        if self._thumb.exists():
            self._thumb.delete(force=True)
        assert not self._thumb.exists()
        try:
            subprocess.check_output(
                _cmds, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            _LOGGER.info(' - BUILD THUMB FAILED %s', self.path)
            _write_fail_thumb(file_=self._thumb, res=_out_res)
        assert self._thumb.exists()

        _LOGGER.info(' - BUILD THUMB TOOK %.02fs', time.time() - _start)


def cur_output():
    """Get output currently loaded in dcc (if any).

    Returns:
        (CPOutput): matching output
    """
    _file = dcc.cur_file()
    if not _file:
        return None
    try:
        return to_output(_file)
    except ValueError:
        return None


def to_output(
        path, job=None, entity=None, work_dir=None, template=None, catch=False):
    """Get an output object based on the given path.

    Args:
        path (str): path to convert
        job (CPJob): parent job
        entity (CPEntity): parent entity
        work_dir (CPWorkDir): parent work dir
        template (CPTemplate): template to use
        catch (bool): no error if no output created

    Returns:
        (CPOutput|CPOutputSeq): output or output seq
    """
    _LOGGER.log(9, 'TO OUTPUT %s', path)

    # Handle catch
    if catch:
        try:
            return to_output(path, job=job, template=template)
        except ValueError as _exc:
            return None

    if not path:
        raise ValueError('Empty path')

    _file = File(path)
    _LOGGER.log(9, ' - PATH %s', _file.path)
    if '%' in _file.path:
        _class = CPOutputSeq
    elif _file.extn and _file.extn.lower() in ('mp4', 'mov'):
        _class = CPOutputVideo
    else:
        _class = CPOutput
    return _class(
        path, job=job, entity=entity, template=template, work_dir=work_dir)


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


def _write_fail_thumb(file_, res):
    """Write fail thumbnail to show that thumb generation failed.

    Args:
        file_ (File): path to write thumb to
        res (tuple): thumb res
    """
    from pini import qt

    _pix = qt.CPixmap(*res)
    _pix.fill('Black')
    _pix.draw_overlay(
        icons.find('Warning'),
        pos=(_pix.width()/2, 3), anchor='T',
        size=_pix.height()*0.4)
    _pix.draw_text(
        'THUMB\nFAILED', pos=(_pix.width()/2, _pix.height()-3),
        anchor='B', col='White', size=7)
    _pix.save_as(file_, force=True)


register_custom_yaml_handler(CPOutput)
register_custom_yaml_handler(CPOutputVideo)
register_custom_yaml_handler(CPOutputSeq)
