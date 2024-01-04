"""Tools for managing shotgrid users."""

import logging

import six

from pini.utils import single, get_user

from . import sg_handler, sg_utils

_LOGGER = logging.getLogger(__name__)


@sg_utils.sg_cache_result
def _read_users_data():
    """Read shotgrid data for all users.

    Returns:
        (dict list): users data
    """
    _filters = [
        ('sg_status_list', 'is_not', 'dis'),
    ]
    _fields = ['name', 'email', 'login']
    return sg_handler.find('HumanUser', _filters, _fields)


@sg_utils.sg_cache_result
def to_user_data(user=None, catch=True, force=False):
    """Obtain shotgrid data for the given user.

    Args:
        user (str|int|None): user name/id to obtain shotgrid data
            for (eg. hvanderbeek) - if empty the current user is used
        catch (bool): no error if user not found
        force (bool): force reread data from shotgrid

    Returns:
        (dict): user data
    """
    _LOGGER.debug('TO USER DATA %s', user)

    # Read username
    _user = _surname = _id = None
    if user is None or isinstance(user, six.string_types):
        _user = (user or get_user()).lower()
        assert _user
        _surname = _user[1:].lower()
    elif isinstance(user, int):
        _id = user
    else:
        raise ValueError(user)
    _LOGGER.debug(' - USER %s', _user)
    _LOGGER.debug(' - SURNAME %s', _surname)
    _LOGGER.debug(' - ID %s', _id)

    _results = _read_users_data()

    # Try id match
    if _id:
        _id_match = single([
            _result for _result in _results
            if _result['id'] == _id], catch=True)
        if _id_match:
            _LOGGER.debug(' - ID MATCH')
            return _id_match

    # Try match login
    if _user:
        _login_match = single([
            _result for _result in _results
            if _result['login'] == _user], catch=True)
        if _login_match:
            _LOGGER.debug(' - LOGIN MATCH')
            return _login_match
    _LOGGER.debug(' - NO LOGIN MATCH')

    # Try match surname
    if _surname:
        _surname_match = single([
            _result for _result in _results
            if _name_to_clean_surname(_result['name']) == _surname], catch=True)
        if _surname_match:
            _LOGGER.debug(' - SURNAME MATCH')
            return _surname_match
    _LOGGER.debug(' - NO SURNAME MATCH')

    # Try match email
    _email_match = single([
        _result for _result in _results
        if _email_to_user(_result['email']) == _user], catch=True)
    if _email_match:
        _LOGGER.debug(' - EMAIL MATCH')
        return _email_match
    _LOGGER.debug(' - NO EMAIL MATCH')

    if catch:
        return {}
    raise ValueError(_user)


def _email_to_user(email):
    """Get a username from an email entry.

    eg. "Henry.vanderBeek@blah.com" -> "hvanderbeek"

    Args:
        email (str): email

    Returns:
        (str): username
    """
    _email = email.lower()
    _name, _ = _email.split('@')
    if '.' not in _name:
        return _name
    assert '.' in _email
    _first, _last = _name.split('.', 1)
    return _first[0]+_last


def _name_to_clean_surname(name):
    """Convert a name to a clean surname.

    eg. "Henry van der Beek" -> "vanderbeek"

    Args:
        name (str): name to read

    Returns:
        (str): surname
    """
    return ''.join(name.lower().split()[1:])
