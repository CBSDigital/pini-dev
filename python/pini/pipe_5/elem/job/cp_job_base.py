"""Tools for managing jobs."""

# pylint: disable=too-many-public-methods

import logging
import operator
import os

from pini import dcc, icons
from pini.utils import (
    Dir, abs_path, single, norm_path, merge_dicts, to_str,
    apply_filter, DATA_PATH, File, cache_on_obj, EMPTY, cache_result,
    is_abs)

from .. import cp_settings_elem
from ... import cp_template
from ...cp_utils import map_path
from .. import root

_LOGGER = logging.getLogger(__name__)

_DEFAULT_CFG_NAME = "Quirinus"
_DEFAULT_CFG = {
    'defaults': {},
    'name': None,
    'tasks': {},
    'templates': {},
    'tokens': {
        'asset_type': {'filter': None},
        'sequence': {'filter': None, 'whitelist': []},
        'dcc': {'allowed': dcc.DCCS},
        'tag': {'default': None, 'nounderscore': True},
        'ver': {'len': 3, 'strict_len': True},
    }}


class CPJobBase(cp_settings_elem.CPSettingsLevel):
    """Represents a job on disk.

    This is the top-level folder for any film/commercial.
    """

    def __init__(self, path):
        """Constructor.

        Args:
            path (str): path within the job
        """
        _path = abs_path(to_str(path))
        _root = root.ROOT
        _rel_path = _root.rel_path(_path)
        _path = _root.to_subdir(_rel_path.split('/')[0])
        super().__init__(_path)
        self.name = self.filename

    @property
    def cfg_file(self):
        """Obtain config file for this job.

        Returns:
            (File): config
        """
        _path = os.environ.get('PINI_PIPE_CFG_PATH', '.pini/config.yml')
        _file = self.to_file(_path) if not is_abs(_path) else File(_path)
        _file = File(map_path(_file.path))
        return _file

    @cache_on_obj
    def get_cfg(self, force=False):
        """Obtain job config.

        Args:
            force (bool): force reread config from disk

        Returns:
            (dict): job config
        """
        _yml_cfg = self.cfg_file.read_yml(catch=True)
        _cfg = merge_dicts(_DEFAULT_CFG, _yml_cfg)
        if 'name' in _cfg and _cfg['name']:
            assert _cfg['name'] == _yml_cfg['name']
        return _cfg

    def create(self, cfg_name=_DEFAULT_CFG_NAME):
        """Create this job on disk.

        Args:
            cfg_name (str): name of config to use

        Returns:
            (CPJob): updated job
        """
        from pini import qt
        qt.ok_cancel(
            f'Create new job using <i>{cfg_name}</i> structure?'
            f'<br><br>{self.path}',
            icon=icons.find('Rosette'), title='Create job')
        self.mkdir()
        self.setup_cfg(cfg_name)
        return self

    def setup_cfg(self, name=_DEFAULT_CFG_NAME):
        """Setup config file for this job.

        Args:
            name (str): name of config to apply
        """
        _dir = Dir(DATA_PATH).to_subdir('job_templates')
        _tmpl_cfg = single(_dir.find(
            depth=1, extn='yml', base=name, class_=True))
        _LOGGER.info('SETUP CFG %s', _tmpl_cfg)
        _tmpl_cfg.copy_to(self.cfg_file)

    @property
    def cfg(self):
        """Obtain config data.

        This is used to configure the pipeline and should be pretty
        static - changing it in an active job should normally be avoided.
        It is used to define paths and naming conventions.

        Returns:
            (dict): job config
        """
        return self.get_cfg()

    @property
    def templates(self):
        """Obtain templates data, read from config.

        Returns:
            ({name: Template list} dict): template name/object data
        """
        return self._build_templates()

    @cache_result
    def _build_templates(self, force=False, catch=True):
        """Build templates data from config into Template objects.

        To handling optional tokens (not supported by lucidity), optional
        tokens are expanded to a list of all the possible options. For
        this reason, each template name had a list of template options to
        apply. In most cases this will just contain a single item.

        Args:
            force (bool): force rebuild templates from config
            catch (bool): catch any errors and return an empty dict

        Returns:
            ({name: Template list} dict): template name/object data
        """
        _LOGGER.debug('BUILD TEMPLATE %s', self)
        return cp_template.build_job_templates(job=self, catch=catch)

    def find_template(
            self, type_, profile=None, dcc_=EMPTY, alt=EMPTY,
            has_key=None, want_key=None, catch=False):
        """Find a single template within this job's templates.

        Args:
            type_ (str): template type (eg. shot_entity_path/work)
            profile (str): template profile (ie. asset/shot)
            dcc_ (str): template dcc (eg. nuke/maya)
            alt (int): filter by alt version of template
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (list): list of keys which are preferred
                but not necessary
            catch (bool): no error if no matching template found

        Returns:
            (CPTemplate): matching template
        """
        _LOGGER.log(9, 'FIND TEMPLATE %s', type_)

        # Find matching templates
        _tmpls = self.find_templates(
            type_=type_, profile=profile, dcc_=dcc_, has_key=has_key,
            want_key=want_key, alt=alt)
        if len(_tmpls) == 1:
            return single(_tmpls)
        _LOGGER.log(9, ' - FOUND %s TEMPLATES', len(_tmpls))

        # Apply alt filtering
        _alts = sorted({_tmpl.alt for _tmpl in _tmpls})
        if len(_alts) > 1:
            _tmpls = [_tmpl for _tmpl in _tmpls if _tmpl.alt == _alts[0]]
            _LOGGER.log(9, ' - DISCARDING ALTS %d %s', len(_tmpls), _alts)

        try:
            return single(_tmpls, catch=catch)
        except ValueError:
            _LOGGER.log(
                9, 'FAILED TO FIND TEMPLATE tmpls=%d has_key=%s want_key=%s '
                'tmpls=%s', len(_tmpls), has_key, want_key, _tmpls)
            raise ValueError(
                f'Failed to find template "{type_}" in {self.name}')

    @cache_result
    def find_template_by_pattern(self, pattern):
        """Find template by its pattern.

        Args:
            pattern (str): pattern to match

        Returns:
            (CPTemplate): matching template
        """
        _tmpl = single(self.find_templates(pattern=pattern), catch=True)
        if not _tmpl:
            raise ValueError(f'Failed to match pattern {pattern}')
        return _tmpl

    def find_templates(
            self, type_=None, profile=None, dcc_=EMPTY, alt=EMPTY, has_key=None,
            want_key=None, pattern=None):
        """Find templates in this job.

        The list is sorted in order of precendence, ie. a nuke_shot_work
        template will take precendence over a shot_work template, which
        will take precendence over a generic work template.

        Args:
            type_ (str): template type (eg. work_dir/work/entity_path)
            profile (str): filter by profile (ie. asset/shot)
            dcc_ (str): filter by dcc
            alt (int): filter by alt version of template
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (dict): dict of keys which are preferred
                but not necessary
            pattern (str): match template by pattern

        Returns:
            (CPTemplate list): matching templates
        """
        _LOGGER.log(9, 'FIND TEMPLATES %s type_=%s', self.name, type_)

        # Apply simple filters
        assert profile in ['shot', 'asset', None]
        _tmpls = []
        for _tmpl in sum(self.templates.values(), []):
            if type_ and _tmpl.type_ != type_:
                continue
            if profile and _tmpl.profile not in (None, profile):
                continue
            if pattern and _tmpl.pattern != pattern:
                continue
            if alt is not EMPTY and _tmpl.alt != alt:
                continue
            _tmpls.append(_tmpl)

        # Apply complex filters
        if dcc_ is not EMPTY:
            _tmpls = self._find_templates_dcc(_tmpls, dcc_=dcc_)
        if has_key:
            _tmpls = self._find_templates_has_key(_tmpls, has_key=has_key)
        if want_key:
            _tmpls = self._find_templates_want_key(_tmpls, want_key=want_key)

        _tmpls = sorted(_tmpls, key=operator.attrgetter('name'))
        return _tmpls

    def _find_templates_dcc(self, templates, dcc_):
        """Find templates matching the given dcc.

        If no templates match the given dcc then the filter is not applied.

        Args:
            templates (CPTemplate list): list of templates to filter
            dcc_ (str): dcc filter to apply

        Returns:
            (CPTemplate list): matching templates
        """
        _dcc_tmpls = [_tmpl for _tmpl in templates if _tmpl.dcc == dcc_]
        if _dcc_tmpls:
            _tmpls = _dcc_tmpls
        else:
            _tmpls = [_tmpl for _tmpl in templates if not _tmpl.dcc]
        return _tmpls

    def _find_templates_has_key(self, templates, has_key):
        """Find templates with specific keys.

        Args:
            templates (CPTemplate list): list of templates to filter
            has_key (dict): dict of keys and whether that key should
                be present in the template

        Returns:
            (CPTemplate list): matching templates
        """
        _tmpls = templates
        _LOGGER.debug(' - APPLY HAS KEY %s', has_key)
        assert isinstance(has_key, dict)
        for _key, _toggle in has_key.items():
            _tmpls = [_tmpl for _tmpl in _tmpls
                      if (_key in _tmpl.keys()) == _toggle]
        _LOGGER.debug(' - APPLIED HAS KEY %d %s', len(_tmpls), _tmpls)
        return _tmpls

    def _find_templates_want_key(self, templates, want_key):
        """Find templates with specific keys if they're available.

        If a want key is available, templates with that key are returned.
        However, if the key in unavailable then no filter is applied.

        Args:
            templates (CPTemplate list): list of templates to filter
            want_key (dict): dict of keys which are preferred
                but not necessary

        Returns:
            (CPTemplate list): matching templates
        """
        _tmpls = templates
        _LOGGER.debug(' - APPLY WANT KEY %s %s', want_key, _tmpls)
        assert isinstance(want_key, dict)
        for _key, _toggle in want_key.items():
            _matching_tmpls = [_tmpl for _tmpl in _tmpls
                               if (_key in _tmpl.keys()) == _toggle]
            if _matching_tmpls:
                _tmpls = _matching_tmpls
                _LOGGER.debug('   - ALLOWED %s FILTER', _key)
        _LOGGER.debug(' - APPLIED WANT KEY %d %s', len(_tmpls), _tmpls)
        return _tmpls

    def create_asset_type(self, asset_type, force=False, parent=None):
        """Create an asset type within this job.

        Args:
            asset_type (str): name of asset type to create
            force (bool): create asset type without confirmation dialogs
            parent (QDialog): parent for confirmation dialogs
        """
        _LOGGER.info('CREATE ASSET TYPE %s', asset_type)

        # Obtain asset type dir
        _tmpl = self.find_template('entity_path', profile='asset')
        _tmpl = _tmpl.crop_to_token('asset_type')
        _tmpl = _tmpl.apply_data(job_path=self.path)
        _LOGGER.info(' - TMPL %s', _tmpl)
        _type_dir = Dir(_tmpl.format(asset_type=asset_type))
        _LOGGER.info(' - ASSET TYPE DIR %s', _type_dir)
        assert _type_dir.filename == asset_type
        assert not _type_dir.exists()

        # Confirm
        if not force:
            from pini import qt
            qt.ok_cancel(
                f'Create new asset type {asset_type} in {self.name}?'
                f'\n\n{_type_dir.path}',
                icon=icons.BUILD, title='Create asset type',
                parent=parent)

        _type_dir.mkdir()

    def find_asset_types(self):
        """Find asset types inside this job.

        Returns:
            (str list): asset types
        """
        _LOGGER.debug('FIND ASSET TYPES %s', self.name)

        # Apply filter
        _types = self._read_all_asset_types()
        _filter = self.cfg['tokens']['asset_type']['filter']
        if _filter:
            _LOGGER.debug(' - FILTER %s', _filter)
            _types = apply_filter(_types, _filter)
            _LOGGER.debug(' - TYPES %s', _types)

        return _types

    def _read_all_asset_types(self):
        """Read all available asset types.

        Returns:
            (str list): asset type names
        """
        raise NotImplementedError

    def find_asset(self, match=None, catch=False, **kwargs):
        """Find an asset in this job.

        Args:
            match (str): match by name or label (eg. char.robot)
            catch (bool): no error if asset not found

        Returns:
            (CPAsset): matching asset
        """
        _LOGGER.debug('FIND ASSET %s', match)
        _assets = self.find_assets(**kwargs)
        _LOGGER.debug(' - FOUND %d ASSETS', len(_assets))
        if len(_assets) == 1:
            return single(_assets)

        # Match by name
        _name_assets = [_asset for _asset in _assets if _asset.name == match]
        _LOGGER.debug(' - NAME ASSETS %s', len(_name_assets))
        if len(_name_assets) == 1:
            return single(_name_assets)

        # Match by label
        for _asset in _assets:
            _label = f'{_asset.asset_type}.{_asset.name}'
            _LOGGER.debug(' - TESTING %s', _label)
            if _label == match:
                return _asset

        if catch:
            return None
        raise ValueError(match)

    def find_assets(self, asset_type=None, filter_=None):
        """Find assets in this job.

        Args:
            asset_type (str): filter by type
            filter_ (str): apply path filter

        Returns:
            (CPAsset list): matching assets
        """
        raise NotImplementedError

    def find_sequence(self, match=None):
        """Find a sequence in this job.

        Args:
            match (str): match by name

        Returns:
            (CPSequence): matching sequence
        """
        _seqs = self.find_sequences()

        if not match:
            return single(_seqs)

        # Try exact name match
        _name_seqs = [_seq for _seq in _seqs if _seq.name == match]
        if len(_name_seqs) == 1:
            return single(_name_seqs)

        # Try filter match
        _filter_seqs = apply_filter(
            _seqs, match, key=operator.attrgetter('name'))
        if len(_filter_seqs) == 1:
            return single(_filter_seqs)

        raise ValueError(match)

    def find_sequences(self, class_=None, filter_=None, head=None):
        """Find sequences in this job.

        Args:
            class_ (class): override sequence class
            filter_ (str): filter by sequence name
            head (str): filter by sequence name prefix

        Returns:
            (str|CPSequence list): sequences
        """
        from pini import pipe

        _LOGGER.debug('FIND SEQUENCES')

        _LOGGER.debug(' - SEQUENCES AS DIRS')

        _class = class_ or pipe.CPSequence
        _filter = self.cfg['tokens']['sequence']['filter']
        _LOGGER.debug(' - FILTER %s', _filter)

        # Build sequence objects
        _seqs = []
        for _path in self._find_sequence_paths():
            try:
                _seq = _class(_path, job=self)
            except ValueError:
                _LOGGER.debug('   - INVALID SEQ %s', _path)
                continue
            _seqs.append(_seq)
        _filter_key = operator.attrgetter('filename')

        if filter_:
            _seqs = apply_filter(_seqs, filter_, key=_filter_key)
        if head:
            _seqs = [_seq for _seq in _seqs
                     if _filter_key(_seq).startswith(head)]

        return _seqs

    def _find_sequence_paths(self):
        """Find paths to all sequences.

        Returns:
            (str list): sequence path
        """
        raise NotImplementedError

    def find_shot(self, match, sequence=None, catch=False):
        """Find shot within this job.

        Args:
            match (str): match by shot name
            sequence (str): filter by sequence
            catch (bool): no error if shot not found

        Returns:
            (CPShot): matching shot
        """
        _match = norm_path(match)
        _LOGGER.debug('FIND SHOT %s %s', match, _match)
        _shots = self.find_shots(sequence=sequence)
        _LOGGER.debug(' - FOUND %d SHOTS', len(_shots))

        # Test name match
        _name_shot = single([
            _shot for _shot in _shots if _shot.name == _match], catch=True)
        if _name_shot:
            return _name_shot

        # Test path match
        _path_shot = single([
            _shot for _shot in _shots
            if _match.startswith(_shot.path)], catch=True)
        if _path_shot:
            return _path_shot

        # Test sequence match
        _seq_match = single([
            _shot for _shot in _shots if _shot.sequence == _match], catch=True)
        if _seq_match:
            return _seq_match

        if catch:
            return None
        raise ValueError('Failed to find shot '+match)

    def find_shots(self, sequence=None, class_=None, filter_=None):
        """Find shots in this job.

        Args:
            sequence (str): filter by sequence
            class_ (class): override shot class
            filter_ (str): filter by shot name

        Returns:
            (CPShot list): matching shots
        """
        from pini import pipe
        _LOGGER.debug('FIND SHOTS %s class=%s filter=%s', self, class_, filter_)

        # Get sequence dirs to search
        if isinstance(sequence, pipe.CPSequence):
            _seqs = [sequence]
        elif isinstance(sequence, str):
            _seq = self.find_sequence(sequence)
            _seqs = [_seq] if _seq else []
        elif sequence is None:
            _seqs = self.find_sequences()
        else:
            raise ValueError(sequence)
        _LOGGER.debug(' - SEQS %s', _seqs)

        # Read shots from seqs
        _shots = []
        for _seq in _seqs:
            _seq_shots = _seq.find_shots(class_=class_, filter_=filter_)
            _LOGGER.debug(
                ' - ADDING SEQ SHOTS %s %s', _seq.name,
                [_shot.name for _shot in _seq_shots])
            _shots += _seq_shots

        return _shots

    def read_type_assets(self, asset_type, class_=None):
        """Read assets of the given type from this job.

        Args:
            asset_type (str): type to read (eg. char/veh)
            class_ (class): override asset class

        Returns:
            (CPAsset list): assets of given type
        """
        from pini import pipe
        _LOGGER.debug('READ TYPE ASSETS %s', asset_type)

        _class = class_ or pipe.CPAsset
        _LOGGER.debug(' - ASSET CLASS %s', _class)

        # Cast to asset objects
        _assets = []
        for _path in self._read_type_asset_paths(asset_type=asset_type):
            _LOGGER.debug(' - BUILD ASSET %s', _path)
            try:
                _asset = _class(_path, job=self)
            except ValueError:
                continue
            _assets.append(_asset)

        return _assets

    def _read_type_asset_paths(self, asset_type):
        """Read asset paths in the given asset type dir.

        Args:
            asset_type (str): asset type (eg. char)

        Returns:
            (str list): asset type paths
        """
        raise NotImplementedError

    def find_entity(self, match):
        """Find entity in this job.

        Args:
            match (str): match by label (eg. mercury/rnd010)

        Returns:
            (CPEntity): matching entity
        """
        from pini import pipe
        _LOGGER.debug('FIND ENTITY %s', match)

        if isinstance(match, str):
            if '.' in match:
                return self.find_asset(match)
            return self.find_shot(match)

        if isinstance(match, (pipe.CPAsset, pipe.CPShot)):
            _etys = self.find_entities()
            _LOGGER.debug(' - FOUND %d ETYS %s', len(_etys), _etys)
            return single(_ety for _ety in _etys if _ety == match)

        raise NotImplementedError(match)

    def find_entities(self, entity_type=None, filter_=None):
        """Find entities in this job.

        Args:
            entity_type (str): filter by entity type (ie. asset type
                or sequence name)
            filter_ (str): apply path filter

        Returns:
            (CPEntity list): entities (shots + assets)
        """
        _etys = self.find_assets() + self.find_shots()
        if entity_type:
            _etys = [_ety for _ety in _etys
                     if _ety.entity_type == entity_type]
        if filter_:
            _etys = apply_filter(
                _etys, filter_, key=operator.attrgetter('path'))
        return _etys

    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        raise NotImplementedError

    def to_asset(self, asset_type, asset, class_=None, catch=True):
        """Build an asset object for an asset within this job.

        Args:
            asset_type (str): asset type (eg. char/veh)
            asset (str): asset name (eg. deadHorse)
            class_ (class): override asset class
            catch (bool): no error if fail to build valid asset

        Returns:
            (CPAsset): asset object
        """
        from pini import pipe

        # Obtain template
        _tmpl = self.find_template('entity_path', profile='asset', catch=True)
        if not _tmpl:
            if catch:
                return None
            raise ValueError('No matching template')

        # Build asset
        _path = _tmpl.format(dict(  # pylint: disable=use-dict-literal
            job_path=self.path, asset_type=asset_type, asset=asset))
        _class = class_ or pipe.CPAsset
        try:
            return _class(_path, job=self)
        except ValueError as _exc:
            if not catch:
                raise _exc
            return None

    def to_sequence(self, sequence, class_=None, catch=False):
        """Build a sequence object for this job.

        Args:
            sequence (CPSequence): sequence name
            class_ (class): override sequence class
            catch (bool): no error if no valid sequence created

        Returns:
            (CPSequence): sequence
        """
        from pini import pipe
        _LOGGER.debug('TO SEQUENCE')
        _class = class_ or pipe.CPSequence

        # Obtain template
        _tmpl = self.find_template('entity_path', profile='shot', catch=True)
        if not _tmpl:
            if catch:
                return None
            raise ValueError
        _tmpl = _tmpl.crop_to_token('sequence')
        _LOGGER.debug(' - TMPL %s', _tmpl)

        # Build path
        _path = _tmpl.format(job_path=self.path, sequence=sequence)
        _LOGGER.debug(' - PATH %s', _path)

        # Build sequence object
        try:
            _result = _class(_path, job=self)
        except ValueError:
            _result = None
        _LOGGER.debug(' - RESULT %s', _result)

        return _result

    def to_shot(self, shot, sequence=None, class_=None):
        """Build a shot object based on the given args.

        Args:
            shot (str): shot name
            sequence (str): sequence
            class_ (class): override shot type

        Returns:
            (CPShot): shot object
        """
        _LOGGER.debug('TO SHOT %s %s', self, shot)
        from pini import pipe

        _tmpl = self.find_template('entity_path', profile='shot')

        # Set up sequence
        _seq = sequence
        if isinstance(sequence, pipe.CPSequence):
            _seq = _seq.name
        if not _seq and 'sequence' in _tmpl.keys():
            raise ValueError('Missing sequence key')

        # Apply data to template
        _path = _tmpl.format(
            job_path=self.path, sequence=_seq, shot=shot)
        _class = class_ or pipe.CPShot
        try:
            return _class(_path, job=self)
        except ValueError as _exc:
            _LOGGER.debug(' - EXC %s', _exc)
            return None

    def to_empty_file(self, dcc_=None):
        """Obtain an empty file for this job.

        This is a template file which is loaded on new scene creation.

        Args:
            dcc_ (str): empty file dcc

        Returns:
            (File): empty file path
        """
        _dcc = dcc_ or dcc.NAME
        if _dcc == dcc.NAME:
            _extn = dcc.DEFAULT_EXTN
        else:
            _extn = {'nuke': 'nk', 'maya': 'ma'}[_dcc]

        _tmpl = self.find_template('empty_file', catch=True, dcc_=_dcc)
        if not _tmpl:
            _LOGGER.info('NO EMPTY FILE TEMPLATE FOUND IN CFG')
            return None

        _file = File(_tmpl.format(dict(  # pylint: disable=use-dict-literal
            job_path=self.path, dcc=_dcc, extn=_extn)))
        if not _file.exists():
            _LOGGER.info('EMPTY FILE IS MISSING %s', _file.path)
            return None
        _LOGGER.info('FOUND EMPTY FILE %s', _file.path)
        return _file

    def __lt__(self, other):
        return self.name.lower() < other.name.lower()
