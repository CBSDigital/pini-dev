"""Maya asset checks."""

import logging

from maya import cmds, mel

from pini import dcc
from pini.utils import wrap_fn

from maya_pini import open_maya as pom, m_pipe

from .. import core
from . import scc_maya_asset

_LOGGER = logging.getLogger(__name__)


class CheckForNgons(core.SCMayaCheck):
    """Check for polygons with more than four sides."""

    task_filter = 'model'
    depends_on = (scc_maya_asset.CheckGeoNaming, )
    sort = 100

    def run(self):
        """Run this check."""
        self._check_count = 0
        for _geo in self.update_progress(m_pipe.read_cache_set()):
            self._check_geo(_geo)

    def _check_geo(self, geo):
        """Check the given geo for ngons.

        Args:
            geo (CMesh): mesh to check
        """
        assert isinstance(geo, pom.CMesh)
        self._check_count += 1

        # Check for mesh marked in scene data as check passed
        _uid = geo.n_vtxs, geo.n_edges, geo.n_faces
        _key = f'SanityCheck.CheckForNgons.{geo}.Passed'
        _data = dcc.get_scene_data(_key)
        if _data == _uid:
            if self._check_count < 100:
                self.write_log('geo marked as passed check %s', geo)
            return

        # Apply ngons check (slow)
        cmds.select(geo)
        mel.eval(
            'polyCleanupArgList 4 { '
            '    "0","2","1","0","1","0","0","0","0","1e-05","0",'
            '    "1e-05","0","1e-05","0","-1","0","0" }')
        if cmds.ls(selection=True):
            _msg = f'Mesh "{geo}" contains ngons'
            self.add_fail(
                _msg, node=geo, fix=wrap_fn(self.fix_ngons, geo))
        else:
            dcc.set_scene_data(_key, _uid)

    def fix_ngons(self, geo):
        """Fix ngons in the given mesh.

        Args:
            geo (str): mesh to fix
        """
        cmds.select(geo)
        mel.eval(
            'polyCleanupArgList 4 {'
            '    "0","1","1","0","1","0","0","0","0","1e-05","0",'
            '    "1e-05","0","1e-05","0","-1","0","0" }')
        cmds.select(geo)


class CheckModelGeo(core.SCMayaCheck):
    """Check naming of cache set geometry."""

    task_filter = 'model'
    _ignore_names = None
    depends_on = (scc_maya_asset.CheckCacheSet, )

    def run(self):
        """Run this check."""
        _geos = m_pipe.read_cache_set()
        self.write_log('Found %d geos: %s', len(_geos), _geos)
        for _geo in _geos:

            # Check for incoming connections to transform attrs
            for _plug in _geo.tfm_plugs:
                if _plug.find_incoming():
                    self.add_fail(
                        f'Plug has incoming connections: "{_plug}"',
                        fix=_plug.break_conns)

            # Check redshift displacement disabled
            if _geo.shp.has_attr('rsEnableDisplacement'):
                self.check_attr(_geo.shp.plug['rsEnableDisplacement'], False)
