#!/usr/bin/env python3
"""Script to backup LDAP databases in LDIF format using Git"""

from __future__ import print_function
import sys
import subprocess
import re
import argparse
import pathlib
import collections
import configparser
import time
import git


def eprint(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)


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
        'ldif_v1': False,
        'ldif_mem': False,
        'no_out': False,
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
            attributes or at least the `entryUUID` attribute. The LDIF input
            format is expected to be in slapcat format without line wrapping or
            comments. This LDIF format can be generated using the commands
            `slapcat -o ldif-wrap=no` or `ldapsearch -LLL -o ldif-wrap=no '*'
            +`. If the LDIF input is in slapcat format but with line wrapping,
            the option `-w` can be used. This will unwrap all lines and write
            the LDIF output unwrapped. If the LDIF input is in LDIFv1 format
            (Version: 1) as per RFC 2849, the option `-1` can be used. This
            will correctly handle LDIFv1 input (for example if it contains
            comments or mutliple blank lines between entries). Any comments
            will be stripped off the output LDIF, line wrapping is preserved.
            Using this mode is a bit slower than the default mode.'''
        )
        group_input = parser.add_mutually_exclusive_group(required=False)
        group_input.add_argument(
            '-i', '--ldif-stdin',
            dest='stdin', action='store_const', const=True,
            help='Read LDIF from stdin (default)'
        )
        group_input.add_argument(
            '-x', '--ldif-cmd',
            dest='ldif_cmd', type=str,
            help='Read LDIF from subprocess'
        )
        group_input.add_argument(
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
            '-O', '--no-out',
            dest='no_out', action='store_const', const=True,
            help='Do not write output LDIF file(s)'
        )
        group_ldif = parser.add_mutually_exclusive_group(required=False)
        group_ldif.add_argument(
            '-w', '--ldif-wrap',
            dest='ldif_wrap', action='store_const', const=True,
            help='''Set if LDIF input is wrapped, this will unwrap any wrapped
            attributes. By default the input LDIF is expected to be unwrapped
            for optimal performance'''
        )
        group_ldif.add_argument(
            '-1', '--ldif-v1',
            dest='ldif_v1', action='store_const', const=True,
            help='''Parse input in LDIFv1 format (Version: 1) as per RFC 2849.
            Comments are ignored, line wrapping is preserved. Using this mode
            is a bit slower than the default mode.'''
        )
        parser.add_argument(
            '--mem',
            dest='ldif_mem', action='store_const', const=True,
            help='Read input LDIF to memory first (experimental option)'
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
        if self.arg['verbose']:
            current_time = time.perf_counter()
            elapsed_time = current_time - self.var['start_time']
            print(''.join(['', '%0.3f' % elapsed_time, 's:']), ' '.join(messages))

    def start_time_measurement(self):
        """Set the start time"""
        if self.arg['verbose']:
            self.var['start_time'] = time.perf_counter()
        self.verbose('start runtime measurement')

    def end_time_measurement(self):
        """Print execution time"""
        self.verbose('execution finished')

    def print_active_parameters(self):
        """Print active parameters"""
        if self.arg['print_params']:
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
    var = context.var

    if not (param['no_rm'] and param['no_add'] and param['no_gc'] and
            param['no_commit']):
        context.verbose('initializing git repo:', var['path_prefix'])
        repo = git.Repo.init(var['path_prefix'])
        context.var['repo'] = repo

    if not param['no_rm']:
        if len(repo.heads) == 0:
            var['last_commit_files'] = []
        else:
            files_in_repo_root = repo.head.commit.tree.blobs
            var['last_commit_files'] = [f.name for f in files_in_repo_root]
        context.verbose('files in repository:',
                        str(len(var['last_commit_files'])))


class LdifDeque(object):
    """Class to store LDIF in memory as deque"""
    def __init__(self):
        self.lines = collections.deque()

    def addline(self, line):
        """Add a line"""
        self.lines.append(line)

    def readline(self):
        """Return a line"""
        try:
            return self.lines.popleft()
        except IndexError:
            return None

    def close(self):
        """Imitate close of fd"""
        pass


def get_input_method(context):
    """Determine LDIF input method and return file descriptor"""
    param = context.param

    if param['ldif_file']:
        fin = open(param['ldif_file'], 'r')
        context.verbose('reading ldif from file')
    elif param['ldif_cmd']:
        proc = subprocess.Popen(param['ldif_cmd'], stdout=subprocess.PIPE)
        fin = proc.stdout
        context.verbose('reading ldif from subprocess')
    else:
        fin = sys.stdin
        context.verbose('reading ldif from stdin')
    if param['ldif_mem']:
        context.verbose('read input to memory')
        ldif = LdifDeque()
        while True:
            line = fin.readline()
            if not line:
                break
            ldif.addline(line)
        fin.close()
        context.verbose('ldif loaded:', str(len(ldif.lines)), 'lines')
        context.start_time_measurement()
        return ldif
    else:
        return fin


def get_output_method(context):
    """"Determine LDIF output method and return file descriptor"""
    param = context.param
    var = context.var
    files = []

    if param['single_ldif']:
        # Open LDIF file for writing
        fname = ''.join([param['ldif_name'], '.ldif'])
        fpath = ''.join([var['path_prefix'], fname])
        files.append(fname)
        fout = open(fpath, 'w')
        context.verbose('single-ldif mode, writing to:', fname)
        return fout, files
    else:
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
        self.no_out = False
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
        if context.param['no_out']:
            self.no_out = True
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
    entry.append('\n')
    if var.single_ldif:
        # Add entry to single LDIF file
        if not var.no_out:
            for line in entry:
                fout.write(line)
    else:
        # Write entry to new LDIF file
        if fname_attr_val:
            fname = ''.join([fname_attr_val, '.ldif'])
            fpath = ''.join([var.path_prefix, fname])
            if not var.no_out:
                with open(fpath, 'w') as fout_new:
                    for line in entry:
                        fout_new.write(line)
            files.append(fname)


def loop_ldifv1(var, fin, fout, files):
    """Stream from LDIFv1 input and write LDIF output"""
    entry_end = False
    ldif_end = False
    write_entry = False
    comment = False
    fname = None
    broken_attr = None
    finding_broken_attr = False
    fname_found = False
    next_line_broken = False
    next_line_sep = False
    line = parse_ldif_version(var, fin)
    next_line = None
    entry = []
    while True:
        next_line = fin.readline()
        if not next_line:
            ldif_end = True
            next_line = ''
        if var.ldif_cmd and not ldif_end:
            next_line = next_line.decode('utf-8')
        # check column 1
        if next_line[:1] == ' ':
            next_line_broken = True
            next_line_sep = False
        elif next_line[:1] == '\n' or next_line == '\r\n':
            next_line_sep = True
            next_line_broken = False
        else:
            next_line_broken = False
            next_line_sep = False
        if line[:1] == '#':
            comment = True
        # Filter comments
        if comment:
            if next_line_broken:
                continue
            elif next_line_sep:
                comment = False
                continue
            else:
                line = next_line
                comment = False
                continue
        # Filter newlines between entries
        if write_entry:
            entry_end = True
        if entry_end:
            if next_line_sep:
                continue
            else:
                write_entry = False
                entry_end = False
        elif next_line_sep:
            write_entry = True
        # Find broken attribute
        if finding_broken_attr:
            if next_line_broken:
                line = ''.join([line, next_line])
                continue
            else:
                finding_broken_attr = False
                broken_attr = True
                # Broken attribute found, next_line is new attribute
        elif next_line_broken:
            line = ''.join([line, next_line])
            finding_broken_attr = True
            continue
        else:
            broken_attr = False
        # Find filename and filter attributes
        if broken_attr:
            attr = line.replace('\r\n ', '').replace('\n ', '')
            if not var.single_ldif and not fname_found:
                if attr.startswith(var.fname_attr_search):
                    fname = attr.split(var.fname_attr_search, 1)[1].rstrip()
                    fname_found = True
                    # Found broken filename
            if var.excl_attrs:
                match_excl = var.rgx_excl.match(attr)
                if match_excl:
                    line = ''
                    # Broken attribute filtered
            broken_attr = False
        else:
            if not var.single_ldif and not fname_found:
                if line.startswith(var.fname_attr_search):
                    fname = line.split(var.fname_attr_search, 1)[1].rstrip()
                    fname_found = True
                    # Found filename attribute
            if var.excl_attrs:
                match_excl = var.rgx_excl.match(line)
                if match_excl:
                    line = ''
                    # Attribute filtered
        # Add line to entry
        if line:
            entry.append(line)
        if not ldif_end:
            line = next_line
        else:
            if entry:
                write_ldif(var, fout, entry, fname, files)
            break
        if write_entry:
            write_ldif(var, fout, entry, fname, files)
            entry = []
            line = ''
            fname_found = False
            fname = None

    return files


def loop_unwrap(var, fin, fout, files):
    """Stream from LDIF input and write LDIF output"""
    entry, attr = [], ''
    fname = None
    fname_found = False
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
            if not var.single_ldif and not fname_found:
                if attr.startswith(var.fname_attr_search):
                    fname = attr.split(var.fname_attr_search, 1)[1].rstrip()
            # Filter out attributes
            if var.excl_attrs:
                match_excl = var.rgx_excl.match(attr)
                if not match_excl:
                    # Add last attribute (part)
                    entry.append(attr)
            # Write LDIF file
            write_ldif(var, fout, entry, fname, files)
            # Prepare local variables for next entry
            entry, attr = [], ''
            fname = None
            fname_found = False
            continue
        # Append the lines to entry
        if line[:1] == ' ':
            # Attribute not complete (wrapped)
            attr = ''.join([attr.rstrip(), line[1:]])
            continue
        else:
            # New attribute (line)
            # Find filename
            if not var.single_ldif and not fname_found:
                if attr.startswith(var.fname_attr_search):
                    # Get value of attribute (attr) for use as filename
                    fname = attr.split(var.fname_attr_search, 1)[1].rstrip()
                    fname_found = True
            # Check if attribute (attr) is filtered
            if var.excl_attrs:
                match_excl = var.rgx_excl.match(attr)
                if not match_excl:
                    entry.append(attr)
            else:
                entry.append(attr)
        attr = line

    return files


def loop(var, fin, fout, files):
    """Stream from LDIF input and write LDIF output"""
    entry = []
    fname = None
    fname_found = False
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
            entry = []
            fname = None
            fname_found = False
            continue
        # Find filename
        if not var.single_ldif and not fname_found:
            if line.startswith(var.fname_attr_search):
                # Get value of attribute for use as filename
                fname = line.split(var.fname_attr_search, 1)[1].rstrip()
                fname_found = True
        # Check if attribute is filtered
        if var.excl_attrs:
            match_excl = var.rgx_excl.match(line)
            if match_excl:
                continue
        # Append the lines to entry
        entry.append(line)

    return files


def parse_ldif_version(var, fin):
    """Parse the LDIF version header"""
    while True:
        line = fin.readline()
        if not line:
            sys.exit("Error: parsing LDIF input")
        if var.ldif_cmd:
            line = line.decode('utf-8')
        if line.startswith('version:'):
            version = line.split(':', 1)[1].strip()
            if version != '1':
                eprint("Warning: expecting LDIFv1 compatible input")
        if line.startswith('dn:'):
            return line


def process_ldif(context):
    """Process LDIF with method depending on the parameters"""
    # Local variables to speed up processing
    loop_var = LoopVariables(context)
    fin = get_input_method(context)
    fout, files = get_output_method(context)

    if context.param['ldif_v1']:
        files = loop_ldifv1(loop_var, fin, fout, files)
    else:
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
        context.verbose('adding git files:', str(len(new_commit_files)))
        repo.index.add(new_commit_files)


def git_remove(context):
    """Remove unneeded LDIF files from index"""
    if not context.param['no_rm']:
        repo = context.var['repo']
        last_commit_files = context.var['last_commit_files']
        new_commit_files = context.var['new_commit_files']
        to_remove_files = set(last_commit_files) - set(new_commit_files)
        context.verbose('removing git files:', str(len(to_remove_files)))
        if to_remove_files:
            repo.index.remove(to_remove_files, working_tree=True)


def git_commit(context):
    """Commit the changes"""
    if not context.param['no_commit']:
        repo = context.var['repo']
        context.verbose('commiting git files')
        repo.index.commit(context.param['commit_msg'])


def git_garbage_collect(context):
    """Clean up the repo"""
    if not context.param['no_gc']:
        repo = context.var['repo']
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
