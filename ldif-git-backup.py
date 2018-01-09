#!/usr/bin/env python3
"""Script to backup LDAP databases in LDIF format using Git"""

import sys
import subprocess
import re
import argparse
import pathlib
import collections
import configparser
import time
import git


class Context(object):
    """Class containing all the context variables:
    - arg: parsed cmd-line arguments
    - param: chain-map: (order: filtered_args > config > defaults)
    - rgx_excl: compiled regular expression for attribute filtering
    """

    DEFAULTS = {
        'ldif_cmd': '',
        'ldif_file': '',
        'ldif_stdin': False,
        'backup_dir': 'ldif-git-backup',
        'commit_msg': 'ldif-git-backup',
        'excl_attrs': '',
        'ldif_attr': '',
        'no_gc': False,
        'no_rm': False,
        'no_add': False,
        'no_commit': False,
        'single_ldif': False,
        'ldif_name': 'db',
        'ldif_wrap': False,
    }

    def __init__(self):
        self.parse_args()
        self.var = {
            'start_time': None,
            'rgx_excl': None,
            'path_prefix': None,
            'repo': None,
            'new_commit_files': None,
            'last_commit_files': None,
        }
        self.start_time_measurement()
        self.print_start_time()
        self.initialize_param()
        self.print_active_parameters()
        self.initialize_input_method()
        self.initialize_ldif_attr()
        self.initialize_regex()
        self.clean_ldif_cmd()

    def parse_args(self):
        """Parse cmd-line arguments"""
        parser = argparse.ArgumentParser(
            add_help=False, description='''Backup LDAP databases in LDIF format
            using Git. The LDIF (Lightweight Directory Interchange Format)
            input can be read either from stdin, subprocess or file. Care must
            be taken to use the correct parameters, which create the LDIF
            input. By default ldif-git-backup will split the LDIF to entries
            and save each entry in a file named after the entry's UUID. If
            these defaults are used, the LDIF must contain operational
            attributes or at least the `entryUUID` attribute.'''
        )
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument(
            '-i', '--ldif-stdin',
            dest='stdin', action='store_const', const=True,
            help='Read LDIF from stdin (default)'
        )
        group.add_argument(
            '-x', '--ldif-cmd',
            dest='ldif_cmd', type=str,
            help='Read LDIF from subprocess'
        )
        group.add_argument(
            '-l', '--ldif-file',
            dest='ldif_file', type=str,
            help='Read LDIF from file'
        )
        parser.add_argument(
            '-d', '--backup-dir',
            dest='backup_dir', type=str,
            help='''The directory for the git backup repository (default:
            `/var/backups/ldap`)'''
        )
        parser.add_argument(
            '-m', '--commit-msg',
            dest='commit_msg', type=str,
            help='The commit message (default: `ldif-git-backup`)'
        )
        parser.add_argument(
            '-e', '--excl-attrs',
            dest='excl_attrs', type=str,
            help='''Exclude all attributes matching the regular expression
            `^(EXCLUDE_ATTRS): `'''
        )
        parser.add_argument(
            '-a', '--ldif-attr',
            dest='ldif_attr', type=str,
            help='''The value of attribute LDIF_ATTR will be used as filename.
            This attribute must be unique in the LDIF. If the attribute is not
            present in the entry, the whole entry will be silently skipped.
            This parameter has no effect if combined with `-s`. If the
            attribute is not unique, bad things will happen, as entries will
            overwrite eachother. (default: `entryUUID`)'''
        )
        parser.add_argument(
            '-s', '--single-ldif',
            dest='single_ldif', action='store_const', const=True,
            help='Use single LDIF mode, do not split entries to files'
        )
        parser.add_argument(
            '-n', '--ldif-name',
            dest='ldif_name', type=str,
            help='''Use LDIF_NAME as filename in single-ldif mode (default:
            `db`)'''
        )
        parser.add_argument(
            '-c', '--config',
            dest='config', type=str,
            help='''Use configuration with saection name CONFIG (default:
            `ldif-git-backup`)'''
        )
        parser.add_argument(
            '-f', '--config-file',
            dest='config_file', type=str,
            help='''Path to the configuration file (default:
            `./ldif-git-backup.conf`)'''
        )
        parser.add_argument(
            '-G', '--no-gc',
            dest='no_gc', action='store_const', const=True,
            help='Do not perform garbage collection'
        )
        parser.add_argument(
            '-R', '--no-rm',
            dest='no_rm', action='store_const', const=True,
            help='Do not perform git rm'
        )
        parser.add_argument(
            '-A', '--no-add',
            dest='no_add', action='store_const', const=True,
            help='Do not perform git add'
        )
        parser.add_argument(
            '-C', '--no-commit',
            dest='no_commit', action='store_const', const=True,
            help='Do not perform git commit'
        )
        parser.add_argument(
            '-w', '--ldif-wrap',
            dest='ldif_wrap', action='store_const', const=True,
            help='''Set if LDIF input is wrapped, this will unwrap any wrapped
            attributes. By default the input LDIF is expected to be unwrapped
            for optimal performance'''
        )
        parser.add_argument(
            '-v', '--verbose',
            dest='verbose', action='store_const', const=True,
            help='Enable verbose mode'
        )
        parser.add_argument(
            '-p', '--print-params',
            dest='print_params', action='store_const', const=True,
            help='Print active parameters and exit'
        )
        parser.add_argument(
            '-h', '--help',
            action='help',
            help='Show this help message and exit'
        )
        self.arg = vars(parser.parse_args())

    def parse_config(self):
        """Parse configuration file"""
        cinterpol = configparser.ExtendedInterpolation()
        cparser = configparser.ConfigParser(interpolation=cinterpol)
        if self.arg['config_file']:
            cpath = pathlib.PosixPath(self.arg['config_file'])
            if cpath.is_file():
                cparser.read(self.arg['config_file'])
            else:
                sys.exit('Error: invalid config file')
        else:
            cparser.read('ldif-git-backup.conf')

        if self.arg['config']:
            if cparser.has_section(self.arg['config']):
                config_params = cparser[self.arg['config']].items()
            else:
                sys.exit('Error: no config section named %s'
                         % self.arg['config'])
        elif cparser.has_section('ldif-git-backup'):
            config_params = cparser['ldif-git-backup'].items()
        else:
            config_params = None
        return config_params

    def filter_config(self, config_params):
        """Filter configuration parameters"""
        if config_params:
            config = {k: v for k, v in config_params if v}
        else:
            config = {}
        defaults = self.DEFAULTS.items()
        defaults_bool = [k for k, v in defaults if isinstance(v, bool)]
        for k in defaults_bool:
            if k in config:
                if config[k].lower() == 'true':
                    config[k] = True
                elif config[k].lower() == 'false':
                    config[k] = False
                else:
                    del config[k]
        return config

    def initialize_param(self):
        """Create param dict with chained default values"""
        # Parse cmd-line arguments
        filtered_args = {k: v for k, v in self.arg.items() if v}

        # Parse configuration file
        config_params = self.parse_config()
        filtered_config = self.filter_config(config_params)

        # Create param dict with chained default values
        chain_map = collections.ChainMap(filtered_args,
                                         filtered_config,
                                         self.DEFAULTS)
        self.param = chain_map

    def verbose(self, *messages):
        """Print current execution time and status message"""
        current_time = time.perf_counter()
        elapsed_time = current_time - self.var['start_time']
        print(''.join(['', '%0.3f' % elapsed_time, 's:']), ' '.join(messages))

    def start_time_measurement(self):
        """Set the start time"""
        if self.arg['verbose']:
            self.var['start_time'] = time.perf_counter()

    def end_time_measurement(self):
        """Print execution time"""
        if self.arg['verbose']:
            self.verbose('execution finished')

    def print_start_time(self):
        """Start measuring runtime"""
        if self.arg['verbose']:
            self.verbose('starting runtime measurement')

    def print_active_parameters(self):
        """Print active parameters"""
        if self.arg['verbose'] or self.arg['print_params']:
            pad_len = 0
            if self.arg['verbose']:
                self.verbose('parameters:')
                pad_len = 12
            col_width = max(len(str(k)) for k in self.param.keys()) + 3
            for key, value in self.param.items():
                col_left = ''.join([str(key), ':']).ljust(col_width)
                col_right = str(value)
                print(''.join([' ' * pad_len, col_left, col_right]))
            if self.arg['print_params']:
                sys.exit()

    def initialize_input_method(self):
        """Sets the flags to the correct values"""
        if self.param['ldif_stdin']:
            self.param['ldif_cmd'] = False
            self.param['ldif_file'] = False
        elif self.param['ldif_cmd']:
            self.param['ldif_file'] = False

    def initialize_ldif_attr(self):
        """Set ldif_attr to entryUUID if not set"""
        if not self.param['ldif_attr']:
            self.param['ldif_attr'] = 'entryUUID'

    def initialize_regex(self):
        """Compile regular expressions"""
        if self.param['excl_attrs']:
            regex = r'(' + self.param['excl_attrs'] + r'): '
            self.var['rgx_excl'] = re.compile(regex)

    def clean_ldif_cmd(self):
        """Replace all whitespace characters with single whitespace"""
        ldif_cmd = self.param['ldif_cmd']
        if ldif_cmd:
            clean_ldif_cmd = re.sub(r'\s+', ' ', ldif_cmd)
            if self.arg['verbose']:
                self.verbose('cleaned up ldif_cmd:', clean_ldif_cmd)
            self.param['ldif_cmd'] = clean_ldif_cmd.split(' ')


