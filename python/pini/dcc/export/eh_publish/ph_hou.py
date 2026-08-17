"""Tools for managing the basic houdini publisher."""

import logging

import hou

from pini import icons, pipe, qt

from . import ph_basic

_LOGGER = logging.getLogger(__name__.rsplit('.', 1)[-1])


class CHouBasicPublish(ph_basic.CBasicPublish):
    """Basic houdini publisher."""

    NAME = 'Hou Basic Publish'
    ICON = icons.find('Top hat')

    def build_metadata(self, **kwargs):
        """Obtain metadata for this publish.

        Returns:
            (dict): metadata
        """
        return super().build_metadata(has_anim=True, **kwargs)

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        _items = []
        for _pub in self.find_publishable_nodes():
            _item = qt.CListWidgetItem(_pub.name())
            _item.set_data(_pub)
            _items.append(_item)

        self.ui.add_list_widget(
            'Nodes', items=_items, select=_items)

    def export(self, nodes, **kwargs):  # pylint: disable=unused-argument
        """Run this export.

        Args:
            nodes (Node list): rop nodes to be executed

        Returns:
            (CPOutput list): outputs
        """
        _LOGGER.info('EXPORT %s', nodes)
        _outs = []
        for _node in nodes:
            _out = self._export_node(_node)
            _outs.append(_out)
        return _outs

    def _export_node(self, node):
        """Export the given node.

        Args:
            node (Node): rop node to export

        Returns:
            (CPOutput): output
        """
        _type = node.type().name()
        if _type == 'kinefx::rop_fbxcharacteroutput':
            _out_extn = 'fbx'
            _out_type = 'char'
            _out_parm = node.parm('outputfilepath')
            _btn = node.parm('execute')
        elif _type == 'kinefx::rop_fbxanimoutput':
            _out_extn = 'fbx'
            _out_type = 'anim'
            _out_parm = node.parm('outputfilepath')
            _btn = node.parm('execute')
        elif _type == 'rop_fbx':
            _out_extn = 'fbx'
            _out_type = 'geo'
            _out_parm = node.parm('sopoutput')
            _btn = node.parm('execute')
        elif _type == 'rop_alembic':
            _out_extn = 'abc'
            _out_type = 'geo'
            _out_parm = node.parm('filename')
            _btn = node.parm('execute')
        elif _type == 'PiniAbc':
            node.parm('UpdatePath').pressButton()
            _out_parm = node.parm('AbcPath')
            _btn = node.parm('ExportAbc')
            _out_type = None
            _out_extn = 'abc'
        else:
            raise NotImplementedError(_type)
        if not (_out_type and _out_extn):
            raise NotImplementedError(node)

        # Find output
        _out = None
        _path = _out_parm.eval()
        if _path:
            _out = pipe.to_output(_path, catch=True)

        # Handle invalid output
        if not _out:
            _expr = '\n'.join([
                "from pini import pipe",
                "_work = pipe.cur_work()",
                "_out = _work.to_output(",
                "    'publish',",
                "    output_name=None,",
                f"    output_type='{_out_type}',",
                f"    extn='{_out_extn}')",
                "return _out.path",
            ])
            if _out_parm.eval():
                qt.ok_cancel(
                    f'Update expression?\n{_out_parm.path()}\n\n{_expr}')
            _out_parm.setExpression(_expr, language=hou.exprLanguage.Python)
            _path = _out_parm.eval()
            _out = pipe.to_output(_path)

        # Execute export
        _out.delete(wording='replace')
        _btn.pressButton()

        return _out

    def _callback__Nodes(self):
        _LOGGER.info('CALLBACK Nodes')

    def find_publishable_nodes(self):
        """Find publishable ROPs in the current scene.

        Returns:
            (Node list): exportable nodes
        """
        _nodes = []
        for _name in [
                'kinefx::rop_fbxcharacteroutput',
                'kinefx::rop_fbxanimoutput',
                'PiniAbc',
                'rop_fbx',
                'rop_alembic',
        ]:
            _type = hou.sopNodeTypeCategory().nodeType(_name)
            if not _type:
                continue
            _nodes += _type.instances()
        # _nodes = [_node for _node in _nodes if not _node.isBypassed()]
        return _nodes

        # dcc.add_export_handler(_exp)
        # _helper = helper.launch()
        # _helper.ui.MainPane.select_tab('Export')
