"""Manages specific dcc-agnostic checks."""

import time
import logging

from pini import dcc, pipe
from pini.utils import wrap_fn, chain_fns

from ..core import SCCheck, SCPipeCheck

_LOGGER = logging.getLogger(__name__)


class CheckRefsLatest(SCPipeCheck):
    """Check all pipeline references are using the latest version."""

    dcc_filter = '-nuke'

    def run(self):
        """Run this check."""
        _refs = self._find_refs()
        if not _refs or not self.check_cache_up_to_date():
            return
        for _ref in self.update_progress(_refs):
            self.write_log('Checking ref %s', _ref)
            if _ref.is_latest():
                continue
            _latest = _ref.output.find_latest()
            _msg = (
                'Reference {} (v{:03d}) is not using latest output '
                '({})'.format(
                    _ref.namespace, _ref.output.ver_n,
                    'v{:03d}'.format(_latest.ver_n) if _latest.ver_n
                    else 'versionless'))
            _fix = wrap_fn(self.update_ref, ref_=_ref, path=_latest)
            self.add_fail(_msg, fix=_fix, node=_ref.node)

    def _find_refs(self):
        """Find references to check.

        Returns:
            (CPipeRef list): pipelined references
        """
        return dcc.find_pipe_refs()

    def update_ref(self, ref_, path):
        """Update the given reference.

        Args:
            ref_ (CPipeRef): reference to update
            path (CPOutput): path to apply to reference
        """
        ref_.update(path)


class CheckAbcFpsMatchesScene(SCPipeCheck):
    """Check frame rate of referenced abcs matches current scene FPS."""

    def run(self):
        """Run this check."""
        self.write_log('Reading abcs')
        _abcs = dcc.find_pipe_refs(extn='abc')
        self.write_log('Found %d abcs', len(_abcs))
        if not _abcs:
            return
        if self.check_cache_up_to_date():
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
                    'Frame rate of abc {} ({:.01f}) does not match scene '
                    'frame rate ({:.01f})'.format(
                        _abc.namespace, _abc_fps, _fps))


class CheckRenderRes(SCCheck):
    """Check resolution matches resolution applied in settings."""

    dcc_filter = '-hou'

    def run(self):
        """Run this check."""
        _ety = pipe.cur_entity()
        if not _ety:
            self.write_log('No current entity found')
            return
        _cfg_res = _ety.settings.get('res')
        if not _cfg_res:
            self.write_log('No res found in '+_ety.name)
            return
        _cfg_res = tuple(_cfg_res)
        _cur_res = dcc.get_res()
        if _cfg_res != _cur_res:
            _fix = wrap_fn(dcc.set_res, _cfg_res[0], _cfg_res[1])
            _msg = (
                "Current resolution {:d}x{:d} doesn't match {} "
                "resolution {:d}x{:d}".format(
                    _cur_res[0], _cur_res[1], _ety.name, _cfg_res[0],
                    _cfg_res[1]))
            self.add_fail(_msg, fix=_fix)


class CheckFps(SCCheck):
    """Check fps matches fps applied in settings."""

    def run(self):
        """Run this check."""
        _ety = pipe.cur_entity()
        if not _ety:
            self.write_log('No current entity found')
            return
        _cfg_fps = _ety.settings.get('fps')
        if not _cfg_fps:
            self.write_log('No fps found in '+_ety.name)
            return
        _cur_fps = dcc.get_fps()
        if _cfg_fps != _cur_fps:
            _fix = wrap_fn(dcc.set_fps, _cfg_fps)
            _msg = (
                "Current fps {:.02f} doesn't match {} "
                "fps {:.02f}".format(_cur_fps, _ety.name, _cfg_fps))
            self.add_fail(_msg, fix=_fix)


class CheckFrameRange(SCCheck):
    """Check frame range matches shotgrid range."""

    profile_filter = 'shot'

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
                'Current frame range ({:d}-{:d}) does not match shotgrid '
                'range for {} ({:d}-{:d}).'.format(
                    _cur_rng[0], _cur_rng[1], _ety.name, _sg_rng[0],
                    _sg_rng[1]))
            _fix = wrap_fn(dcc.set_range, *_sg_rng)
            _fail = self.add_fail(_msg, fix=_fix)
            _update = wrap_fn(
                shotgrid.set_entity_range, entity=_ety, range_=_cur_rng)
            if pipe.MASTER == 'disk':
                _fail.add_action(
                    'Update shotgrid', chain_fns(_update, self.run),
                    is_fix=True, index=0)


class SlowCheckTest(SCCheck):
    """Test check which runs over a few seconds."""

    dev_only = True

    def run(self):
        """Run this check."""

        _count = 30
        for _idx in self.update_progress(range(_count)):
            self.write_log('Updating %d/%d', _idx+1, _count)
            time.sleep(0.1)

        for _key in ['BLAH', 'BLUE', 'BLEE']:
            if dcc.get_scene_data(_key):
                _fix = wrap_fn(self.fix_scene_data, _key)
                self.add_fail('Bad scene data '+_key, fix=_fix)

    def fix_scene_data(self, key):
        """Fix scene data issue.

        Args:
            key (str): data items to fix
        """
        dcc.set_scene_data(key, False)
        time.sleep(0.3)
