"""Tools for managing entities, the base class for shots and assets."""

# pylint: disable=no-member,disable=too-many-lines

import copy
import logging
import os

import six

from pini import dcc
from pini.utils import single, EMPTY, passes_filter, cache_result

from .. import cp_settings_elem
from ...cp_utils import task_sort

_LOGGER = logging.getLogger(__name__)


class CPEntityBase(cp_settings_elem.CPSettingsLevel):
    """Represents an entity (ie. an asset or shots) dir on disk."""

    job = None
    name = None

    profile = None
    asset_type = None
    asset = None
    sequence = None
    shot = None

    def __init__(self, path):
        """Constructor.

        Args:
            path (str): entity path
        """
        super().__init__(path)

        # Reject leading underscore in name (archived entities)
        if self.name.startswith('_'):
            raise ValueError('Name has leading underscore '+self.name)

    def create(self, force=False, parent=None, shotgrid_=True):
        """Create this entity.

        Args:
            force (bool): create entity without confirmation
            parent (QDialog): parent for confirmation dialogs
            shotgrid_ (bool): register in shotgrid (if available)
        """
        from pini import pipe

        if not force:
            del parent
            raise NotImplementedError

        self._create_tasks()

        # Setup shotgrid
        _enable = shotgrid_ and not self.settings['shotgrid']['disable']
        if _enable and pipe.SHOTGRID_AVAILABLE:
            from pini.pipe import shotgrid
            shotgrid.create_entity(self, force=force)

    def find_template(self, *args, **kwargs):
        """Find a template within this entity.

        Returns:
            (CPTemplate): matching template
        """
        return self.job.find_template(*args, profile=self.profile, **kwargs)

    def find_templates(self, *args, **kwargs):
        """Find templates within this entity.

        Returns:
            (CPTemplate list): matching templates
        """
        return self.job.find_templates(*args, profile=self.profile, **kwargs)

    @cache_result
    def _template_type_uses_token(self, type_, token):
        """Test whether the given template type uses the given token.

        For example in some pipelines, the cache template doesn't use the
        tag token. This means that when searching for caches, the tag token
        should be ignored. However, if the cache template uses the tag token
        the searching for caches should take account of tag.

        Args:
            type_ (str): template type (eg. cache)
            token (str): token to check (eg. tag)

        Returns:
            (bool): whether any templates of the given type uses the
                given token
        """
        for _tmpl in self.find_templates(type_=type_):
            if token in _tmpl.keys():
                return True
        return False

    def to_default_tasks(self, dcc_):
        """Read default tasks from config for the given dcc in this entity.

        Args:
            dcc_ (str): dcc to read tasks for

        Returns:
            (str list): tasks
        """
        _defaults = self.job.cfg['tasks']
        _dcc_key = '{}_{}s'.format(dcc_, self.profile)
        _generic_key = '{}s'.format(self.profile)
        if _dcc_key in _defaults:
            _tasks = _defaults[_dcc_key]
        else:
            _tasks = _defaults.get(_generic_key, [])
        return sorted(_tasks, key=task_sort)

    def _create_tasks(self):
        """Create task folders (work dirs)."""

        # Create tasks
        _LOGGER.debug('CREATE TASKS %s', self)
        for _dcc in dcc.DCCS:
            _tasks = self.to_default_tasks(dcc_=_dcc)
            _LOGGER.debug(' - TASKS %s %s', _dcc, _tasks)
            for _task in _tasks:
                _LOGGER.debug(' - CREATE WORKDIR %s %s', _task, _dcc)
                _work_dir = self.to_work_dir(task=_task, dcc_=_dcc)
                _work_dir.mkdir()

    def find_work_dir(
            self, match=None, task=None, step=None, dcc_=None, catch=False):
        """Find a work dir in this entity.

        Args:
            match (str): token to match (task/step)
            task (str): match by task
            step (str): match by step
            dcc_ (str): match by dcc
            catch (bool): no error if no work dir found

        Returns:
            (CPWorkDir): matching work dir

        Raises:
            (ValueError): if exactly one work dir was not found
        """
        from pini import pipe

        _LOGGER.debug('FIND WORK DIR')
        _work_dirs = self.find_work_dirs(step=step, task=task, dcc_=dcc_)
        _LOGGER.debug(' - FOUND %d WORK DIRS', len(_work_dirs))
        if len(_work_dirs) == 1:
            return single(_work_dirs)

        _task_matches = [
            _work_dir for _work_dir in _work_dirs
            if match in (_work_dir.task, _work_dir.pini_task)]
        _LOGGER.debug(' - FOUND %d TASK MATCHES', len(_task_matches))
        if len(_task_matches) == 1:
            return single(_task_matches)

        _map_task_matches = [
            _work_dir for _work_dir in _work_dirs
            if match == pipe.map_task(_work_dir.task)]
        _LOGGER.debug(' - FOUND %d MAP TASK MATCHES', len(_map_task_matches))
        if len(_map_task_matches) == 1:
            return single(_map_task_matches)

        # In case where step matches mutiple tasks (eg. anim -> anim/layout)
        _task_arg_matches = [
            _work_dir for _work_dir in _work_dirs
            if task == _work_dir.task]
        _LOGGER.debug(
            ' - FOUND %d TASK ARG MATCHES (%s)', len(_task_arg_matches), task)
        if len(_task_arg_matches) == 1:
            return single(_task_arg_matches)

        if catch:
            return None
        raise ValueError(match, task, step, dcc_)

    def find_work_dirs(self, task=None, step=None, dcc_=None):
        """Find work dirs within this entity.

        Args:
            task (str): filter by task
            step (str): filter by step
            dcc_ (str): match by dcc

        Returns:
            (CPWorkDir list): matching work dirs
        """
        _LOGGER.debug('FIND WORK DIRS task=%s dcc_=%s', task, dcc_)
        _all_work_dirs = self._read_work_dirs()
        _LOGGER.debug(
            ' - READ %d WORK DIRS %s', len(_all_work_dirs), _all_work_dirs)

        # Apply filters
        _work_dirs = []
        _filter = os.environ.get('PINI_PIPE_TASK_FILTER')
        for _work_dir in _all_work_dirs:
            if _filter and not passes_filter(_work_dir.task_label, _filter):
                continue
            if task and task not in (_work_dir.task, _work_dir.pini_task):
                continue
            if step and _work_dir.step != step:
                continue
            _work_dirs.append(_work_dir)

        # Apply dcc filter
        if dcc_:
            _dcc_has_specific_tmpls = bool([
                _tmpl for _tmpl in self.find_templates('work_dir', dcc_=dcc_)
                if _tmpl.dcc == dcc_])
            if _dcc_has_specific_tmpls:
                _match = (dcc_, )
            else:
                _match = (dcc_, None)
            _LOGGER.debug(' - DCC HAS SPECIFIC TMPLS %d dcc=%s match=%s',
                          _dcc_has_specific_tmpls, dcc_, _match)
            _work_dirs = [_work_dir for _work_dir in _work_dirs
                          if _work_dir.dcc in _match]

        return _work_dirs

    def _find_work_dir_templates(self):
        """Find work_dir templates for this entity.

        Any dccs which contain a dcc tag and which don't have a specific
        template for that dcc are expanded for all unhandled dccs.

        For example if there's a nuke_work_dir template and a generic work_dir
        template which has a dcc tag, the generic work_dir template is
        duplicated for every dcc except nuke.

        Returns:
            (CPTemplate list): templates
        """

        # Find templates
        _tmpls = self.job.find_templates(
            type_='work_dir', profile=self.profile)
        if (  # shot/asset template replaces generic template
                len(_tmpls) > 1 and
                not _tmpls[-1].profile and
                _tmpls[-2].profile and
                not _tmpls[-2].dcc):
            _tmpls.pop(-1)

        # Apply cur entity path data
        _tmpls = sorted({_tmpl.apply_data(entity_path=self.path)
                         for _tmpl in _tmpls})

        # Expand for dccs if necessary
        _handled_dccs = {_tmpl.dcc for _tmpl in _tmpls if _tmpl.dcc}
        _unhandled_dccs = set(dcc.DCCS).difference(_handled_dccs)
        _tmpls = sorted({
            _tmpl.apply_data(dcc=_tmpl.dcc)
            if 'dcc' in _tmpl.keys() and _tmpl.dcc
            else _tmpl
            for _tmpl in _tmpls})
        _tmpls = sum([
            [_tmpl.apply_data(dcc=_dcc) for _dcc in _unhandled_dccs]
            if 'dcc' in _tmpl.keys() and not _tmpl.dcc
            else [_tmpl]
            for _tmpl in _tmpls], [])
        _LOGGER.debug(' - FOUND %d TMPLS', len(_tmpls))

        assert len({_tmpl.pattern for _tmpl in _tmpls}) == len(_tmpls)

        return _tmpls

    def _read_work_dirs(self, class_=None):
        """Read work dirs within this entity.

        Args:
            class_ (class): override work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        raise NotImplementedError

    def to_work_dir(
            self, task, dcc_=None, step=None, user=None, catch=False,
            class_=None):
        """Build a work dir object matching this entity's tokens.

        Args:
            task (str): work dir task
            dcc_ (str): work dir dcc
            step (str): work dir step
            user (str): work dir user
            catch (bool): no error if arg do not create valid work dir object
            class_ (class): override work dir class

        Returns:
            (CPWorkDir): work dir object
        """
        _LOGGER.debug('TO WORK DIR %s', task)
        from pini import pipe

        _class = class_ or pipe.CPWorkDir
        _step = step or task
        _user = user or pipe.cur_user()

        # Apply defaults
        _dcc = dcc_
        if _dcc is None:
            _dcc = dcc.NAME
        if not _dcc:
            raise ValueError('No dcc defined')

        # Find template
        _tmpls = self.job.find_templates(
            type_='work_dir', profile=self.profile, dcc_=_dcc)
        _tmpl = _tmpls[0].apply_data(entity_path=self.path)

        # Build work dir
        _data = {'task': task, 'dcc': _dcc, 'step': _step, 'user': _user}
        _LOGGER.debug('TO WORK DIR %s', self)
        _LOGGER.debug(' - DATA %s', _data)
        _LOGGER.debug(' - TMPL %s', _tmpl)
        _path = _tmpl.format(_data)
        _LOGGER.debug(' - PATH %s', _path)
        try:
            return _class(_path, entity=self, template=_tmpl)
        except ValueError as _exc:
            if catch:
                return None
            raise _exc

    def find_work(self, tag=EMPTY, ver_n=None, task=None, catch=False):
        """Find a work file in this entity.

        Args:
            tag (str|None): filter by tag
            ver_n (int): filter by version number
            task (str): filter by task
            catch (bool): no error if work not found

        Returns:
            (CPWork): matching work file
        """
        _works = self.find_works(tag=tag, ver_n=ver_n, task=task)
        return single(_works, catch=catch)

    def find_works(self, task=None, tag=EMPTY, ver_n=None, dcc_=None):
        """Find work files in this entity.

        Args:
            task (str): filter by task
            tag (str|None): filter by tag
            ver_n (int): filter by version number
            dcc_ (str): filter by dcc

        Returns:
            (CPWork list): matching work files
        """
        _LOGGER.debug('FIND WORKS')
        _works = []
        _work_dirs = self.find_work_dirs(task=task, dcc_=dcc_)
        _LOGGER.debug(' - WORK DIRS %d %s', len(_work_dirs), _work_dirs)
        for _work_dir in _work_dirs:
            _task_works = _work_dir.find_works(tag=tag, ver_n=ver_n)
            _LOGGER.debug(
                ' - ADD TASK WORKS %s %s', _work_dir.task, _task_works)
            _works += _task_works
        return _works

    def find_output(self, catch=False, **kwargs):
        """Find an output within this entity.

        Args:
            catch (bool): no error if no output found

        Returns:
            (CPOutput): matching output
        """
        return single(self.find_outputs(**kwargs), catch=catch)

    def find_outputs(
            self, type_=None, output_name=None, output_type=None, task=None,
            ver_n=EMPTY, tag=EMPTY, extn=None, filter_=None, class_=None):
        """Find outputs in this entity.

        This will only search outputs stored at entity level.

        Args:
            type_ (str): filter by output type (eg. render/cache)
            output_name (str): filter by output name
            output_type (str):  filter by output type
            task (str): filter by task
            ver_n (int|None): filter by version number
            tag (str|None): filter by tag
            extn (str): filter by extension
            filter_ (str): filter by path
            class_ (class): filter by class

        Returns:
            (CPOutput list): matching outputs
        """
        _LOGGER.debug('FIND OUTPUTS')
        _all_outs = self._read_outputs()
        _LOGGER.debug(' - FOUND %d OUTPUTS', len(_all_outs))

        # Apply latest filter
        _ver_n = ver_n
        if _ver_n == 'latest':
            _LOGGER.debug(' - APPLYING LATEST FILTER %s', _all_outs)
            _latests = {}
            for _out in _all_outs:
                _key = (_out.type_, _out.tag, _out.output_name, _out.task,
                        _out.output_type)
                _LOGGER.debug(' - ADDING %s', _out)
                _latests[_key] = _out
            _LOGGER.debug(' - LATESTS %s', _latests)
            _all_outs = sorted(_latests.values())
            _ver_n = EMPTY

        # Apply other filters
        _outs = []
        for _out in _all_outs:
            _LOGGER.debug(' - TESTING %s', _out)
            if extn and _out.extn != extn:
                continue
            if output_type and _out.output_type != output_type:
                continue
            if output_name and _out.output_name != output_name:
                continue
            if task and task not in (_out.task, _out.pini_task):
                continue
            if (
                    tag is not EMPTY and
                    self._template_type_uses_token(
                        type_=_out.type_, token='tag') and
                    _out.tag != tag):
                continue
            if _ver_n is not EMPTY and _out.ver_n != _ver_n:
                continue
            if type_ is not None and _out.type_ != type_:
                _LOGGER.debug('   - TYPE FILTERED %s (%s)', _out.type_, type_)
                continue
            if filter_ and not passes_filter(_out.path, filter_):
                continue
            if class_ and not isinstance(_out, class_):
                continue
            _outs.append(_out)
        return sorted(_outs)

    def _read_outputs(self):
        """Read outputs in this entity.

        Returns:
            (CPOutput list): outputs
        """
        raise NotImplementedError

    def find_publish(self, catch=True, **kwargs):
        """Find a publish in this entity.

        Args:
            catch (bool): no error if fail to match single publish

        Returns:
            (CPOutput): matching publish
        """
        return single(self.find_publishes(**kwargs), catch=catch)

    def find_publishes(  # pylint: disable=too-many-branches
            self, task=None, output_type=EMPTY, output_name=None, ver_n=EMPTY,
            tag=EMPTY, extn=EMPTY, extns=None, versionless=None, filter_=None):
        """Find publishes in this entity.

        Args:
            task (str): filter by task
            output_type (str): filter by output type
            output_name (str): filter by output name
            ver_n (int): filter by version number
            tag (str): filter by tag
            extn (str): filter by publish extension
            extns (str list): filter by publish extensions
            versionless (bool): filter by versionless state
            filter_ (str): apply path filter

        Returns:
            (CPOutput list): matching publishes
        """

        # Determine extns filter
        _extns = []
        if extn is not EMPTY:
            _extns.append(extn)
        if extns:
            _extns += extns

        # Filter list of extns
        _pubs = []
        for _pub in self._read_publishes():

            if task and task not in (_pub.task, _pub.pini_task):
                continue
            if output_name and _pub.output_name != output_name:
                continue
            if output_type is not EMPTY and _pub.output_type != output_type:
                continue
            if tag is not EMPTY and _pub.tag != tag:
                continue
            if _extns and _pub.extn not in _extns:
                continue
            if versionless is not None and bool(_pub.ver_n) == versionless:
                continue
            if filter_ and not passes_filter(_pub.path, filter_):
                continue

            # Apply version filter
            if ver_n == 'latest':
                if not _pub.is_latest():
                    continue
            elif ver_n is not EMPTY:
                assert ver_n is None or isinstance(ver_n, int)
                if _pub.ver_n != ver_n:
                    continue

            _pubs.append(_pub)

        return _pubs

    def _read_publishes(self):
        """Read all publishes in this entity.

        Returns:
            (CPOutput list): all publishes
        """
        raise NotImplementedError

    def to_output(
            self, template, task=None, step=None, tag=None, output_type=None,
            output_name=None, dcc_=None, user=None, ver_n=1, extn=None):
        """Build an output object for this entity.

        Args:
            template (CPTemplate): output template to use
            task (str): output task
            step (str): output step (if applicable)
            tag (str): output tag
            output_type (str): apply output name
            output_name (str): output name
            dcc_ (str): output dcc (if applicable)
            user (str): output user (if applicable)
            ver_n (int): output version
            extn (str): output extension

        Returns:
            (CPOutput): matching output
        """
        _LOGGER.debug('TO OUTPUT')
        from pini import pipe

        # Get template
        _tag = tag or self.job.cfg['tokens']['tag']['default']
        if isinstance(template, pipe.CPTemplate):
            _tmpl = template
        elif isinstance(template, six.string_types):
            _want_key = {
                'output_type': bool(output_type)}
            _LOGGER.debug(' - WANT KEY %s', _want_key)
            _has_key = {
                'tag': bool(_tag),
                'ver': bool(ver_n)}
            _LOGGER.debug(' - HAS KEY %s', _has_key)
            _tmpl = self.find_template(
                template, has_key=_has_key, want_key=_want_key)
        else:
            raise ValueError(template)
        _LOGGER.debug(' - TMPL %s', _tmpl)
        _LOGGER.debug(' - TAG %s', _tag)

        # Apply defaults
        _tag = tag
        if tag is None:
            _tag = self.job.cfg['tokens']['tag']['default']
        _extn = extn
        if extn is None:
            _extn = {'render': 'exr',
                     'mov': 'mp4',
                     'publish': dcc.DEFAULT_EXTN,
                     'cache': 'abc'}.get(_tmpl.type_)

        _ver_pad = self.job.cfg['tokens']['ver']['len']
        _ver = str(ver_n).zfill(_ver_pad)

        # Build data dict
        _data = copy.copy(self.data)
        _data['user'] = user
        _data['ver'] = _ver
        _data['entity'] = self.name
        _data['entity_path'] = self.path
        _data['task'] = task
        _data['step'] = step or task
        _data['dcc'] = dcc_ or dcc.NAME
        _data['tag'] = _tag
        _data['output_name'] = output_name
        _data['output_type'] = output_type
        _data['extn'] = _extn
        if 'work_dir' in _tmpl.keys():
            _LOGGER.debug(' - TO WORK DIR %s %s', step, task)
            _work_dir = self.to_work_dir(step=step, task=task)
            _data['work_dir'] = _work_dir.path
        if 'job_prefix' in _tmpl.keys():
            _data['job_prefix'] = self.job.to_prefix()

        # Check for missing keys
        _missing = []
        for _key in _tmpl.keys():
            if _key not in _data or not _data[_key]:
                _missing.append(_key)
        if _missing:
            raise RuntimeError('Missing keys {}'.format('/'.join(_missing)))

        # Construct output
        _path = _tmpl.format(_data)
        _LOGGER.debug(' - PATH %s', _path)
        return pipe.to_output(_path, template=_tmpl)

    def to_work(
            self, task, step=None, tag=None, ver_n=1, dcc_=None, user=None,
            extn=None, class_=None, catch=False):
        """Build a work file object for this entity.

        Args:
            task (str): work file task
            step (str): work file step (if applicable)
            tag (str|None): work file tag
            ver_n (int): work file version number
            dcc_ (str): force dcc token
            user (str): override user (if applicable)
            extn (str): override extension
            class_ (CPWork): override work class
            catch (bool): no error if args are invalid (just return None)

        Returns:
            (CPWork): work file
        """
        _work_dir = self.to_work_dir(task=task, dcc_=dcc_, step=step)
        return _work_dir.to_work(
            tag=tag, ver_n=ver_n, extn=extn, catch=catch, class_=class_,
            user=user, dcc_=dcc_)
