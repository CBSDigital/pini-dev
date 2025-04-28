"""Tools for managing work files."""

# pylint: disable=too-many-instance-attributes,too-many-lines

import copy
import logging
import os
import platform
import sys
import time

import lucidity

from pini import dcc
from pini.utils import (
    File, strftime, get_user, passes_filter, single, EMPTY, abs_path,
    Video, Seq, plural, find_callback)

from ..work_dir import CPWorkDir, map_task
from ...cp_utils import EXTN_TO_DCC, validate_tokens, cur_user
from ... import cp_utils
from . import cp_work_bkp

_LOGGER = logging.getLogger(__name__)


class CPWorkBase(File):  # pylint: disable=too-many-public-methods
    """Represents a work file on disk."""

    entity_type = None
    asset_type = None
    asset = None
    sequence = None
    shot = None
    step = None
    task = None

    tag = None
    user = None
    ver = None

    def __init__(self, file_, work_dir=None, template=None):
        """Constructor.

        Args:
            file_ (str): path to work file
            work_dir (CPWorkDir): force parent work dir
            template (CPTemplate): force template
        """
        _file = abs_path(file_)
        _LOGGER.debug('INIT %s %s', type(self).__name__, file_)
        super().__init__(_file)

        if self.extn not in EXTN_TO_DCC:
            raise ValueError(self.extn)
        self.dcc = EXTN_TO_DCC[self.extn]

        # Set up entity/job
        self.work_dir = work_dir or CPWorkDir(_file)
        self.entity = self.work_dir.entity
        self.job = self.entity.job

        # Pass attrs
        self.profile = self.entity.profile
        self.entity_type = self.entity.entity_type
        self.asset_type = self.entity.asset_type
        self.asset = self.entity.asset
        self.sequence = self.entity.sequence
        self.shot = self.entity.shot
        self.task = self.work_dir.task
        self.step = self.work_dir.step

        # Find templates
        if template:
            _tmpls = [template]
        else:
            _tmpls = [
                _tmpl.apply_data(
                    work_dir=self.work_dir.path, entity=self.entity.name,
                    task=self.work_dir.task, extn=self.extn,
                    step=self.work_dir.step, shot=self.entity.name)
                for _tmpl in self.job.find_templates(
                    type_='work', profile=self.entity.profile,
                    dcc_=self.dcc)]
        _LOGGER.log(9, ' - TMPLS %s', _tmpls)

        # Extract data - use single template if possible for better error
        if len(_tmpls) == 1:
            self.template = single(_tmpls)
            try:
                _data = self.template.parse(self.path)
            except lucidity.ParseError as _exc:
                _LOGGER.debug(' - TMPL %s', self.template)
                _LOGGER.debug(' - EXC %s', _exc)
                raise ValueError('Lucidity rejected ' + self.path) from _exc
        else:
            try:
                self.data, self.template = lucidity.parse(self.path, _tmpls)
            except lucidity.ParseError as _exc:
                _LOGGER.debug(' - EXC %s', _exc)
                raise ValueError('Lucidity rejected ' + self.path) from _exc
        validate_tokens(_data, job=self.job)

        # Setup up data
        self.data = {}
        self.data.update(self.work_dir.data)
        self.data.update(_data)
        self.data['dcc'] = self.dcc or self.data.get('dcc')

        # Setup attrs
        for _key, _val in self.data.items():
            if _key in ('entity', 'work_dir', 'job'):
                continue
            setattr(self, _key, _val)
        self.sequence = self.entity.sequence
        self.ver_n = int(self.ver)
        self.metadata_yml = self.to_dir().to_file(
            f'.pini/metadata/{self.base}.yml')
        self.thumb = self.to_dir().to_file(
            f'.pini/thumb/{self.base}.jpg')
        self.image = self.to_dir().to_file(
            f'.pini/image/{self.base}.jpg')

    @property
    def cmp_key(self):
        """Obtain sort key for this work file.

        This allows work files to be sorted by version, even if there is
        a username token embedded in the path.

        Returns:
            (tuple): sort key
        """
        return self.work_dir.path, self.filename

    @property
    def metadata(self):
        """Object work metadata.

        Returns:
            (dict): metadata
        """
        return self._read_metadata()

    @property
    def notes(self):
        """Obtain work notes.

        Returns:
            (str): notes
        """
        return self.metadata.get('notes')

    @property
    def pini_task(self):
        """Obtain pini task for this work file.

        eg. surf/dev -> lookdev

        Returns:
            (str): pini task
        """
        return map_task(task=self.task, step=self.step)

    def find_template(
            self, type_, has_key=None, want_key=None, dcc_=None, catch=False):
        """Find template with keys matching this work file.

        Args:
            type_ (str): template type
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (list): list of keys which are preferred
                but not necessary
            dcc_ (str): filter by dcc
            catch (bool): no error if exactly one template isn't found

        Returns:
            (CPTemplate): matching template
        """
        _LOGGER.debug('FIND TEMPLATE %s', type_)

        # Set has_key (required keys)
        _has_key = {'ver': True}
        if has_key:
            _has_key.update(has_key)
        _LOGGER.debug(' - HAS KEY %s', _has_key)

        # Set want_key (desired keys)
        _want_key = {'tag': bool(self.tag),
                     'user': bool(self.user)}
        if want_key:
            _want_key.update(want_key)
        _LOGGER.debug(' - WANT KEY %s', _want_key)

        _dcc = dcc_ or EXTN_TO_DCC[self.extn]
        return self.entity.find_template(
            type_=type_, has_key=_has_key, dcc_=_dcc, want_key=_want_key,
            catch=catch)

    def _read_metadata(self):
        """Read work metadata from disk.

        Returns:
            (dict): metadata
        """
        if self.metadata_yml.exists():
            _data = self.metadata_yml.read_yml()
        elif not self.exists():
            _data = {}
        else:
            _owner = self.user or super().owner()
            _mtime = int(File(self).mtime())
            _data = {
                'size': self.size(),
                'owner': _owner,
                'mtime': _mtime,
            }
            self.metadata_yml.write_yml(_data)
        return _data

    def find_latest(self, catch=False):
        """Find latest version of this work file.

        Args:
            catch (bool): no error if no versions found

        Returns:
            (CPWork): latest version
        """
        _vers = self.find_vers()
        if _vers:
            return _vers[-1]
        if catch:
            return None
        raise ValueError('No versions found ' + self.path)

    def find_next(self, user=None, class_=None):
        """Find next version, ie. one after the latest one.

        This version should not exist on disk.

        Args:
            user (str): override user
            class_ (class): override work file class

        Returns:
            (CPWork): next version
        """
        _LOGGER.debug('FIND NEXT %s', self)

        _latest = self.find_latest(catch=True)
        _LOGGER.debug(' - LATEST %s', _latest)

        # Determine next version
        if not _latest:
            _ver_n = 1
        else:
            _ver_n = _latest.ver_n + 1
        _user = user or cur_user()

        _extn = self.extn
        if self.dcc == dcc.NAME:
            _extn = dcc.DEFAULT_EXTN
        _next = self.to_work(
            ver_n=_ver_n, class_=class_, user=_user, extn=_extn)
        assert _next.work_dir is self.work_dir
        return _next

    def find_vers(self):
        """Find all versions of this work file.

        Returns:
            (CPWork list): work file list
        """
        if dcc.NAME == self.dcc:
            _extns = dcc.VALID_EXTNS
        else:
            _extns = [self.extn]
        return self.work_dir.find_works(tag=self.tag, extns=_extns)

    def has_bkp(self):
        """Test if this file has a corresponding backup file.

        This assumed that the mtime in the work metadata matches
        the mtime of the backup file.

        Returns:
            (bool): whether bkp file exists
        """
        _data = self.metadata
        _mtime = _data.get('mtime', int(File(self).mtime()))
        _bkp = self._to_bkp_file(mtime=_mtime)
        return _bkp.exists()

    def _to_bkp_file(self, mtime=None, extn=None):
        """Build a backup file object.

        Args:
            mtime (int): backup mtime
            extn (str): override backup extension

        Returns:
            (File): backup file
        """
        _mtime = mtime or time.time()
        _extn = extn or self.extn
        _t_stamp = strftime(cp_work_bkp.BKP_TSTAMP_FMT, _mtime)
        return self.to_dir().to_file(
            f'.pini/bkp/{self.base}/{_t_stamp}.{_extn}')

    def find_bkps(self):
        """Find backup files belonging to this work.

        Returns:
            (File list): backup files
        """
        _bkp_dir = self._to_bkp_file().to_dir()
        return _bkp_dir.find(
            depth=1, type_='f', extn=self.extn, class_=cp_work_bkp.CPWorkBkp,
            catch_missing=True)

    def flush_bkps(self, reason_filter=None):  # pylint: disable=arguments-differ
        """Remove backup files.

        Args:
            reason_filter (str): filter list by reason
        """
        for _bkp in self.find_bkps():
            if reason_filter and not passes_filter(_bkp.reason, reason_filter):
                continue
            _LOGGER.info(' - DELETE BKP %s %s', _bkp.reason, _bkp)
            _bkp.yml.delete(force=True)
            _bkp.delete(force=True)

    def find_output(self, type_=None, catch=False, **kwargs):
        """Find a matching output belonging to this work file.

        Args:
            type_ (str): filter by type (eg. publish/cache)
            catch (bool): no error if didn't match exactly one output

        Returns:
            (CPOutput): matching output
        """
        _outs = self.find_outputs(type_=type_, **kwargs)
        return single(_outs, catch=catch, items_label='outputs')

    def find_outputs(self, type_=None, **kwargs):
        """Find outputs generated from this work file.

        Args:
            type_ (str): filter by type (eg. publish/cache)

        Returns:
            (CPOutput list): matching outputs
        """
        from pini import pipe
        _outs = []
        for _out in self._read_outputs():
            if not pipe.passes_filters(_out, type_=type_, **kwargs):
                continue
            _outs.append(_out)
        return _outs

    def is_latest(self):
        """Test whether this is the latest version.

        Returns:
            (bool): whether latest
        """
        return self == self.find_latest()

    def _owner_from_user(self):
        """Obtain owner based on user tag.

        Returns:
            (str|None): owner (if any)
        """
        return self.user

    def _read_outputs(self):
        """Read disk to find outputs outputs generated from this work file.

        Returns:
            (CPOutput list): outputs
        """
        _LOGGER.debug('READ OUTPUTS %s', self)
        _outs = self._read_outputs_from_pipe()

        # Update image thumbnail
        self._check_image(_outs)

        return _outs

    def _read_outputs_from_pipe(self):
        """Read outputs from current pipeline."""
        raise NotImplementedError

    def _check_image(self, outputs):
        """Check this work file's thumbnail image against the given outputs.

        If the image doesn't exist and there are convertable outputs (ie. videos
        or image sequences), it will be generated from the outputs.

        Args:
            outputs (CPOutput list): outputs from this work file
        """
        _LOGGER.debug(' - CHECK IMAGE')
        if self.image.exists():
            _LOGGER.debug(' - IMAGE EXISTS')
            return

        # Check videos
        _vids = [_out for _out in outputs if isinstance(_out, Video)]
        if _vids:
            _vid = _vids[0]
            _LOGGER.info(' - EXTRACT FRAME %s', _vid)
            _img = _vid.to_frame(self.image)
            _LOGGER.info(' - IMG %s', _img)
            assert self.image.exists()
            return

        # Check seqs
        _seqs = sorted(
            [_out for _out in outputs if isinstance(_out, Seq)],
            key=cp_utils.output_clip_sort)
        if _seqs:
            _seqs[0].build_thumbnail(self.image)

    def save(
            self, notes=None, reason=None, mtime=None, parent=None,
            force=None):
        """Save this work version.

        Args:
            notes (str): notes for save
            reason (str): save reason (for backup label)
            mtime (int): force save mtime
            parent (QDialog): parent dialog for confirmation dialogs
            force (bool): overwrite existing + create entity
                without confirmation

        Returns:
            (CPWorkBkp): backup file
        """
        _LOGGER.debug('SAVE WORK %s', self)

        if not self.work_dir.exists():
            self.work_dir.create(force=force)

        # Determine globals
        _mtime = mtime or int(time.time())
        _LOGGER.debug(
            ' - MTIME %s %s %s', _mtime, strftime('%H:%M:%S', _mtime), mtime)
        _reason = reason
        _notes = notes or self.notes
        if _notes:
            _notes = str(_notes)
        _force = force
        if (  # Save over existing without confirmation if owner matches
                _force is None and
                dcc.cur_file() == self.path and
                self.metadata.get('owner') == get_user()):
            _force = True

        # Backup any existing file if needed
        if not self.exists():
            _LOGGER.debug(' - NEW SAVE')
            _reason = _reason or 'new save'
        else:
            if not self.has_bkp():
                _LOGGER.debug(' - SAVING EXISTING WORK W/O BKP')
                _metadata = self.metadata
                _owner = _metadata.get('owner', self.owner())
                _owner = _owner or self.user
                _LOGGER.debug(' - OWNER %s', _owner)
                _e_mtime = int(File(self).mtime())
                self._save_bkp(
                    source=self, reason='backup existing', notes=_notes,
                    owner=_owner, mtime=_e_mtime)
            else:
                _LOGGER.debug(' - EXISTING FILE HAS BKP')
            _reason = reason or 'save over'

        self._apply_sanity_check_on_new_entity(force=force)

        # Save file + bkp + metadata
        _LOGGER.debug(' - SAVE SCENE %s', self.path)
        dcc.save(file_=self.path, force=_force, parent=parent)
        self._save_metadata(notes=_notes, mtime=_mtime)
        _bkp = self._save_bkp(
            source=self, reason=_reason, mtime=_mtime, notes=_notes,
            owner=get_user())

        self.set_env()

        return _bkp

    def _apply_sanity_check_on_new_entity(self, force, enabled=False):
        """Apply sanity check on new entity.

        Args:
            force (bool): ignore checks
            enabled (bool): enable this feature
        """
        _ety_path = dcc.get_scene_data('EntityPath')
        if not force and enabled:
            raise NotImplementedError
            # from pini.tools import sanity_check
            # sanity_check.launch_new_scene_ui(

        dcc.set_scene_data('EntityPath', self.entity.path)

    def _save_bkp(
            self, reason, source=None, mtime=None, owner=None, notes=None):
        """Save a backup file.

        Args:
            reason (str): backup reason
            source (File): source file
            mtime (int): backup mtime
            owner (str): force owner
            notes (str): notes for bkp metadata
        """
        _LOGGER.debug('SAVE BKP mtime=%s', mtime)

        # Check vars
        assert reason.islower()
        _mtime = mtime or self.metadata.get('mtime') or int(self.mtime())
        _LOGGER.debug(' - MTIME %s', _mtime)
        assert isinstance(_mtime, int)
        _data = {'owner': owner or self.metadata.get('owner'),
                 'notes': notes or self.metadata.get('notes'),
                 'reason': reason}
        _src = source or self

        # Determine bkp path
        _bkp = self._to_bkp_file(mtime=_mtime)
        _LOGGER.debug(' - BKP %s', _bkp.path)

        # Save bkp
        File(_src).copy_to(_bkp, force=True)
        _LOGGER.debug(' - SAVED BKP %s', _bkp.path)
        _bkp_yml = self._to_bkp_file(extn='yml', mtime=_mtime)
        _bkp_yml.write_yml(_data, force=True)
        _LOGGER.debug(' - SAVED BKP YML %s', _bkp_yml)

        return _bkp

    def _save_metadata(self, notes, mtime):
        """Save work metadata to yml.

        Args:
            notes (str): work notes
            mtime (int): work mtime
        """
        assert isinstance(mtime, int)

        _data = {}
        _data['fps'] = dcc.get_fps()
        _data['dcc'] = f'{dcc.NAME}-{dcc.to_version(str)}'
        _data['machine'] = platform.node()
        _data['mtime'] = mtime
        _data['notes'] = notes
        _data['user'] = get_user()
        _data['owner'] = self.owner()
        _data['platform'] = sys.platform
        _data['range'] = dcc.t_range()
        _data['size'] = int(os.path.getsize(self.path))

        # Obtain refs
        _refs = dcc.find_pipe_refs()
        _refs_data = {_ref.namespace: _ref.path for _ref in _refs}
        _data['refs'] = _refs_data

        self.set_metadata(_data, mode='add')

    def add_metadata(self, **kwargs):
        """Add to existing metadata."""
        _data = copy.copy(self.metadata)
        _data.update(kwargs)
        self.set_metadata(_data)

    def set_metadata(self, data, mode='replace'):
        """Set metadata for this work file.

        Args:
            data (dict): metadata to apply
            mode (str): how to apply metadata (eg. replace/add)
        """
        _data = {}
        if mode == 'replace':
            pass
        elif mode == 'add':
            _data.update(self.metadata)
        else:
            raise NotImplementedError(mode)
        _data.update(data)
        self.metadata_yml.write_yml(_data, force=True)
        _LOGGER.debug('SAVED METADATA %s', self.metadata_yml.path)

    def set_notes(self, notes):
        """Set work file notes.

        Existing metadata is maintained.

        Args:
            notes (str): notes to apply
        """
        _data = self.metadata
        _data['notes'] = notes
        self.metadata_yml.write_yml(_data, force=True)

    def set_env(self):
        """Set environment to match this work file."""
        from pini import pipe
        from pini.tools import helper

        pipe.add_recent_work(self)

        os.environ['PINI_JOB'] = self.job.name
        os.environ['PINI_JOB_PATH'] = self.job.path
        os.environ['PINI_ENTITY'] = self.entity.name
        os.environ['PINI_ENTITY_PATH'] = self.entity.path

        os.environ['PINI_TASK'] = self.task
        os.environ['PINI_TAG'] = self.tag or ''
        os.environ['PINI_VER'] = self.ver

        dcc.set_env(self)
        _callback = find_callback('SetWork')
        if _callback:
            _callback(self)

        # Update helper recent work cache
        helper.obt_recent_work(force=True)

    def load(self, parent=None, force=False, lazy=False, load_func=None):
        """Load this work file in the current dcc.

        Args:
            parent (QDialog): parent dialog for popups
            force (bool): load scene without unsaved changes warning
            lazy (bool): don't load the file if it's already open
            load_func (fn): override load function
        """
        _LOGGER.debug('LOAD WORK %s', self)

        # Obtain file to load - if this work file does not exist then
        # load the job empty file (if any)
        _file = File(self.path)
        _save = False
        if not _file.exists():
            _file = self.job.to_empty_file()
            _save = True

        # Load the file or create the scene
        if load_func:
            load_func()
        elif _file:
            dcc.load(_file, parent=parent, force=force, lazy=lazy)
        else:
            _LOGGER.debug(' - NEW SCENE')
            dcc.new_scene(force=force, parent=parent)
            _settings = self.entity.settings
            _LOGGER.debug(' - SETTINGS %s', _settings)
            _res = _settings.get('res')
            _LOGGER.debug(' - RES %s', _res)
            if _res:
                dcc.set_res(*_res)
            _fps = _settings.get('fps')
            _LOGGER.debug(' - FPS %s', _fps)
            if _fps:
                dcc.set_fps(_fps)
            _rng = _settings.get('range')
            _LOGGER.debug(' - RNG %s', _rng)
            if _rng:
                dcc.set_range(*_rng)
        if _save:
            self.save()

        self.set_env()

    def to_output(
            self, template, has_key=None, want_key=None, dcc_=None, ver_n=None,
            **kwargs):
        """Build an output from this work file's template data.

        Args:
            template (CPTemplate): output template to use
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (dict): dict of keys and whether that key are desired
                in the template
            dcc_ (str): filter by dcc
            ver_n (int): apply version number

        Returns:
            (CPOutput): output
        """
        from pini import pipe
        _LOGGER.debug('TO OUTPUT')
        _dcc = dcc_ or dcc.NAME

        # Build data
        _data = {
            'entity_path': self.entity.path,
            'entity': self.entity.name,
            'user': self.user,
            'step': self.step,
            'dcc': _dcc}
        _data.update(self.data)
        if 'data' in kwargs:
            raise TypeError
        if ver_n is not None:
            _ver_pad = self.job.cfg['tokens']['ver']['len']
            _data['ver'] = str(ver_n).zfill(_ver_pad)
        _data.update(kwargs)
        _LOGGER.debug(' - DATA %s', _data)

        # Get output class
        _tmpl = self._to_output_template(
            template=template, want_key=want_key, has_key=has_key,
            dcc_=_dcc, data=_data)
        _LOGGER.debug(' - TEMPLATE %s', _tmpl)
        if _tmpl.type_ in pipe.OUTPUT_FILE_TYPES:
            _class = pipe.CPOutputFile
        elif _tmpl.type_ in pipe.OUTPUT_VIDEO_TYPES:
            _class = pipe.CPOutputVideo
        elif _tmpl.type_ in pipe.OUTPUT_SEQ_TYPES:
            _class = pipe.CPOutputSeq
        else:
            raise ValueError(_tmpl.name)
        _LOGGER.debug(' - CLASS %s', _class)

        # Build path
        _missing_keys = [
            _key for _key in _tmpl.keys()
            if _key not in _data or _data[_key] is None]
        if 'job_prefix' in _missing_keys:
            _data['job_prefix'] = self.job.to_prefix()
            _missing_keys.remove('job_prefix')
            assert _data['job_prefix']
        if _missing_keys:
            raise ValueError(
                f'Missing key{plural(_missing_keys)} '
                f'{"/".join(_missing_keys)}')
        _path = _tmpl.format(_data)
        _LOGGER.debug(' - PATH %s', _path)

        _work_dir = self.work_dir if self.work_dir.contains(_path) else None
        if _work_dir:
            _LOGGER.debug(' - WORK DIR %s', _work_dir)
            _tmpl = _tmpl.apply_data(work_dir=_work_dir.path)
            _LOGGER.debug(' - TEMPLATE %s', _tmpl)

        return _class(_path, templates=[_tmpl], entity=self.entity,
                      work_dir=_work_dir)

    def _to_output_template(
            self, template, has_key, want_key, dcc_, data):
        """To locate template for output.

        Args:
            template (CPTemplate): output template to use
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (dict): dict of keys and whether that key are desired
                in the template
            dcc_ (str): filter by dcc
            data (dict): data to apply to template

        Returns:
            (CPTemplate): output template
        """
        from pini import pipe

        if isinstance(template, pipe.CPTemplate):
            return template

        if isinstance(template, str):
            _want_key = {}
            for _key in ['output_name', 'output_type', 'tag']:
                if _key in data:
                    _want_key[_key] = bool(data[_key])
            if want_key:
                _want_key.update(want_key)
            _LOGGER.debug(' - WANT KEY %s', _want_key)
            return self.find_template(
                template, dcc_=dcc_, has_key=has_key, want_key=_want_key)

        raise ValueError(template)

    def to_stream(self):
        """Obtain path to version zero of this stream.

        Returns:
            (str): stream key
        """
        return self.to_work(ver_n=0).path

    def to_work(
            self, task=None, tag=EMPTY, user=EMPTY, ver_n=None,
            dcc_=None, extn=EMPTY, class_=None):
        """Build a work file using this work file's template data.

        Args:
            task (str): override task
            tag (str): override tag
            user (str): over user
            ver_n (int): override version number
            dcc_ (str): override dcc
            extn (str): override extension
            class_ (class): override work file class

        Returns:
            (CPWork): mapped work file
        """
        from pini import pipe
        _LOGGER.debug('TO WORK %s', self.path)
        _class = class_ or pipe.CPWork

        # Determine work dir, maintaining current if possible
        _work_dir = self.work_dir.to_work_dir(user=user)
        _LOGGER.debug(' - WORK DIR %s', _work_dir)
        if _work_dir == self.work_dir:
            _LOGGER.debug(' - USING THIS WORK DIR')
            _work_dir = self.work_dir

        # Build data dict
        _data = copy.copy(self.data)
        _data['extn'] = extn or self.extn
        _LOGGER.debug(' - EXTN %s', self.extn)
        if user:
            _data['user'] = user
        _data['work_dir'] = _work_dir.path
        if dcc_:
            _data['dcc'] = dcc_
        if task is not None:
            _data['task'] = task
            _work_dir = self.entity.to_work_dir(task=task)
            _data['work_dir'] = _work_dir.path
        if tag is not EMPTY:
            _data['tag'] = tag
        if extn is not EMPTY:
            _data['extn'] = extn
        if ver_n is not None:
            _ver_pad = self.job.cfg['tokens']['ver']['len']
            _data['ver'] = str(ver_n).zfill(_ver_pad)
        _LOGGER.debug(' - DATA %s', _data)

        # Obtain fresh template (in case tokens have been filled in)
        _tmpl = self.job.find_template(
            'work', profile=self.entity.profile, dcc_=dcc_ or self.dcc,
            has_key={'tag': 'tag' in _data})
        _LOGGER.debug(' - TMPL %s', _tmpl)

        return _class(_tmpl.format(_data), work_dir=_work_dir)

    def __lt__(self, other):
        return self.cmp_key < other.cmp_key
