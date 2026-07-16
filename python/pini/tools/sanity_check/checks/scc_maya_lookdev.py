"""Maya lookdev checks."""

import logging

from maya import cmds

from pini import dcc
from pini.tools import error
from pini.utils import wrap_fn, plural, chain_fns

from maya_pini import open_maya as pom, m_pipe, tex
from maya_pini.m_pipe import lookdev
from maya_pini.utils import (
    DEFAULT_NODES, to_clean, to_node, to_long, cur_renderer)

from .. import core, utils

_LOGGER = logging.getLogger(__name__)


class CheckForFaceAssignments(core.SCMayaCheck):
    """Checks for shaders assigned to faces rather than geometry."""

    task_filter = 'lookdev'
    action_filter = 'LookdevPublish'

    def run(self):
        """Run this check."""
        _LOGGER.debug('CHECK FOR FACE ASSIGNMENTS')
        for _se in self.update_progress(cmds.ls(type='shadingEngine')):

            # Deterine shader
            self.write_log('Checking %s ', _se)
            _shd = tex.to_shd(_se)
            if not _shd:
                continue
            self.write_log(' - shader %s ', _shd)

            # Find relevant face assignments
            _face_assigns = {}
            for _assign in _shd.to_geo(faces=True):
                self.write_log(' - checking face assignment %s', _assign)
                _long = to_long(_assign)
                if _long.startswith('|JUNK'):
                    continue
                _geo = to_node(_assign)
                _face_assigns[_geo] = _shd

            # Add fails
            for _geo, _shd in _face_assigns.items():
                _assigns = _shd.to_geo(node=_geo, faces=True)
                _assigns_s = ', '.join(f'"{_assign}"' for _assign in _assigns)
                _msg = (
                    f'Shader "{_shd}" has face assigment{plural(_assigns)}: '
                    f'{_assigns_s}')
                _fix = wrap_fn(
                    self._fix_face_assignment, geo=_geo, shader=_shd)
                _fail = core.SCFail(_msg, node=_geo)
                _fail.add_action(
                    'Select shader', wrap_fn(cmds.select, _shd))
                _fail.add_action('Fix', _fix, is_fix=True)
                self.add_fail(_fail)

    def _fix_face_assignment(self, shader, geo):
        """Fix shader face assignment.

        Args:
            shader (Shader): shader with face assignment
            geo (str): geometry to apply
        """
        _LOGGER.info('FIX FACE ASSIGNMENTS %s %s', shader, geo)
        try:
            shader.unassign(node=geo)
        except ValueError as _exc:
            raise error.HandledError(
                f'Failed to unassign "{shader}" from "{geo}".'
                '\n\n'
                'It seems like maya is having trouble with this assignment.'
                'Try deleting history on this node or removing it '
                'if possible') from _exc
        shader.assign_to(geo)


