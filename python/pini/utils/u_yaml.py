"""Tools for managing yaml within pini."""

import logging

import yaml

_LOGGER = logging.getLogger(__name__)


def register_custom_yaml_handler(type_):
    """Register a custom yaml handler.

    This allows how a type is stored in a yaml files to be overriden, allowing
    for more efficient yaml.

    The type must have a yaml_tag attribute declared, and to_yaml/from_yaml
    class methods defined too.

    Args:
        type_ (class): class to register
    """
    _LOGGER.debug('REGISTER CUSTOM HANDLER %s %s', type_, type_.yaml_tag)

    # Clean existing
    for _key, _val in list(yaml.Dumper.yaml_multi_representers.items()):
        if _key.__name__ == type_.__name__:
            _LOGGER.debug(' - REMOVE EXISTING REPRESENTATION %s %s', _key, _val)
            yaml.Dumper.yaml_multi_representers.pop(_key)

    yaml.Dumper.add_multi_representer(type_, type_.to_yaml)
    yaml.UnsafeLoader.add_constructor(type_.yaml_tag, type_.from_yaml)
