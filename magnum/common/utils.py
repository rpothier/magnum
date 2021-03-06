# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
# Copyright (c) 2012 NTT DOCOMO, INC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Utilities and helper functions."""

import contextlib
import errno
import hashlib
import os
import random
import re
import shutil
import tempfile
import uuid

import netaddr
from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import paramiko
import six

from magnum.common import exception
from magnum.i18n import _
from magnum.i18n import _LE
from magnum.i18n import _LW


# Default symbols to use for passwords. Avoids visually confusing characters.
# ~6 bits per symbol
DEFAULT_PASSWORD_SYMBOLS = ['23456789',  # Removed: 0,1
                            'ABCDEFGHJKLMNPQRSTUVWXYZ',   # Removed: I, O
                            'abcdefghijkmnopqrstuvwxyz']  # Removed: l

UTILS_OPTS = [
    cfg.StrOpt('rootwrap_config',
               default="/etc/magnum/rootwrap.conf",
               help='Path to the rootwrap configuration file to use for '
                    'running commands as root.'),
    cfg.StrOpt('tempdir',
               help='Explicitly specify the temporary working directory.'),
    cfg.ListOpt('password_symbols',
                default=DEFAULT_PASSWORD_SYMBOLS,
                help='Symbols to use for passwords')
]

CONF = cfg.CONF
CONF.register_opts(UTILS_OPTS)

LOG = logging.getLogger(__name__)

MEMORY_UNITS = {
    'Ki': 2 ** 10,
    'Mi': 2 ** 20,
    'Gi': 2 ** 30,
    'Ti': 2 ** 40,
    'Pi': 2 ** 50,
    'Ei': 2 ** 60,
    'm': 10 ** -3,
    'k': 10 ** 3,
    'M': 10 ** 6,
    'G': 10 ** 9,
    'T': 10 ** 12,
    'p': 10 ** 15,
    'E': 10 ** 18,
    '': 1
}

DOCKER_MEMORY_UNITS = {
    'b': 1,
    'k': 2 ** 10,
    'm': 2 ** 20,
    'g': 2 ** 30,
}


def _get_root_helper():
    return 'sudo magnum-rootwrap %s' % CONF.rootwrap_config


def execute(*cmd, **kwargs):
    """Convenience wrapper around oslo's execute() method.

    :param cmd: Passed to processutils.execute.
    :param use_standard_locale: True | False. Defaults to False. If set to
                                True, execute command with standard locale
                                added to environment variables.
    :returns: (stdout, stderr) from process execution
    :raises: UnknownArgumentError
    :raises: ProcessExecutionError
    """

    use_standard_locale = kwargs.pop('use_standard_locale', False)
    if use_standard_locale:
        env = kwargs.pop('env_variables', os.environ.copy())
        env['LC_ALL'] = 'C'
        kwargs['env_variables'] = env
    if kwargs.get('run_as_root') and 'root_helper' not in kwargs:
        kwargs['root_helper'] = _get_root_helper()
    result = processutils.execute(*cmd, **kwargs)
    LOG.debug('Execution completed, command line is "%s"',
              ' '.join(map(str, cmd)))
    LOG.debug('Command stdout is: "%s"', result[0])
    LOG.debug('Command stderr is: "%s"', result[1])
    return result


def trycmd(*args, **kwargs):
    """Convenience wrapper around oslo's trycmd() method."""
    if kwargs.get('run_as_root') and 'root_helper' not in kwargs:
        kwargs['root_helper'] = _get_root_helper()
    return processutils.trycmd(*args, **kwargs)


