"""Tools for managing work directories.

These are task directories containing work which are generally dcc-specific.
"""

# pylint: disable=too-many-instance-attributes

import copy
import logging

from pini import dcc
from pini.utils import (
    Dir, abs_path, single, EMPTY, passes_filter, to_str)

from . import cp_utils
from .cp_entity import to_entity
from .cp_utils import extract_template_dir_data, EXTN_TO_DCC
from .cp_output import OUTPUT_TEMPLATE_TYPES

_LOGGER = logging.getLogger(__name__)
_TASK_MAP = {
    'animation': 'anim',
    'ani': 'anim',
    'anm': 'anim',
    'mod': 'model',
    'surf': 'lookdev',
    'mat': 'lookdev',
    'lgt': 'lighting',
    'trk': 'tracking',
}


class CPWorkDir(Dir):
    """Represents a work directory."""

    step = None
    user = None

    def __init__(self, path, entity=None, template=None):
        """Constructor.

        Args:
            path (str): path to or within work dir
            entity (CPEntity): force parent entity
            template (CPTemplate): for work dir template
        """
        _path = abs_path(to_str(path))
        _LOGGER.debug('INIT CPWorkDir %s', _path)

        # Apply entity
        self.entity = entity
        if not self.entity:
            self.entity = to_entity(_path)
            _LOGGER.debug('CREATING ENTITY %s', self.entity)
        self.job = self.entity.job
        self.profile = self.entity.profile
        self.asset_type = self.entity.asset_type
        self.asset = self.entity.asset

        # Find template + extract data
        if not template:
            _tmpls = [
                _tmpl.apply_data(entity_path=self.entity.path)
                for _tmpl in self.job.find_templates(
                    'work_dir', profile=self.profile)]
        else:
            _tmpls = [template]
        _LOGGER.debug(' - TRYING %d TEMPLATES', len(_tmpls))
        for _tmpl in _tmpls:
            _LOGGER.debug(' - TRYING TEMPLATE %s %s', _tmpl,
                          _tmpl.embedded_data)
            try:
                _dir, self.data = extract_template_dir_data(
                    template=_tmpl, path=_path, job=self.job)
            except ValueError as _exc:
                _LOGGER.debug('   - FAILED %s', _exc)
                continue
            self.template = _tmpl
            break
        else:
            raise ValueError(_path)
        self.dcc = self.data.get('dcc') or self.template.dcc
        _LOGGER.debug(' - DCC %s %s', self.dcc, self.template.embedded_data)

        super(CPWorkDir, self).__init__(_dir)

        self.task = self.data['task']
        self.step = self.data.get('step')
        self.user = self.data.get('user')

    @property
    def cmp_key(self):
        """Get sort key for this work dir.

        This allows work dirs to be sorted via task sorting

        Returns:
            (tuple): sort key
        """
        _step_sort = cp_utils.task_sort(self.step)
        _task_sort = cp_utils.task_sort(self.task)
        return _step_sort, _task_sort, self.path

    @property
    def task_label(self):
        """Obtain task label for this work dir.

        Generally this is just the task, but if the pipeline uses steps and
        tasks then this is "<step>/<task>" - eg. "surf/dev"

        Returns:
            (str): task label
        """
        if self.step:
            return '{}/{}'.format(self.step, self.task)
        return self.task

    def create(self, force=False):
        """Create this work dir.

        Args:
            force (bool): create any parent entity without
                confirmation
        """
        from pini import pipe
        if pipe.MASTER == 'disk' and not self.entity.exists():
            self.entity.create(force=force)
        self.mkdir()

    def find_work(self, catch=False, **kwargs):
        """Find single work file inside this work dir.

        Args:
            catch (bool): no error if work dir not found

        Returns:
            (CPWork): matching work
        """
        return single(self.find_works(**kwargs), catch=catch)

    def find_works(
            self, filter_=None, tag=EMPTY, dcc_=None, ver_n=None, extns=None):
        """Find work files in this work dir.

        Args:
            filter_ (str): apply path filter
            tag (str): filter by tag (because tag as None is
                a valid value, use -1 no tag filter)
            dcc_ (str): apply dcc filter
            ver_n (int): filter by version number
            extns (str list): filter by file extensions

        Returns:
            (CPWork list): matching work files
        """
        _LOGGER.debug('FIND WORKS')
        _works, _ = self._read_works_data()

        # Apply latest filter
        _ver_n = ver_n
        if _ver_n == 'latest':
            _map = {}
            for _work in _works:
                _map[_work.tag] = _work
            _works = sorted(_map.values())
            _ver_n = None
        if _ver_n is not None:
            assert isinstance(_ver_n, int)

        # Apply other filters
        _filtered_works = []
        for _work in _works:
            if tag is not EMPTY and _work.tag != tag:
                continue
            if _ver_n is not None and _work.ver_n != _ver_n:
                continue
            if dcc_ and EXTN_TO_DCC[_work.extn] != dcc_:
                continue
            if filter_ and not passes_filter(_work.path, filter_):
                continue
            if extns and _work.extn not in extns:
                continue
            _filtered_works.append(_work)

        return _filtered_works

    def _read_works_data(self, class_=None):
        """Read files in this work dir.

        Args:
            class_ (CPWork): override work file class

        Returns:
            (CPWork list, int): matching work files, number of
                badly named files
        """
        from pini import pipe

        _LOGGER.debug('READ WORKS %s', self.dcc)

        _class = class_ or pipe.CPWork
        _work_subdirs = self._read_work_subdirs()
        _badly_named_files = 0

        _works = []
        for _subdir in _work_subdirs:
            for _file in _subdir.find(
                    depth=1, type_='f', catch_missing=True, class_=True):
                _LOGGER.debug(' - TESTING FILE %s', _file.path)

                # Filter results
                if (
                        _file.extn not in EXTN_TO_DCC or
                        (self.dcc and not EXTN_TO_DCC[_file.extn] == self.dcc)):
                    _LOGGER.debug('   - REJECTED')
                    continue

                # Build work object
                try:
                    _work = _class(_file, work_dir=self)
                except ValueError:
                    _badly_named_files += 1
                    _LOGGER.debug('   - FAILED TO BUILD CLASS')
                    continue

                _LOGGER.debug('   - ACCEPTED')
                _works.append(_work)

        _LOGGER.debug(' - BADLY NAMED FILES %d', _badly_named_files)
        _works.sort()

        return _works, _badly_named_files

    def _read_work_subdirs(self):
        """Read work subdirectories.

        In a simple pipeline, the work dir is the parent of a work file,
        so the subdirs will be a single empty string. In a pipeline with
        wip subdirs for each user though, this will search for user folders
        within this work dir.

        Returns:
            (str list): work file subdirs
        """
        from pini import pipe

        # import pprint
        _tmpls = self.entity.find_templates('work')
        _tmpls = [
            _tmpl.apply_data(work_dir=self.path) for _tmpl in _tmpls]
        _tmpls = [
            pipe.CPTemplate(
                name='work_subdir', pattern=_tmpl.pattern.rsplit('/', 1)[0])
            for _tmpl in _tmpls]
        _LOGGER.debug(' - TMPLS %d %s', len(_tmpls), _tmpls)

        _subdirs = []
        for _tmpl in copy.copy(_tmpls):
            if _tmpl.is_resolved():
                _tmpls.remove(_tmpl)
                _subdirs.append(Dir(_tmpl.pattern))

        if _tmpls:
            _LOGGER.debug(' - GLOBBING %d %s', len(_tmpls), _tmpls)
            _globs = pipe.glob_templates(templates=_tmpls, job=self.job)
            _subdirs += [_path for _, _path in _globs]

        _LOGGER.debug(' - FOUND %d SUBDIRS %s', len(_subdirs), _subdirs)

        return _subdirs

    def to_work_dir(self, user=EMPTY, **kwargs):
        """Map to a new work dir object updating the given parameters.

        Args:
            user (str): override user

        Returns:
            (CPWorkDir): work dir
        """
        _LOGGER.debug('TO WORK DIR %s', self)
        _data = copy.copy(self.data)
        _data.update(kwargs)
        if user is not EMPTY:
            _data['user'] = user
        _LOGGER.debug(' - DATA %s', _data)
        _path = self.template.pattern.format(**_data)
        _LOGGER.debug(' - PATH %s', _path)
        return CPWorkDir(_path)

    def to_work(
            self, tag=None, ver_n=1, user=None, dcc_=None, extn=None,
            class_=None, catch=False):
        """Build a work file object with this work dir's tokens.

        Args:
            tag (str): apply tag
            ver_n (int): apply version number
            user (str): apply user
                (use -1 for no user, None applies current user)
            dcc_ (str): override dcc
            extn (str): force file extension
            class_ (class): override work object class
            catch (bool): no error if tokens do not create valid tag

        Returns:
            (CPWork): work file object
        """
        from pini import pipe

        _LOGGER.debug('TO WORK %s', self.path)
        _class = class_ or pipe.CPWork
        _user = pipe.cur_user() if not user else user
        _LOGGER.debug(' - USER %s %s', _user, user)
        _tag = tag or self.job.cfg['tokens']['tag']['default']
        _dcc = dcc_ or self.dcc or dcc.NAME

        # Obtain template (favour template w/o user token)
        _tmpl = self.entity.find_template(
            'work', dcc_=_dcc, catch=True,
            want_key={'tag': bool(tag), 'user': bool(user)})

        # Obtain ver
        _ver_pad = self.job.cfg['tokens']['ver']['len']
        _ver = str(ver_n).zfill(_ver_pad)

        # Obtain work dir
        _work_dir = self.to_work_dir(user=_user)
        if _work_dir == self:
            _work_dir = self
        _LOGGER.debug(' - WORK DIR %s', _work_dir)

        # Obtain extn
        if extn:
            _extn = extn
        else:
            _defaults = self.job.cfg['defaults']
            _key = '{}_extn'.format(dcc.NAME)
            _extn = _defaults.get(_key, dcc.DEFAULT_EXTN)

        # Build data
        _data = dict(  # pylint: disable=use-dict-literal
            entity=self.entity.name, user=_user,
            shot=self.entity.name, dcc=_dcc,
            asset=self.entity.name,
            extn=_extn, ver=_ver, step=self.step,
            work_dir=_work_dir.path, task=self.task, tag=_tag)
        _token_cfg = self.job.cfg['tokens']
        for _token, _val in _data.items():
            if _token not in _token_cfg:
                continue
            _limit = _token_cfg[_token].get('limit')
            if _limit and _val:
                _data[_token] = _val[:_limit]
        if 'job_prefix' in _tmpl.keys():
            _data['job_prefix'] = self.job.to_prefix()
        _LOGGER.debug(' - DATA %s', _data)

        # Build work file
        _file = _tmpl.format(_data)
        _LOGGER.debug(' - FILE %s', _file)
        try:
            return _class(_file, work_dir=_work_dir)
        except ValueError as _exc:
            if catch:
                return None
            raise _exc

    def find_output(self, catch=False, **kwargs):
        """Find an output within this work dir.

        Args:
            catch (bool): no error if output not found

        Returns:
            (CPOutput): matching output
        """
        return single(self.find_outputs(**kwargs), catch=catch)

    def find_outputs(
            self, type_=None, output_name=None, output_type=EMPTY, ver_n=EMPTY,
            tag=EMPTY, extn=None):
        """Find outputs within this work dir.

        Args:
            type_ (str): filter by type (eg. cache/publish)
            output_name (str): filter by output name
            output_type (str): filter by output type
            ver_n (int): filter by version number
            tag (str): filter by tag
            extn (str): filter by file extension

        Returns:
            (CPOutput list): outputs
        """
        _LOGGER.debug('FIND OUTPUTS %s', self.path)
        _all_outs = self._read_outputs()
        _LOGGER.debug(' - READ %d OUTPUTS', len(_all_outs))

        # Apply latest version filter
        _ver_n = ver_n
        if _ver_n == 'latest':
            _LOGGER.debug(' - APPLYING LATEST FILTER %s', _all_outs)
            _latests = {}
            for _out in _all_outs:
                _latests[_out.tag] = _out
            _LOGGER.debug(' - LATESTS %s', _latests)
            _all_outs = sorted(_latests.values())
            _ver_n = EMPTY

        # Apply other filters
        _LOGGER.debug(' - VER N %s', _ver_n)
        _outs = []
        for _out in _all_outs:

            if type_ and not _out.type_ == type_:
                continue
            if output_name and _out.output_name != output_name:
                continue
            if output_type is not EMPTY and _out.output_type != output_type:
                continue
            if tag is not EMPTY and _out.tag != tag:
                continue
            if extn and _out.extn != extn:
                continue

            if _ver_n is EMPTY:
                pass
            elif _ver_n is None and _out.ver_n:
                continue
            elif _out.ver_n != _ver_n:
                continue

            _outs.append(_out)

        return _outs

    def _find_output_templates(self):
        """Find output templates for this work dir.

        Returns:
            (CPTemplate list): matching output templates
        """

        # Find templates
        _tmpls = []
        for _type in OUTPUT_TEMPLATE_TYPES:
            _tmpls += self.job.find_templates(type_=_type, profile=self.profile)
        _tmpls = [_tmpl for _tmpl in _tmpls
                  if _tmpl.pattern.startswith('{work_dir}')]
        _tmpls = sorted({
            _tmpl.apply_data(
                entity_path=self.entity.path, entity=self.entity.name,
                task=self.task, work_dir=self.path)
            for _tmpl in _tmpls})
        _tmpls.sort()

        return _tmpls

    def _read_outputs(self, class_=None):
        """Read this work dir's outputs from disk.

        Args:
            class_ (class): override output class

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe

        _LOGGER.debug('READ OUTPUTS %s', self)
        if pipe.MASTER == 'disk':
            _outs = self._read_outputs_disk(class_=class_)
        elif pipe.MASTER == 'shotgrid':
            _outs = self._read_outputs_sg()
        else:
            raise ValueError(pipe.MASTER)

        return sorted(_outs)

    def _read_outputs_disk(self, class_=None):
        """Read outputs from disk.

        Args:
            class_ (class): override output class

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe

        _class = class_ or pipe.CPOutput
        _LOGGER.debug('READ OUTPUTS DISK %s', _class)
        _tmpls = self._find_output_templates()
        _LOGGER.debug(' - FOUND %d TMPLS', len(_tmpls))

        _globs = pipe.glob_templates(_tmpls, job=self.job)
        _outs = []
        for _tmpl, _path in _globs:
            _out = _class(
                _path, template=_tmpl, work_dir=self, entity=self.entity)
            _outs.append(_out)

        return _outs

    def _read_outputs_sg(self):
        """Read outputs from shotgrid.

        Returns:
            (CPOutput list): outputs
        """
        from pini.pipe import shotgrid
        return shotgrid.find_pub_files(work_dir=self)

    def to_output(self, type_, tag=None, output_name=None, ver_n=1, extn=None):
        """Map this work dir to an output.

        Args:
            type_ (str): output type (eg. render/cache)
            tag (str): output tag
            output_name (str): output name
            ver_n (int): output version number
            extn (str): output extension

        Returns:
            (CPOutput): output
        """
        _work = self.to_work(ver_n=ver_n, tag=tag)
        return _work.to_output(type_, extn=extn, output_name=output_name)

    def __lt__(self, other):
        return self.cmp_key < other.cmp_key