def create_backup_directory(context):
    """Create backup directory"""
    dpath = pathlib.PosixPath(context.param['backup_dir'])
    dpath.mkdir(mode=0o700, parents=True, exist_ok=True)
    context.var['path_prefix'] = ''.join([dpath.as_posix(), '/'])


def initialize_git_repository(context):
    """Initialize git repo, get file list from last commit"""
    param = context.param
    arg = context.arg
    var = context.var

    if not (param['no_rm'] and param['no_add'] and param['no_gc'] and
            param['no_commit']):
        if arg['verbose']:
            context.verbose('initializing git repo:', var['path_prefix'])
        repo = git.Repo.init(var['path_prefix'])
        context.var['repo'] = repo

    if not param['no_rm']:
        if len(repo.heads) == 0:
            var['last_commit_files'] = []
        else:
            files_in_repo_root = repo.head.commit.tree.blobs
            var['last_commit_files'] = [f.name for f in files_in_repo_root]
        if arg['verbose']:
            context.verbose('files in repository:',
                            str(len(var['last_commit_files'])))


def get_input_method(context):
    """Determine LDIF input method and return file descriptor"""
    param = context.param
    arg = context.arg

    if param['ldif_file']:
        fin = open(param['ldif_file'], 'r')
        if arg['verbose']:
            context.verbose('reading ldif from file')
    elif param['ldif_cmd']:
        proc = subprocess.Popen(param['ldif_cmd'], stdout=subprocess.PIPE)
        fin = proc.stdout
        if arg['verbose']:
            context.verbose('reading ldif from subprocess')
    else:
        fin = sys.stdin
        if arg['verbose']:
            context.verbose('reading ldif from stdin')

    return fin


