"""Maya render checks."""

import logging
import re

from maya import cmds, mel
from maya.app.renderSetup.views import renderSetup

from pini import dcc
from pini.utils import single, wrap_fn, is_camel, to_camel

from maya_pini import ref, open_maya as pom
from maya_pini.utils import (
    to_render_extn, set_render_extn)

from ..core import SCFail, SCMayaCheck

_LOGGER = logging.getLogger(__name__)


class CheckLookdevAssign(SCMayaCheck):
    """Check lookdev assignments have been applied correctly.

    If a node is missing from the target reference or if the target node
    doesn't have the correct lookdev shader applied then this is flagged.
    """

    def run(self):
        """Run this check."""
        for _lookdev in dcc.find_pipe_refs(task='lookdev'):
            if (
                    not _lookdev.ref or
                    not _lookdev.output.metadata.get('shd_yml')):
                continue
            self.write_log('Checking %s', _lookdev)
            _lookdev_ref = _lookdev.ref
            _geo_ns = _lookdev_ref.namespace[:-4]
            _geo_ref = ref.find_ref(_geo_ns)
            if not _geo_ref:
                self.write_log(' - No geo ref found %s', _geo_ns)
                continue
            _shd_data = _lookdev.shd_data.get('shds', {})
            for _, _data in _shd_data.items():
                _geos = _data['geos']
                _sg = _data['shadingEngine']
                self._check_shd_assignments(
                    lookdev_ref=_lookdev_ref, geo_ref=_geo_ref, geos=_geos,
                    sg=_sg)

    def _check_shd_assignments(self, lookdev_ref, geo_ref, sg, geos):
        """Check assignments for the given lookdev.

        Args:
            lookdev_ref (CMayaShadersRef): lookdev ref
            geo_ref (CMayaRef): geometery ref
            sg (str): shading group to check
            geos (str list): geos using this shader
        """

        # Read shading group
        if sg == 'initialShadingGroup':
            return

        # Check shading group
        _node_fail = _check_lookdev_node(ref_=lookdev_ref, node=sg)
        if _node_fail:
            self.add_fail(_node_fail)
            return
        _sg = pom.CNode(lookdev_ref.to_node(sg))
        self.write_log(' - Check shading group %s', _sg)

        # Get list of assigned shapes
        _sg_geos = set()
        _sg_items = pom.CMDS.sets(_sg, query=True) or []
        for _sg_shp in _sg_items:
            _sg_geo = _sg_shp.to_parent()
            _sg_geos.add(_sg_geo)
        _sg_geos = sorted(_sg_geos)

        # Check geos have shader assigned
        for _geo in geos:

            # Check node exists
            _geo = geo_ref.to_node(_geo)
            try:
                _geo = pom.CNode(_geo)
            except RuntimeError:
                _msg = 'Failed to apply lookdev {} to missing node {}'.format(
                    lookdev_ref.namespace, _geo)
                _node = geo_ref.find_top_node(catch=True)
                self.add_fail(_msg, node=_node)
                continue

            # Check assignment
            if _geo not in _sg_geos:
                _geo_s = _geo.to_shp(catch=True)
                if not _geo_s:
                    _msg = (
                        'Geo "{}" is missing a shape node - failed to apply '
                        'to lookdev "{}" (shading group "{}")'.format(
                            _geo, lookdev_ref.namespace, _sg))
                    self.add_fail(_msg, node=_geo)
                else:
                    _msg = (
                        'Lookdev "{}" not applied to "{}" (shading group '
                        '"{}")'.format(
                            lookdev_ref.namespace, _geo, _sg))
                    _fix = wrap_fn(cmds.sets, _geo_s, forceElement=_sg)
                    self.add_fail(_msg, node=_geo, fix=_fix)


def _check_lookdev_node(ref_, node):
    """Check a lookdev reference has a node referred to in its yaml.

    Args:
        ref_ (FileRef): lookdev ref
        node (str): required node

    Returns:
        (SCFail|None): missing node fail (if any)
    """
    _node = ref_.to_node(node)
    if cmds.objExists(_node):
        return None
    _msg = (
        'Node {} is missing from the lookdev reference {} which means '
        'that there is something wrong with the publish'.format(
            _node, ref_.namespace))
    _fail = SCFail(_msg, node=ref_.ref_node)
    return _fail