def cur_task(fmt='local'):
    """Obtain current task name.

    Args:
        fmt (str): task format
            local - use local task name
            pini - use standardised pini name (eg. mod -> model)

    Returns:
        (str): current task
    """
    _work_dir = cur_work_dir()
    _task = _work_dir.task if _work_dir else None
    _step = _work_dir.step if _work_dir else None

    if fmt == 'full':
        if not _work_dir:
            return None
        if _step:
            return '{}/{}'.format(_step, _task)
        return _work_dir.task

    return map_task(_task, step=_step, fmt=fmt)


def cur_work_dir(entity=None):
    """Obtain current work dir.

    Args:
        entity (CPEntity): force parent entity (to facilitate caching)

    Returns:
        (CPWorkDir): current work dir
    """
    return to_work_dir(dcc.cur_file(), entity=entity)


def map_task(task, step=None, fmt='pini'):
    """Map task name.

    Args:
        task (str): task name to map
        step (str): step name to map - this can be used if the task is not
            descriptive, eg. dev
        fmt (str): task format
            local - use local task name (ie. does nothing)
            pini - use standardised pini name (eg. mod -> model)

    Returns:
        (str): mapped task name
    """

    if fmt == 'local':
        _task = task
    elif fmt == 'pini':
        _task = _TASK_MAP.get(step) or _TASK_MAP.get(task) or task
    else:
        raise ValueError(fmt)
    return _task


def to_work_dir(path, entity=None):
    """Build a work dir object from the given path.

    Args:
        path (str): path to convert to work dir
        entity (CPEntity): force parent entity (to facilitate caching)

    Returns:
        (CPWorkDir|None): work dir (if any)
    """
    try:
        return CPWorkDir(path, entity=entity)
    except ValueError:
        return None
