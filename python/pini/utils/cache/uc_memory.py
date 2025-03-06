"""General utilities relating to caching."""

import functools
import logging
import time

from inspect import getfullargspec as _get_args  # py3

_LOGGER = logging.getLogger(__name__)
_RESULTS = {}


class _Result:
    """Represents the result of a cacheable function."""

    def __init__(self, value):
        """Constructor.

        Args:
            value (any): function result
        """
        self.value = value
        self.mtime = time.time()

    @property
    def age(self):
        """Obtain age of this result.

        Returns:
            (float): age in seconds
        """
        return time.time() - self.mtime


def obt_results_cache(namespace='default'):
    """Obtain cached results for the given namespace.

    Args:
        namespace (str): cache namespace

    Returns:
        (dict): cached results
    """
    if namespace not in _RESULTS:
        _RESULTS[namespace] = {}
    return _RESULTS[namespace]


def flush_caches(namespace=None):
    """Flush memory cached results.

    Args:
        namespace (str): only flush the given namespace
    """
    global _RESULTS
    if namespace:
        if namespace in _RESULTS:
            del _RESULTS[namespace]
    else:
        _RESULTS = {}


def get_result_cacher(use_args=None, namespace='default', max_age=None):
    """Build a result caching decorator.

    Args:
        use_args (list): limit the list of args to use
        namespace (str): cache namespace
        max_age (float): force recalculate after this many seconds

    Returns:
        (fn): caching decorator
    """

    def _build_result_cacher(func):

        @functools.wraps(func)
        def _func(*args, **kwargs):

            # Determine args
            _args_key = _get_args_key(
                func=func, args=args, kwargs=kwargs, use_args=use_args)
            _force = kwargs.get('force')
            _LOGGER.debug('[cache_result] - ARGS KEY (%s): %s',
                          func.__name__, _args_key)
            _results = obt_results_cache(namespace)

            # Determine whether result needs to be calculated
            if _force:
                _calculate = True
            elif _args_key not in _results:
                _calculate = True
            elif max_age and _results[_args_key].age > max_age:
                _calculate = True
            else:
                _calculate = False

            # Retrieve/generate retult
            if _calculate:
                _result = func(*args, **kwargs)
                _LOGGER.debug('[cache_result] - CALCULATED RESULT %s %s',
                              func.__name__, _result)
                _results[_args_key] = _Result(_result)
            else:
                _result = _results[_args_key].value
                _LOGGER.debug('[cache_result] - USING CACHED RESULT %s %s',
                              func.__name__, _result)
            return _result

        return _func

    return _build_result_cacher


def cache_result(func):
    """Decorator which caches a result for each unique set of args/kwargs.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated func
    """
    _result_cacher = get_result_cacher()
    return _result_cacher(func)


def cache_on_obj(func):
    """Cache the result of a method on the object.

    All other args apart from self are ignored.

    Args:
        func (fn): method to decorate

    Returns:
        (fn): decorated func
    """
    _result_cacher = get_result_cacher(use_args=('self', ))
    return _result_cacher(func)


def _get_args_key(func, args, kwargs, use_args=None):
    """Get a hashable unique identifier for the given func and set of args.

    Args:
        func (fn): function being executed
        args (list): args passed
        kwargs (dict): kwargs passed
        use_args (list): limit the args which are used for the key

    Returns:
        (tuple): args key
    """
    _LOGGER.debug('[cache_result] GET ARGS KEY %s %s %s',
                  func.__name__, args, kwargs)

    _arg_spec = _get_args(func)
    _defaults = _arg_spec.defaults or []
    _args = list(_arg_spec.args)

    _key = [func]
    for _idx, _arg_name in enumerate(_args):

        _arg_idx = _idx - len(_args)
        if _arg_name in ['force', 'verbose']:
            continue
        if use_args and _arg_name not in use_args:
            continue

        if _idx < len(args):
            _val = args[_idx]
        elif _arg_name in kwargs:
            _val = kwargs[_arg_name]
        elif abs(_arg_idx) > len(_defaults):
            _LOGGER.info('ARGS %s %s', _arg_spec.args, _args)
            _LOGGER.info('DEFAULTS %s %s', _arg_spec.defaults, _defaults)
            raise TypeError(
                f'It looks like some of the required args are '
                f'missing {func.__name__}')
        else:
            _val = _defaults[_arg_idx]

        # For self arg use object id
        if _idx == 0 and _arg_name == 'self' and isinstance(_val, object):
            _val = id(_val), _val

        _key.append((_arg_name, _val))

    return tuple(_key)