def ssh_connect(connection):
    """Method to connect to a remote system using ssh protocol.

    :param connection: a dict of connection parameters.
    :returns: paramiko.SSHClient -- an active ssh connection.
    :raises: SSHConnectFailed

    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_contents = connection.get('key_contents')
        if key_contents:
            data = six.moves.StringIO(key_contents)
            if "BEGIN RSA PRIVATE" in key_contents:
                pkey = paramiko.RSAKey.from_private_key(data)
            elif "BEGIN DSA PRIVATE" in key_contents:
                pkey = paramiko.DSSKey.from_private_key(data)
            else:
                # Can't include the key contents - secure material.
                raise ValueError(_("Invalid private key"))
        else:
            pkey = None
        ssh.connect(connection.get('host'),
                    username=connection.get('username'),
                    password=connection.get('password'),
                    port=connection.get('port', 22),
                    pkey=pkey,
                    key_filename=connection.get('key_filename'),
                    timeout=connection.get('timeout', 10))

        # send TCP keepalive packets every 20 seconds
        ssh.get_transport().set_keepalive(20)
    except Exception as e:
        LOG.debug("SSH connect failed: %s", e)
        raise exception.SSHConnectFailed(host=connection.get('host'))

    return ssh


def generate_uid(topic, size=8):
    characters = '01234567890abcdefghijklmnopqrstuvwxyz'
    choices = [random.choice(characters) for _x in range(size)]
    return '%s-%s' % (topic, ''.join(choices))


def random_alnum(size=32):
    characters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join(random.choice(characters) for _ in range(size))


def delete_if_exists(pathname):
    """delete a file, but ignore file not found error."""

    try:
        os.unlink(pathname)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            raise


def is_int_like(val):
    """Check if a value looks like an int."""
    try:
        return str(int(val)) == str(val)
    except Exception:
        return False


def is_valid_boolstr(val):
    """Check if the provided string is a valid bool string or not."""
    boolstrs = ('true', 'false', 'yes', 'no', 'y', 'n', '1', '0')
    return str(val).lower() in boolstrs


def is_valid_mac(address):
    """Verify the format of a MAC address.

    Check if a MAC address is valid and contains six octets. Accepts
    colon-separated format only.

    :param address: MAC address to be validated.
    :returns: True if valid. False if not.

    """
    m = "[0-9a-f]{2}(:[0-9a-f]{2}){5}$"
    if isinstance(address, six.string_types) and re.match(m, address.lower()):
        return True
    return False


def validate_and_normalize_mac(address):
    """Validate a MAC address and return normalized form.

    Checks whether the supplied MAC address is formally correct and
    normalize it to all lower case.

    :param address: MAC address to be validated and normalized.
    :returns: Normalized and validated MAC address.
    :raises: InvalidMAC If the MAC address is not valid.

    """
    if not is_valid_mac(address):
        raise exception.InvalidMAC(mac=address)
    return address.lower()


def is_valid_ipv4(address):
    """Verify that address represents a valid IPv4 address."""
    try:
        return netaddr.valid_ipv4(address)
    except Exception:
        return False


def is_valid_ipv6(address):
    try:
        return netaddr.valid_ipv6(address)
    except Exception:
        return False


def is_valid_ipv6_cidr(address):
    try:
        str(netaddr.IPNetwork(address, version=6).cidr)
        return True
    except Exception:
        return False


def get_shortened_ipv6(address):
    addr = netaddr.IPAddress(address, version=6)
    return str(addr.ipv6())


def get_shortened_ipv6_cidr(address):
    net = netaddr.IPNetwork(address, version=6)
    return str(net.cidr)


def is_valid_cidr(address):
    """Check if the provided ipv4 or ipv6 address is a valid CIDR address."""
    try:
        # Validate the correct CIDR Address
        netaddr.IPNetwork(address)
    except netaddr.core.AddrFormatError:
        return False
    except UnboundLocalError:
        # NOTE(MotoKen): work around bug in netaddr 0.7.5 (see detail in
        # https://github.com/drkjam/netaddr/issues/2)
        return False

    # Prior validation partially verify /xx part
    # Verify it here
    ip_segment = address.split('/')

    if (len(ip_segment) <= 1 or
            ip_segment[1] == ''):
        return False

    return True


def get_ip_version(network):
    """Returns the IP version of a network (IPv4 or IPv6).

    :raises: AddrFormatError if invalid network.
    """
    if netaddr.IPNetwork(network).version == 6:
        return "IPv6"
    elif netaddr.IPNetwork(network).version == 4:
        return "IPv4"


def convert_to_list_dict(lst, label):
    """Convert a value or list into a list of dicts."""
    if not lst:
        return None
    if not isinstance(lst, list):
        lst = [lst]
    return [{label: x} for x in lst]


def sanitize_hostname(hostname):
    """Return a hostname which conforms to RFC-952 and RFC-1123 specs."""
    hostname = six.text_type(hostname)

    hostname = re.sub('[ _]', '-', hostname)
    hostname = re.sub('[^a-zA-Z0-9_.-]+', '', hostname)
    hostname = hostname.lower()
    hostname = hostname.strip('.-')

    return hostname


def read_cached_file(filename, cache_info, reload_func=None):
    """Read from a file if it has been modified.

    :param cache_info: dictionary to hold opaque cache.
    :param reload_func: optional function to be called with data when
                        file is reloaded due to a modification.

    :returns: data from file

    """
    mtime = os.path.getmtime(filename)
    if not cache_info or mtime != cache_info.get('mtime'):
        LOG.debug("Reloading cached file %s", filename)
        with open(filename) as fap:
            cache_info['data'] = fap.read()
        cache_info['mtime'] = mtime
        if reload_func:
            reload_func(cache_info['data'])
    return cache_info['data']


def file_open(*args, **kwargs):
    """Open file

    see built-in file() documentation for more details

    Note: The reason this is kept in a separate module is to easily
          be able to provide a stub module that doesn't alter system
          state at all (for unit tests)
    """
    return file(*args, **kwargs)


def hash_file(file_like_object):
    """Generate a hash for the contents of a file."""
    checksum = hashlib.sha1()
    for chunk in iter(lambda: six.b(file_like_object.read(32768)), b''):
        checksum.update(chunk)
    return checksum.hexdigest()


@contextlib.contextmanager
def tempdir(**kwargs):
    tempfile.tempdir = CONF.tempdir
    tmpdir = tempfile.mkdtemp(**kwargs)
    try:
        yield tmpdir
    finally:
        try:
            shutil.rmtree(tmpdir)
        except OSError as e:
            LOG.error(_LE('Could not remove tmpdir: %s'), e)


def mkfs(fs, path, label=None):
    """Format a file or block device

    :param fs: Filesystem type (examples include 'swap', 'ext3', 'ext4'
               'btrfs', etc.)
    :param path: Path to file or block device to format
    :param label: Volume label to use
    """
    if fs == 'swap':
        args = ['mkswap']
    else:
        args = ['mkfs', '-t', fs]
    # add -F to force no interactive execute on non-block device.
    if fs in ('ext3', 'ext4'):
        args.extend(['-F'])
    if label:
        if fs in ('msdos', 'vfat'):
            label_opt = '-n'
        else:
            label_opt = '-L'
        args.extend([label_opt, label])
    args.append(path)
    try:
        execute(*args, run_as_root=True, use_standard_locale=True)
    except processutils.ProcessExecutionError as e:
        with excutils.save_and_reraise_exception() as ctx:
            if os.strerror(errno.ENOENT) in e.stderr:
                ctx.reraise = False
                LOG.exception(_LE('Failed to make file system. '
                                  'File system %s is not supported.'), fs)
                raise exception.FileSystemNotSupported(fs=fs)
            else:
                LOG.exception(_LE('Failed to create a file system '
                                  'in %(path)s. Error: %(error)s'),
                              {'path': path, 'error': e})


def unlink_without_raise(path):
    try:
        os.unlink(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            LOG.warning(_LW("Failed to unlink %(path)s, error: %(e)s"),
                        {'path': path, 'e': e})


def rmtree_without_raise(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
    except OSError as e:
        LOG.warning(_LW("Failed to remove dir %(path)s, error: %(e)s"),
                    {'path': path, 'e': e})


def write_to_file(path, contents):
    with open(path, 'w') as f:
        f.write(contents)


def create_link_without_raise(source, link):
    try:
        os.symlink(source, link)
    except OSError as e:
        if e.errno == errno.EEXIST:
            return
        else:
            LOG.warning(_LW("Failed to create symlink from %(source)s to "
                            "%(link)s, error: %(e)s"),
                        {'source': source, 'link': link, 'e': e})


def safe_rstrip(value, chars=None):
    """Removes trailing characters from a string if that does not make it empty

    :param value: A string value that will be stripped.
    :param chars: Characters to remove.
    :return: Stripped value.

    """
    if not isinstance(value, six.string_types):
        LOG.warning(_LW(
            "Failed to remove trailing character. Returning original object. "
            "Supplied object is not a string: %s,"
        ), value)
        return value

    return value.rstrip(chars) or value


def generate_uuid():
    return str(uuid.uuid4())


def is_uuid_like(val):
    """Returns validation of a value as a UUID.

    For our purposes, a UUID is a canonical form string:
    aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa

    """
    try:
        return str(uuid.UUID(val)) == val
    except (TypeError, ValueError, AttributeError):
        return False


def mount(src, dest, *args):
    """Mounts a device/image file on specified location.

    :param src: the path to the source file for mounting
    :param dest: the path where it needs to be mounted.
    :param args: a tuple containing the arguments to be
        passed to mount command.
    :raises: processutils.ProcessExecutionError if it failed
        to run the process.
    """
    args = ('mount', ) + args + (src, dest)
    execute(*args, run_as_root=True, check_exit_code=[0])


def umount(loc, *args):
    """Umounts a mounted location.

    :param loc: the path to be unmounted.
    :param args: a tuple containing the argumnets to be
        passed to the umount command.
    :raises: processutils.ProcessExecutionError if it failed
        to run the process.
    """
    args = ('umount', ) + args + (loc, )
    execute(*args, run_as_root=True, check_exit_code=[0])


def dd(src, dst, *args):
    """Execute dd from src to dst.

    :param src: the input file for dd command.
    :param dst: the output file for dd command.
    :param args: a tuple containing the arguments to be
        passed to dd command.
    :raises: processutils.ProcessExecutionError if it failed
        to run the process.
    """
    execute('dd', 'if=%s' % src, 'of=%s' % dst, *args,
            run_as_root=True, check_exit_code=[0])


def is_name_safe(name):
    """Checks whether the name is valid or not.

    :param name: name of the resource.
    :returns: True, when name is valid
              False, otherwise.
    """
    # TODO(madhuri): There should be some validation of name.
    # Leaving it now as there is no validation
    # while resource creation.
    # https://bugs.launchpad.net/magnum/+bug/1430617
    if not name:
        return False
    return True


def raise_exception_invalid_scheme(url):
    valid_schemes = ['http', 'https']

    if not isinstance(url, six.string_types):
        raise exception.Urllib2InvalidScheme(url=url)

    scheme = url.split(':')[0]
    if scheme not in valid_schemes:
        raise exception.Urllib2InvalidScheme(url=url)


def get_k8s_quantity(quantity):
    """This function is used to get k8s quantity.

    It supports to get CPU and Memory quantity:

    Kubernetes cpu format must be in the format of:

        <signedNumber>'m'
        for example:
        500m = 0.5 core of cpu

    Kubernetes memory format must be in the format of:

        <signedNumber><suffix>
        signedNumber = digits|digits.digits|digits.|.digits
        suffix = Ki|Mi|Gi|Ti|Pi|Ei|m|k|M|G|T|P|E|''
        or suffix = E|e<signedNumber>
        digits = digit | digit<digits>
        digit = 0|1|2|3|4|5|6|7|8|9

    :param name: String value of a quantity such as '500m', '1G'
    :returns: Quantity number
    :raises: exception.UnsupportedK8sQuantityFormat if the quantity string
             is a unsupported value
    """

    signed_num_regex = r"(^\d+\.\d+)|(^\d+\.)|(\.\d+)|(^\d+)"
    matched_signed_number = re.search(signed_num_regex, quantity)
    if matched_signed_number is None:
        raise exception.UnsupportedK8sQuantityFormat()
    else:
        signed_number = matched_signed_number.group(0)
    suffix = quantity.replace(signed_number, '', 1)
    if suffix == '':
        return float(quantity)
    if re.search(r"^(Ki|Mi|Gi|Ti|Pi|Ei|m|k|M|G|T|P|E|'')$", suffix):
        return float(signed_number) * MEMORY_UNITS[suffix]
    elif re.search(r"^[E|e][+|-]?(\d+\.\d+$)|(\d+\.$)|(\.\d+$)|(\d+$)",
                   suffix):
        return float(signed_number) * (10 ** float(suffix[1:]))
    else:
        raise exception.UnsupportedK8sQuantityFormat()


def get_docker_quanity(quantity):
    """This function is used to get swarm Memory quantity.

     Memory format must be in the format of:

        <unsignedNumber><suffix>
        suffix = b | k | m | g

    eg:  100m = 104857600
    :raises: exception.UnsupportedDockerQuantityFormat if the quantity string
             is a unsupported value
    """
    matched_unsigned_number = re.search(r"(^\d+)", quantity)

    if matched_unsigned_number is None:
        raise exception.UnsupportedDockerQuantityFormat()
    else:
        unsigned_number = matched_unsigned_number.group(0)

    suffix = quantity.replace(unsigned_number, '', 1)
    if suffix == '':
        return int(quantity)

    if re.search(r"^(b|k|m|g)$", suffix):
        return int(unsigned_number) * DOCKER_MEMORY_UNITS[suffix]

    raise exception.UnsupportedDockerQuantityFormat()


def generate_password(length, symbolgroups=None):
    """Generate a random password from the supplied symbol groups.

    At least one symbol from each group will be included. Unpredictable
    results if length is less than the number of symbol groups.

    Believed to be reasonably secure (with a reasonable password length!)

    """

    if symbolgroups is None:
        symbolgroups = CONF.password_symbols

    r = random.SystemRandom()

    # NOTE(jerdfelt): Some password policies require at least one character
    # from each group of symbols, so start off with one random character
    # from each symbol group
    password = [r.choice(s) for s in symbolgroups]
    # If length < len(symbolgroups), the leading characters will only
    # be from the first length groups. Try our best to not be predictable
    # by shuffling and then truncating.
    r.shuffle(password)
    password = password[:length]
    length -= len(password)

    # then fill with random characters from all symbol groups
    symbols = ''.join(symbolgroups)
    password.extend([r.choice(symbols) for _i in range(length)])

    # finally shuffle to ensure first x characters aren't from a
    # predictable group
    r.shuffle(password)

    return ''.join(password)