def get_output_method(context):
    """"Determine LDIF output method and return file descriptor"""
    arg = context.arg
    param = context.param
    var = context.var
    files = []

    if param['single_ldif']:
        # Open LDIF file for writing
        fname = ''.join([param['ldif_name'], '.ldif'])
        fpath = ''.join([var['path_prefix'], fname])
        files.append(fname)
        fout = open(fpath, 'w')
        if arg['verbose']:
            context.verbose('single-ldif mode, writing to:', fname)
        return fout, files
    else:
        if arg['verbose']:
            context.verbose('multi-ldif mode, writing to:',
                            ''.join(['<', param['ldif_attr'], '>', '.ldif']))
        return None, files


def close_file_descriptors(fin, fout):
    """Close file descriptors"""
    fin.close()
    if fout:
        fout.close()


class LoopVariables(object):
    """Flags used in loop"""
    def __init__(self, context):
        self.ldif_cmd = False
        self.excl_attrs = False
        self.single_ldif = False
        self.ldif_wrap = False
        self.path_prefix = None
        self.fname_attr_search = None
        self.rgx_excl = None
        self.init_vars(context)

    def init_vars(self, context):
        """Initialize vars"""
        if context.var['path_prefix']:
            self.path_prefix = True
        if context.param['ldif_cmd']:
            self.ldif_cmd = True
        if context.param['excl_attrs']:
            self.excl_attrs = True
        if context.param['single_ldif']:
            self.single_ldif = True
        if context.param['ldif_wrap']:
            self.ldif_wrap = True
        self.init_path_prefix(context.var)
        self.init_fname_attr_search(context.param)
        self.init_rgx_excl(context.var)

    def init_path_prefix(self, var):
        """Initialize path_prefix"""
        self.path_prefix = var['path_prefix']

    def init_fname_attr_search(self, param):
        """Initialize fname_attr_search"""
        self.fname_attr_search = ''.join([param['ldif_attr'], ': '])

    def init_rgx_excl(self, var):
        """Initialize rgx_excl"""
        self.rgx_excl = var['rgx_excl']


def write_ldif(var, fout, entry, fname_attr_val, files):
    """Write the LDIF"""
    if var.single_ldif:
        # Add entry to single LDIF file
        fout.write(''.join([entry, '\n']))
    else:
        # Write entry to new LDIF file
        if fname_attr_val:
            fname = ''.join([fname_attr_val, '.ldif'])
            fpath = ''.join([var.path_prefix, fname])
            with open(fpath, 'w') as fout_new:
                fout_new.write(''.join([entry, '\n']))
            files.append(fname)