class CheckAOVs(SCMayaCheck):
    """Check current scene AOVs match the job template.

    If no job AOV template has been published, the check does nothing.
    """

    task_filter = 'lookdev layout lighting'
    label = 'Check AOVs'

    def run(self):
        """Run this check."""
        _ren = cmds.getAttr("defaultRenderGlobals.currentRenderer")
        if _ren not in ['redshift']:
            self.write_log('Not implemented for renderer %s', _ren)
            return
        _aovs = _find_aovs()
        self._check_for_job_default_aovs(_aovs)
        if _ren == 'arnold':
            self._check_for_broken_cryto_aovs(_aovs)

    def _check_for_job_default_aovs(self, aovs):
        """Check scene AOVs match job defaults (if available).

        Args:
            aovs (CNode list): AOVs to check
        """
        self.write_log('Check settings for AOVs')

        _req_aovs = self.settings.get('aovs', [])
        self.write_log('Required AOVs %s', _req_aovs)

        _cur_aovs = [_aov.plug['aovType'].get_val() for _aov in aovs]
        self.write_log('Cur AOVs %s', _cur_aovs)

        for _aov in _req_aovs:
            if _aov in _cur_aovs:
                continue
            _msg = f'AOV "{_aov}" is missing from the scene'
            _fix = wrap_fn(_create_aov, _aov)
            self.add_fail(_msg, fix=_fix)

    def _check_for_broken_cryto_aovs(self, aovs):
        """Check for broken cryto AOVs.

        Args:
            aovs (CNode list): AOVs to check
        """
        self.write_log('Check for broken cryto AOVs')

        # Find crypto aovs to check
        _aovs = [_aov for _aov in aovs
                 if _aov.plug['aovType'].get_val().startswith('crypto_')]
        self.write_log(' - AOVs %s', _aovs)
        if not _aovs:
            self.write_log(' - Nothing to check')
            return

        # Find shader
        _shds = pom.find_nodes(type_='cryptomatte')
        self.write_log(
            ' - cryptomatte shaders: %s', [str(_shd) for _shd in _shds])
        if len(_shds) > 1:
            _msg = 'Too many crypto shaders (see log for details)'
            self.add_fail(_msg)
            return
        if not _shds:
            _msg = 'Missing cryptomatte shader'
            _fix = wrap_fn(pom.CMDS.shadingNode, 'cryptomatte', asShader=True)
            self.add_fail(_msg, fix=_fix)
            return
        _shd = single(_shds)
        _shd_col = _shd.plug['outColor']
        self.write_log(' - cryptomatte shader: %s %s', _shd, _shd_col)

        # Check connections
        for _aov in _aovs:
            self.write_log(' - checking aov: %s', _aov)
            _shd_plug = _aov.plug['defaultValue']
            if not _shd_plug.find_incoming():
                _msg = 'AOV "{}" not connected to shader "{}"'.format(
                    _aov.plug['name'].get_val(), _shd)
                _fix = wrap_fn(_shd_col.connect, _shd_plug)
                self.add_fail(_msg, fix=_fix, node=_aov)


def _find_aovs():
    """Find aovs in the current scene.

    Returns:
        (CNode list): aovs
    """
    _ren = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    if _ren == 'arnold':
        _type = 'aiAOV'
    elif _ren == 'redshift':
        _type = 'RedshiftAOV'
    else:
        raise NotImplementedError(_ren)
    return [
        _aov for _aov in pom.CMDS.ls(type=_type)
        if not _aov.is_referenced()]


