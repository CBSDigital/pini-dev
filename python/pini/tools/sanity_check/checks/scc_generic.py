"""Manages specific dcc-agnostic checks."""

import logging

from pini import dcc, pipe
from pini.utils import wrap_fn, chain_fns, Res

from ..core import SCCheck, SCPipeCheck

_LOGGER = logging.getLogger(__name__)


class CheckRefsLatest(SCPipeCheck):
    """Check all pipeline references are using the latest version."""

    dcc_filter = '-nuke -substance'

    def run(self):
        """Run this check."""
        _refs = dcc.find_pipe_refs()
        if not _refs or not self.check_cache_up_to_date():
            return
        for _ref in self.update_progress(_refs):
            self.write_log('Checking ref %s', _ref)
            if not _ref.output or _ref.is_latest():
                continue
            _latest = _ref.output.find_latest()
            _out_s = f'v{_latest.ver_n:03d}' if _latest.ver_n else 'versionless'
            _msg = (
                f'Reference {_ref.namespace} (v{_ref.output.ver_n:03d}) is '
                f'not using latest output ({_out_s})')
            _fix = wrap_fn(self.update_ref, ref_=_ref, path=_latest)
            self.add_fail(_msg, fix=_fix, node=_ref.node)

    def update_ref(self, ref_, path):
        """Update the given reference.

        Args:
            ref_ (CPipeRef): reference to update
            path (CPOutput): path to apply to reference
        """
        ref_.update(path)


class CheckAbcFpsMatchesScene(SCPipeCheck):
    """Check frame rate of referenced abcs matches current scene FPS."""

    dcc_filter = '-substance'

    def run(self):
        """Run this check."""
        self.write_log('Reading abcs')
        _abcs = dcc.find_pipe_refs(extn='abc')
        self.write_log('Found %d abcs', len(_abcs))
        if not _abcs:
            return
        _fps = dcc.get_fps()
        self.write_log('FPS %.01f', _fps)
        for _abc in self.update_progress(_abcs):
            self.write_log('Checking abc %s', _abc)
            _abc_fps = _abc.output.metadata.get('fps')
            if not _abc_fps:
                self.write_log('FPS missing from metadata %s', _abc)
                continue
            if _abc_fps != _fps:
                self.add_fail(
                    f'Frame rate of abc {_abc.namespace} ({_abc_fps:.01f}) '
                    f'does not match scene frame rate ({_fps:.01f})')


class CheckRenderRes(SCCheck):
    """Check resolution matches resolution applied in settings."""

    dcc_filter = '-hou -substance'

    def run(self):
        """Run this check."""
        _ety = pipe.cur_entity()
        if not _ety:
            self.write_log('No current entity found')
            return
        _setting_res = _ety.settings.get('res')
        if not _setting_res:
            self.write_log(f'No res found in "{_ety.label}"')
            return
        _setting_res = tuple(_setting_res)
        self.write_log('Settings res %s', _setting_res)
        _cur_res = dcc.get_res()
        self.write_log('Cur res %s', _cur_res)
        if _setting_res != _cur_res:
            _fix = wrap_fn(dcc.set_res, _setting_res[0], _setting_res[1])
            _msg = (
                f"Current resolution {Res(*_cur_res)} doesn't match "
                f"{_ety.name} settings resolution {Res(*_setting_res)}")
            self.add_fail(_msg, fix=_fix)


class CheckFps(SCCheck):
    """Check fps matches fps applied in settings."""

    dcc_filter = '-substance'

    def run(self):
        """Run this check."""
        _ety = pipe.cur_entity()
        if not _ety:
            self.write_log('No current entity found')
            return
        _cfg_fps = _ety.settings.get('fps')
        if not _cfg_fps:
            self.write_log('No fps found in ' + _ety.name)
            return
        self.write_log('Entity fps %s %s', _cfg_fps, _ety)
        _cur_fps = dcc.get_fps()
        self.write_log('Cur fps %s', _cur_fps)
        if _cfg_fps != _cur_fps:
            _fix = wrap_fn(dcc.set_fps, _cfg_fps)
            _msg = (
                f"Current fps {_cur_fps:.02f} doesn't match {_ety.name} "
                f"fps {_cfg_fps:.02f}")
            self.add_fail(_msg, fix=_fix)


class CheckFrameRange(SCCheck):
    """Check frame range matches shotgrid range."""

    profile_filter = 'shot'
    task_filter = '-fx'

    def run(self):
        """Run this check."""
        if not pipe.SHOTGRID_AVAILABLE:
            self.write_log('Shotgrid not available')
            return
        from pini.pipe import shotgrid
        _ety = pipe.cur_entity()
        _ety_sg = shotgrid.SGC.find_entity(_ety)
        _sg_rng = _ety_sg.data['sg_head_in'], _ety_sg.data['sg_tail_out']
        if None in _sg_rng:
            self.write_log('No range found in %s', _ety)
            return
        _cur_rng = dcc.t_range(int)
        if _sg_rng != _cur_rng:
            _msg = (
                f'Current frame range ({_cur_rng[0]:d}-{_cur_rng[1]:d}) does '
                f'not match shotgrid range for {_ety.name} '
                f'({_sg_rng[0]:d}-{_sg_rng[1]:d}).')
            _fix = wrap_fn(dcc.set_range, *_sg_rng)
            _fail = self.add_fail(_msg, fix=_fix)
            _update = wrap_fn(
                shotgrid.set_entity_range, entity=_ety, range_=_cur_rng)
            if pipe.MASTER == 'disk':
                _fail.add_action(
                    'Update shotgrid', chain_fns(_update, self.run),
                    is_fix=True, index=0)