def loop_unwrap(var, fin, fout, files):
    """Stream from LDIF input and write LDIF output"""
    entry, attr = '', ''
    fname = None
    while True:
        line = fin.readline()
        # Exit the loop when finished reading
        if not line:
            break
        # Optional decode bytes from subprocess
        if var.ldif_cmd:
            line = line.decode('utf-8')
        # End of an entry
        if line == '\n':
            # Get value of attribute for use as filename
            if attr.startswith(var.fname_attr_search):
                fname = attr.split(var.fname_attr_search, 1)[1].rstrip()
            # Filter out attributes
            if var.excl_attrs:
                match_excl = var.rgx_excl.match(attr)
                if not match_excl:
                    # Add last attribute (part)
                    entry = ''.join([entry, attr])
            # Write LDIF file
            write_ldif(var, fout, entry, fname, files)
            # Prepare local variables for next entry
            entry, attr = '', ''
            fname = None
            continue
        # Append the lines to entry
        if line.startswith(' '):
            attr = ''.join([attr.rstrip(), line[1:]])
        else:
            # Get value of attribute for use as filename
            if attr.startswith(var.fname_attr_search):
                fname = attr.split(var.fname_attr_search, 1)[1].rstrip()
            # Filter out attributes
            if var.excl_attrs:
                match_excl = var.rgx_excl.match(attr)
                if not match_excl:
                    entry = ''.join([entry, attr])
            attr = line

    return files


def loop(var, fin, fout, files):
    """Stream from LDIF input and write LDIF output"""
    entry = ''
    fname = None
    while True:
        line = fin.readline()
        # Exit the loop when finished reading
        if not line:
            break
        # Optional decode bytes from subprocess
        if var.ldif_cmd:
            line = line.decode('utf-8')
        # End of an entry
        if line == '\n':
            # Write LDIF file
            write_ldif(var, fout, entry, fname, files)
            # Prepare for next entry
            entry = ''
            fname = None
            continue
        # Get value of attribute for use as filename
        if line.startswith(var.fname_attr_search):
            fname = line.split(var.fname_attr_search, 1)[1].rstrip()
        # Filter out attributes
        if var.excl_attrs:
            match_excl = var.rgx_excl.match(line)
            if match_excl:
                continue
        # Append the lines to entry
        entry = ''.join([entry, line])

    return files


def process_ldif(context):
    """Process LDIF with method depending on the parameters"""
    # Local variables to speed up processing
    loop_var = LoopVariables(context)
    fin = get_input_method(context)
    fout, files = get_output_method(context)

    if not context.param['ldif_wrap']:
        files = loop(loop_var, fin, fout, files)
    else:
        files = loop_unwrap(loop_var, fin, fout, files)

    context.var['new_commit_files'] = files
    close_file_descriptors(fin, fout)


def git_add(context):
    """Add new LDIF files to index (stage)"""
    if not context.param['no_add']:
        repo = context.var['repo']
        new_commit_files = context.var['new_commit_files']
        if context.arg['verbose']:
            context.verbose('adding git files:', str(len(new_commit_files)))
        repo.index.add(new_commit_files)


def git_remove(context):
    """Remove unneeded LDIF files from index"""
    if not context.param['no_rm']:
        repo = context.var['repo']
        last_commit_files = context.var['last_commit_files']
        new_commit_files = context.var['new_commit_files']
        to_remove_files = set(last_commit_files) - set(new_commit_files)
        if context.arg['verbose']:
            context.verbose('removing git files:', str(len(to_remove_files)))
        if to_remove_files:
            repo.index.remove(to_remove_files, working_tree=True)


def git_commit(context):
    """Commit the changes"""
    if not context.param['no_commit']:
        repo = context.var['repo']
        if context.arg['verbose']:
            context.verbose('commiting git files')
        repo.index.commit(context.param['commit_msg'])


def git_garbage_collect(context):
    """Clean up the repo"""
    if not context.param['no_gc']:
        repo = context.var['repo']
        if context.arg['verbose']:
            context.verbose('triggering git garbage collection')
        repo.git.gc('--auto')


def main():
    """The main function"""
    context = Context()

    create_backup_directory(context)
    initialize_git_repository(context)

    process_ldif(context)

    git_add(context)
    git_remove(context)
    git_commit(context)
    git_garbage_collect(context)

    context.end_time_measurement()


if __name__ == "__main__":
    main()