class CheckLookdevShaders(core.SCMayaCheck):
    """Check lookdev shaders."""

    sort = 100
    action_filter = 'LookdevPublish'
    task_filter = 'lookdev'

    def run(
            self, check_ai_shd=None, check_refd_geo=True, flag_refd_shds=False,
            shds_required=True, check_face_assign=False):
        """Run this check.

        Args:
            check_ai_shd (bool): check any attached arnold shader override
            check_refd_geo (bool): check geometry is referenced
            flag_refd_shds (bool): flag referenced shaders
            shds_required (bool): shading assignments are required
            check_face_assign (bool): flag face assignments (now handled in
                separate check so disabled by default)
        """
        self.check_ai_shd = self.read_setting(
            'CheckAiShd', default=True, force=check_ai_shd)
        self.check_refd_geo = check_refd_geo
        self.flag_refd_shds = flag_refd_shds
        self.shds_required = shds_required
        self.check_face_assign = check_face_assign

        self._ignore_names = set()

        if self.flag_refd_shds:
            self._flag_refd_shds()
        self._check_shaders()

    def _check_shaders(self):
        """Apply shaders check."""

        # Find shaders
        _shds = lookdev.read_shader_assignments(
            catch=True, allow_face_assign=True, referenced=False)
        self.write_log('Found %d shaders: %s', len(_shds), _shds)

        # Flag no shading assignments
        if not _shds and self.shds_required:
            self.add_fail(
                'No shader assignments found - this publish saves out shading '
                'assignments so you need to apply shaders to your geometry')

        # Check shaders
        for _shd, _data in _shds.items():
            self._check_shader(_shd, data=_data)

    def _check_shader(self, shd, data):
        """Check shader.

        Args:
            shd (str): shader to check
            data (dict): shader data
        """
        self.write_log('Checking shader %s', shd)

        if shd == 'lambert1':
            return

        _se = data['shadingEngine']
        self.write_log(' - shading engine %s', _se)
        _type = cmds.objectType(shd)
        _select_shd = wrap_fn(cmds.select, shd)

        # Flag namespace
        if shd != to_clean(shd):
            _msg = f'Shader "{shd}" is using a namespace'
            _fix = wrap_fn(cmds.rename, shd, to_clean(shd))
            self.add_fail(_msg, fix=_fix, node=shd)
            return

        # Flag missing MTL suffix
        if not shd.endswith('_MTL'):
            _msg, _fix, _suggestion = utils.fix_node_suffix(
                shd, suffix='_MTL', alts=['_shd', '_mtl', '_SHD', '_Mat'],
                type_='shader', ignore=self._ignore_names)
            self._ignore_names.add(_suggestion)
            self.add_fail(_msg, fix=_fix, node=shd)
            return

        self._check_engine_name(shd=shd, engine=_se)
        self._check_assigned_geo(engine=_se, shader=shd)
        if self.check_refd_geo:
            self._check_for_unreferenced_geo(shd)

        _ren = cur_renderer()
        if _ren == 'arnold':
            self._run_arnold_checks(shd, data=data, type_=_type)

    def _run_arnold_checks(self, shd, data, type_):
        """Run arnold shader checks.

        Args:
            shd (str): shader to check
            data (dict): shader data
            type_ (str): shader node type
        """
        if 'arnold' not in dcc.allowed_renderers():
            return

        # Flag non-arnold shader
        _se = data['shadingEngine']
        if (
                self.check_ai_shd and
                self.settings.get('flag_non_arnold', True) and
                utils.shd_is_arnold(engine=_se, type_=type_)):
            _msg = f'Shader "{shd}" ({type_}) is not arnold shader'
            self.add_fail(_msg, node=shd)
            return

        # Check ai shader suffix
        _ai_shd = data.get('ai_shd')
        _base = shd[:-4]
        if self.check_ai_shd and _ai_shd:
            if not _ai_shd.endswith('_AIS'):
                _msg, _fix, _suggestion = utils.fix_node_suffix(
                    _ai_shd, suffix='_AIS',
                    alts=['_shd', '_mtl', '_SHD'],
                    type_='ai shader', base=_base, ignore=self._ignore_names)
                self._ignore_names.add(_suggestion)
                self.add_fail(_msg, fix=_fix, node=_ai_shd)

    def _flag_refd_shds(self):
        """Flag referenced shaders."""
        for _shd in lookdev.read_shader_assignments(fmt='shd', referenced=True):
            _fix = wrap_fn(utils.import_referenced_shader, _shd)
            self.add_fail(
                f'Shader "{_shd}" is referenced - this must be imported into '
                'the current scene', node=_shd, fix=_fix)

    def _check_assigned_geo(self, engine, shader):
        """Flag geo assigned to intermediate nodes.

        Args:
            engine (str): shading engine
            shader (str): shader
        """
        _shd = tex.to_shd(shader)
        _assigns = _shd.to_assignments()
        self.write_log(' - assigns %s', _assigns)

        for _assign in _assigns:

            if self._check_for_assign_to_dup_geo(_assign, shader=shader):
                continue

            _geo = pom.cast_node(to_node(_assign), maintain_shapes=True)
            self.write_log(' - check geo %s %s', _geo, _geo.object_type())

            # Check for face assigns
            if self.check_face_assign and self._check_for_face_assigns(
                    _assign, shd=_shd, geo=_geo):
                continue

            if _geo.object_type() != 'mesh':
                continue
            self.write_log('   - is mesh')
            if not _geo.plug['intermediateObject'].get_val():
                continue
            _msg = (
                f'Shader "{shader}" is assigned to intermediate object '
                f'"{_geo}" which is not renderable. This assigment has '
                f'no effect and may bloat the publish file.')
            _fix = wrap_fn(
                self._unassign_shader, engine=engine, geo=_geo)
            _fail = core.SCFail(_msg, node=_geo)
            _fail.add_action('Select shader', wrap_fn(cmds.select, shader))
            _fail.add_action('Fix', _fix, is_fix=True)
            self.add_fail(_fail)

    def _check_for_assign_to_dup_geo(self, assign, shader):
        """Check for assignment to duplicate geometry.

        Args:
            assign (str): geometry assignment
            shader (str): shader

        Returns:
            (bool): whether check failed
        """
        if '|' not in assign:
            return False

        # Check dup nodes are not junk
        _, _name = assign.rsplit('|', 1)
        _nodes = cmds.ls(_name)
        _pub_nodes = [
            _node for _node in _nodes
            if not m_pipe.node_is_junk(_node)]
        if len(_pub_nodes) <= 1:
            return False

        # Build fail
        _fail = core.SCFail(
            f'Shader "{shader}" is assigned to duplicate node '
            f'"{assign}".',
            node=assign)
        _fail.add_action('Select shader', wrap_fn(cmds.select, shader))
        self.add_fail(_fail)
        return True

    def _check_for_face_assigns(self, assign, geo, shd):
        """Check for face assignments.

        Args:
            assign (str): assignmemt
            geo (CMesh): geometry
            shd (Shader): shader

        Returns:
            (SCFail|None): fail (if any)
        """
        if '.f[' not in assign:
            return None
        self.write_log('   - face assign')

        _fix = None

        # Check for fixable all faces assigned
        _all_faces = f'{geo}.f[0:{geo.n_faces - 1:d}]'
        self.write_log('   - all faces %s', _all_faces)
        if geo and assign == _all_faces:
            _fix = chain_fns(
                wrap_fn(self._unassign_shader, engine=shd.to_se(), geo=assign),
                wrap_fn(shd.assign_to, geo))

        _fail = core.SCFail(
            f'Shader "{shd}" is face assignment "{assign}".',
            node=assign, fix=_fix)
        _fail.add_action('Select shader', wrap_fn(cmds.select, shd))

        self.add_fail(_fail)
        return _fail

    def _unassign_shader(self, engine, geo):
        """Unassign a shader from the given geometry.

        Args:
            engine (str): shading engine (set)
            geo (str): geometry to detatch
        """
        cmds.sets(geo, edit=True, remove=engine)

    def _check_engine_name(self, shd, engine):
        """Check shading group matches shader.

        Args:
            shd (str): shader to check
            engine (str): shading engine
        """
        if shd == 'lambert1':
            return
        if cmds.referenceQuery(shd, isNodeReferenced=True):
            return

        self.write_log('Checking shd %s', shd)
        assert shd.endswith('_MTL')
        _good_name = shd[:-4] + '_SG'
        if _good_name == engine:
            self.write_log(' - shading engine %s is good', engine)
            return

        _msg = (
            f'Shading engine "{engine}" name does not match shader "{shd}" '
            f'(should be "{_good_name}")')
        _fix = wrap_fn(cmds.rename, engine, _good_name)
        self.add_fail(_msg, fix=_fix, node=shd)

    def _check_for_unreferenced_geo(self, shd):
        """Check for shaders which are not applied to referenced geometry.

        Args:
            shd (str): shader node
        """
        _shd = tex.to_shd(shd)
        _ref = None
        _assigns = _shd.to_assignments()
        _nodes = set()
        for _assign in _assigns:

            # Obtain node (for face assigns)
            _node_s = to_node(_assign)
            if _node_s in _nodes:
                continue
            _nodes.add(_node_s)

            try:
                _node = pom.cast_node(_node_s)
            except ValueError:
                continue
            if not _node.is_referenced():
                continue

            _ref = pom.find_ref(_node.namespace)
            break

        if not _ref:
            _fail = core.SCFail(
                f'Shader "{shd}" is not assigned to referenced geometry, '
                'which can lead to a mismatch between the geometry names in '
                'the model/rig and the assignment - this could cause '
                'shaders to fail to attach.')
            _fail.add_action('Select shader', wrap_fn(cmds.select, shd))
            _fail.add_action('Select nodes', wrap_fn(cmds.select, _assigns))
            self.add_fail(_fail)


class NoObjectsWithDefaultShader(core.SCMayaCheck):
    """Lookdev check to make sure no geos have default shader assigned."""

    task_filter = 'lookdev'
    depends_on = (CheckForFaceAssignments, )

    def run(self):
        """Run this check."""
        _shds = lookdev.read_shader_assignments()

        _flagged_geos = set()
        for _shd, _data in _shds.items():

            _se = _data['shadingEngine']
            _geos = _data['geos']

            # Check for default shader
            if _shd in DEFAULT_NODES:
                for _geo in _geos:
                    _msg = f'Geo "{_geo}" has default shader "{_shd}" applied'
                    self.add_fail(_msg, node=_geo)
                    _flagged_geos.add(_geo)

            # Check for default shading group
            if _se in DEFAULT_NODES:
                for _geo in _geos:
                    if _geo in _flagged_geos:
                        continue
                    _msg = (
                        f'Geo "{_geo}" has shader "{_shd}" applied which uses '
                        f'default shading engine "{_se}" - this will cause '
                        f'issues as default nodes do not appear in references')
                    self.add_fail(_msg, node=_geo)