def _create_aov(type_, name=None):
    """Create the given AOV.

    Args:
        type_ (str): AOV type
        name (str): AOV name (if required)
    """
    _ren = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    _LOGGER.info('CREATE AOV (%s) %s %s', _ren, type_, name)
    if _ren == 'arnold':
        from mtoa import aovs

        cmds.lockNode('initialParticleSE', lock=False, lockUnpublished=False)

        _LOGGER.info('ADD AOV %s type=%s', name, type_)
        _api = aovs.AOVInterface()
        _match = (
            "setAttr: The attribute 'initialParticleSE.aiCustomAOVs[0]"
            ".aovName' is locked or connected and cannot be modified.")
        try:
            _api.addAOV(name, aovType=type_)
        except RuntimeError as _exc:
            _exc = str(_exc).strip()
            if _exc != _match:
                _LOGGER.info(' - ERROR "%s"', _exc)
                _LOGGER.info(' - MATCH "%s"', _match)
                raise _exc
    elif _ren == 'redshift':
        cmds.rsCreateAov(type=type_)
        mel.eval('redshiftUpdateActiveAovList')
    else:
        raise NotImplementedError(_ren)


class CheckCustomAovConnections(SCMayaCheck):
    """Check custom aov assignments.

    Checks the names of the custom aov connections to each shading group
    matches the name of the aov in the lookdev scene.
    """

    label = 'Check custom AOV connections'

    def run(self):
        """Run this check."""
        for _lookdev in dcc.find_pipe_refs(task='lookdev'):
            if (
                    not _lookdev.ref or
                    not _lookdev.output.metadata.get('shd_yml')):
                continue
            self.write_log('Checking %s', _lookdev)
            _ref = _lookdev.ref
            _custom_aovs = _lookdev.shd_data.get('custom_aovs', [])
            for _src, _aov in _custom_aovs:

                # Check node
                _node_fail = _check_lookdev_node(ref_=_ref, node=_src)
                if _node_fail:
                    self.add_fail(_node_fail)
                    continue

                _src = pom.CPlug(_ref.to_plug(_src))
                self._check_custom_aov(src=_src, aov=_aov)

    def _check_custom_aov(self, src, aov):
        """Check the given custom aov setting from the lookdev scene.

        Args:
            src (str): plug being applied to custom aov list
            aov (str): name of aov which it was applied to
        """
        _LOGGER.debug('CHECK CUSTOM AOV %s %s', src, aov)
        self.write_log('   - aov %s %s', src, aov)

        # Read current custom aov connection
        _cur_trg = single(
            src.find_outgoing(type_='shadingEngine'), catch=True)
        if not _cur_trg:
            return

        # Read name of current aov
        _LOGGER.debug(' - CUR TRG %s %s', _cur_trg, type(_cur_trg))
        _tokens = re.split(r'[\[\]]', str(_cur_trg))
        _LOGGER.debug(' - TOKENS %s', _tokens)
        _, _idx, _ = _tokens
        _idx = int(_idx)
        _sg = pom.to_node(_cur_trg)
        _name_attr = _sg.to_attr(
            'aiCustomAOVs[{:d}].aovName'.format(_idx))
        _cur_aov = cmds.getAttr(_name_attr)
        if _cur_aov == aov:
            self.write_log(' - connected correctly')
            return

        # Find correct connection index
        _idxs = []
        for _idx in cmds.getAttr(
                _sg.to_plug('aiCustomAOVs'), multiIndices=True):
            _name_attr = _sg.to_attr(
                'aiCustomAOVs[{:d}].aovName'.format(_idx))
            _name = cmds.getAttr(_name_attr)
            if _name == aov:
                _idxs.append(_idx)
        _idx = single(_idxs, catch=True)
        if not _idx:
            _msg = (
                'Custom aov {aov} is wrongly connected to {cur_aov} in '
                '{sg} - no {aov} aov was found to connect to'.format(
                    aov=aov, cur_aov=_cur_aov, sg=_sg))
            self.add_fail(_msg, node=_sg)
            return

        # Build fix with new target
        _new_trg = _sg.to_attr('aiCustomAOVs[{:d}].aovInput'.format(_idx))
        _cur_conn = src, _cur_trg
        _new_conn = src, _new_trg
        _msg = ('Custom aov {} is wrongly connected to {} in {}'.format(
            aov, _cur_aov, _sg))
        _fix = wrap_fn(
            _fix_bad_aov_conn, disconnect=_cur_conn, connect=_new_conn)
        self.add_fail(_msg, node=_sg, fix=_fix)


