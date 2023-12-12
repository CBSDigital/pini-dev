"""Plugin which provides a node which performs modulo function (%)."""

import sys

from maya import OpenMaya, OpenMayaMPx

kPluginNodeName = 'modulo'
kPluginNodeId = OpenMaya.MTypeId(0x0000A001)


class _ModuloNode(OpenMayaMPx.MPxNode):
    """Node which performs modulo function."""

    input_ = OpenMaya.MObject()
    modulo = OpenMaya.MObject()
    output = OpenMaya.MObject()

    def __init__(self):
        """Constructor."""
        OpenMayaMPx.MPxNode.__init__(self)

    def compute(self, plug, block):
        """Calcuate modulo.

        Args:
            plug (MPlug): plug representing the attribute that needs to
                be recomputed
            block (MDataBlock): data block containing storage for the
                node's attributes

        Returns:
            (str): parameter
        """
        if plug == _ModuloNode.output:
            _input = block.inputValue(_ModuloNode.input_).asFloat()
            _modulo = block.inputValue(_ModuloNode.modulo).asFloat()
            _result = _input % _modulo
            block.outputValue(_ModuloNode.output).setFloat(_result)
            block.setClean(plug)
        return OpenMaya.kUnknownParameter


def nodeCreator():
    """Callback for node create.

    Returns:
        (ModuloNode): modulo node
    """
    return OpenMayaMPx.asMPxPtr(_ModuloNode())


def nodeInitializer():
    """Initialise this node."""
    _num_attr = OpenMaya.MFnNumericAttribute()

    # Inputs
    _ModuloNode.input_ = _num_attr.create(
        'input', 'i', OpenMaya.MFnNumericData.kFloat, 0)
    _num_attr.writable = True
    _num_attr.readable = False
    _num_attr.storable = True
    _num_attr.hidden = False
    _ModuloNode.addAttribute(_ModuloNode.input_)

    _ModuloNode.modulo = _num_attr.create(
        'modulo', 'm', OpenMaya.MFnNumericData.kFloat, 1.0)
    _num_attr.writable = True
    _num_attr.readable = False
    _num_attr.storable = True
    _num_attr.hidden = False
    _num_attr.setMin(0.01)
    _ModuloNode.addAttribute(_ModuloNode.modulo)

    # Outputs
    _ModuloNode.output = _num_attr.create(
        'output', 'o', OpenMaya.MFnNumericData.kFloat, 0)
    _num_attr.writable = False
    _num_attr.readable = True
    _num_attr.storable = False
    _num_attr.hidden = False
    _ModuloNode.addAttribute(_ModuloNode.output)

    _ModuloNode.attributeAffects(
        _ModuloNode.input_, _ModuloNode.output)
    _ModuloNode.attributeAffects(
        _ModuloNode.modulo, _ModuloNode.output)


def initializePlugin(plugin):
    """Initialise this plugin.

    Args:
        plugin (MObject): plugin to initialise
    """
    _plugin = OpenMayaMPx.MFnPlugin(plugin)
    try:
        _plugin.registerNode(
            kPluginNodeName, kPluginNodeId, nodeCreator, nodeInitializer)
    except Exception as _exc:
        sys.stderr.write('Failed to register node: {}\n'.format(
            kPluginNodeName))
        raise _exc


def uninitializePlugin(plugin):
    """Uninitialise this plugin.

    Args:
        plugin (MObject): plugin to uninitialise
    """
    _plugin = OpenMayaMPx.MFnPlugin(plugin)
    try:
        _plugin.deregisterNode(kPluginNodeId)
    except Exception as _exc:
        sys.stderr.write('Failed to deregister node: {}\n'.format(
            kPluginNodeName))
        raise _exc