def _fix_bad_aov_conn(disconnect, connect):
    """Fix bad a bad aov connection.

    Args:
        disconnect (tuple): connection to break
        connect (tuple): connection to build
    """
    cmds.disconnectAttr(*disconnect)
    cmds.connectAttr(*connect)


class CheckRenderGlobals(SCMayaCheck):
    """Check render format is exr."""

    task_filter = 'lighting model lookdev'

    def run(self):
        """Run this check."""

        # Check render format
        _fmt = to_render_extn()
        self.write_log('check format %s', _fmt)
        if _fmt != 'exr':
            _fix = wrap_fn(set_render_extn, 'exr')
            _msg = f'Image format is not "exr" (set to "{_fmt}")'
            self.add_fail(_msg, fix=_fix)

        _to_check = []

        _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
        self.write_log('renderer %s', _ren)
        if _ren == 'arnold' and 'arnold' in dcc.allowed_renderers():
            if not cmds.objExists('defaultArnoldDriver'):
                _msg = (
                    'Missing defaultArnoldDriver - try opening render globals')
                self.add_fail(_msg)
            else:
                _to_check += [
                    ('defaultArnoldDriver.mergeAOVs', True),
                    ('defaultArnoldDriver.exrTiled', False),
                    ('defaultArnoldDriver.halfPrecision', True)]

        elif _ren == 'redshift':
            _to_check += [
                # ('redshiftOptions.autocrop', True),
                ('redshiftOptions.exrForceMultilayer', True),
                ('redshiftOptions.exrMultipart', True)]

        for _attr, _val in _to_check:
            self._check_setting(_attr, _val)

    def _check_setting(self, attr, val):
        """Check a setting has the given value.

        Args:
            attr (str): attribute to check
            val (any): expected value
        """
        _plug = pom.CPlug(attr)
        _cur_val = _plug.get_val()
        _passed = _cur_val == val
        self.write_log(
            ' - check setting %s == %s passed=%d', attr, val, _passed)
        if _passed:
            return
        _msg = f'Attribute "{_plug}" is not set to "{val}"'
        _fix = wrap_fn(_plug.set_val, val)
        self.add_fail(_msg, fix=_fix, node=_plug.node)


class CheckRenderLayers(SCMayaCheck):
    """Check current scene render layers."""

    task_filter = 'lighting model lookdev'

    def run(self):
        """Run this check."""

        # Obtain list of prefixes
        _prefixes = {'bty', 'mte', 'sdw', 'ref', 'utl'}
        _prefixes |= set(self.settings.get('add_prefixes', []))
        _prefixes = sorted(_prefixes)
        self.write_log(' - prefixes %s', _prefixes)

        for _lyr in pom.find_render_layers():
            self.write_log('Checking %s pass=%s', _lyr, _lyr.pass_name)

            if _lyr.pass_name == 'masterLayer':
                continue

            if '_' in _lyr.pass_name:
                _prefix, _suffix = _lyr.pass_name.split('_', 1)
            else:
                _prefix, _suffix = _lyr.pass_name, None

            # Check prefix
            if _prefix not in _prefixes:
                _msg = (
                    'Render layer "{}" has prefix "{}" which is not in the '
                    'list of approved prefixes: {}'.format(
                        _lyr.pass_name, _prefix, str(_prefixes).strip('[]')))
                _fail = SCFail(_msg)
                _fail.add_action('Open layers', renderSetup.createUI)
                self.add_fail(_fail)
                continue

            # Check suffix
            if _suffix and not is_camel(_suffix):
                _new_suffix = to_camel(_suffix)
                _new_name = '{}_{}'.format(_prefix, _new_suffix)
                _msg = (
                    'Render layer "{}" has suffix "{}" which is not camel '
                    'case (should be "{}")'.format(
                        _lyr.pass_name, _suffix, _new_name))
                _fix = wrap_fn(_lyr.set_pass_name, _new_name)
                self.add_fail(_msg, fix=_fix)
                continue
