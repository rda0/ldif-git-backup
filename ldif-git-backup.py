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


def verbose(starttime, *messages):
    """Print current execution time and status message"""
    currenttime = time.perf_counter()
    runtime = currenttime - starttime
    print(''.join(['', '%0.3f' % runtime, 's:']), ' '.join(messages))


def main():
    """The main function"""
    # Define default parameter values
    defaults = {
        'ldif_cmd': '',
        'ldif_file': '',
        'ldif_stdin': False,
        'backup_dir': '/var/backups/ldap',
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

    # Parse cmd-line arguments
    parser = argparse.ArgumentParser(
        add_help=False, description='''Backup LDAP databases in LDIF format
        using Git. The LDIF (Lightweight Directory Interchange Format) input
        can be read either from stdin, subprocess or file. Care must be taken
        to use the correct parameters, which create the LDIF input. By default
        ldif-git-backup will split the LDIF to entries and save each entry in a
        file named after the entry's UUID. If these defaults are used, the LDIF
        must contain operational attributes or at least the `entryUUID`
        attribute.'''
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
        help='''The value of attribute LDIF_ATTR will be used as filename. This
        attribute must be unique in the LDIF. If the attribute is not present
        in the entry, the whole entry will be silently skipped. This parameter
        has no effect if combined with `-s`. If the attribute is not unique,
        bad things will happen, as entries will overwrite eachother. (default:
        `entryUUID`)'''
    )
    parser.add_argument(
        '-s', '--single-ldif',
        dest='single_ldif', action='store_const', const=True,
        help='Use single LDIF mode, do not split entries to files'
    )
    parser.add_argument(
        '-n', '--ldif-name',
        dest='ldif_name', type=str,
        help='Use LDIF_NAME as filename in single-ldif mode (default: `db`)'
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
        attributes. By default the input LDIF is expected to be unwrapped for
        optimal performance'''
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
    args = vars(parser.parse_args())
    filtered_args = {k: v for k, v in args.items() if v}

    # Start measuring runtime
    if args['verbose']:
        starttime = time.perf_counter()
        verbose(starttime, 'starting runtime measurement')

    # Parse configuration file
    cinterpol = configparser.ExtendedInterpolation()
    cparser = configparser.ConfigParser(interpolation=cinterpol)
    if args['config_file']:
        cpath = pathlib.PosixPath(args['config_file'])
        if cpath.is_file():
            cparser.read(args['config_file'])
        else:
            sys.exit('Error: invalid config file')
    else:
        cparser.read('ldif-git-backup.conf')
    if args['config']:
        if cparser.has_section(args['config']):
            config_params = cparser[args['config']].items()
        else:
            sys.exit('Error: no config section named %s' % args['config'])
    elif cparser.has_section('ldif-git-backup'):
        config_params = cparser['ldif-git-backup'].items()
    else:
        config_params = None
    if config_params:
        config = {k: v for k, v in config_params if v}
    else:
        config = {}
    defaults_bool = [k for k, v in defaults.items() if isinstance(v, bool)]
    for k in defaults_bool:
        if k in config:
            if config[k].lower() == 'true':
                config[k] = True
            elif config[k].lower() == 'false':
                config[k] = False
            else:
                del config[k]

    # Create param dict with chained default values
    param = collections.ChainMap(filtered_args, config, defaults)

    # Print active parameters
    if args['verbose'] or args['print_params']:
        pad_len = 0
        if args['verbose']:
            verbose(starttime, 'parameters:')
            pad_len = 12
        col_width = max(len(str(k)) for k in param.keys()) + 3
        for key, value in param.items():
            col_left = ''.join([str(key), ':']).ljust(col_width)
            col_right = str(value)
            print(''.join([' ' * pad_len, col_left, col_right]))
        if args['print_params']:
            sys.exit()

    # Define flags, compile regular expressions
    ldif_from_cmd = False
    ldif_from_file = False
    ldif_wrapped = False
    excl_attrs = False
    ldif_attr = 'entryUUID'
    single_ldif = False
    if not param['ldif_stdin']:
        if not param['ldif_cmd']:
            if param['ldif_file']:
                ldif_from_file = True
        elif param['ldif_cmd']:
            ldif_from_cmd = True
    if param['ldif_wrap']:
        ldif_wrapped = True
    if param['excl_attrs']:
        regex = r'(' + param['excl_attrs'] + r'): '
        rgx_excl = re.compile(regex)
        excl_attrs = True
    if param['ldif_attr']:
        ldif_attr = param['ldif_attr']
    if param['single_ldif']:
        single_ldif = True

    # Clean up ldif command
    ldif_cmd = re.sub(r'\s+', ' ', param['ldif_cmd']).split(' ')
    if args['verbose']:
        if ldif_cmd:
            verbose(starttime, 'cleaned up ldif_cmd:', ' '.join(ldif_cmd))

    # Create backup directory
    dpath = pathlib.PosixPath(param['backup_dir'])
    dpath.mkdir(mode=0o700, parents=True, exist_ok=True)
    path_prefix = ''.join([dpath.as_posix(), '/'])

    # Initialize git repo, get file list from last commit
    if not (param['no_rm'] and param['no_add'] and param['no_gc'] and
            param['no_commit']):
        if args['verbose']:
            verbose(starttime, 'initializing git repo:', path_prefix)
        repo = git.Repo.init(path_prefix)
    new_commit_files = []
    if not param['no_rm']:
        if len(repo.heads) == 0:
            last_commit_files = []
        else:
            last_commit_files = [f.name for f in repo.head.commit.tree.blobs]
        if args['verbose']:
            verbose(starttime, 'files in repository:',
                    str(len(last_commit_files)))

    # Determine LDIF input method
    if ldif_from_file:
        fin = open(param['ldif_file'], 'r')
        if args['verbose']:
            verbose(starttime, 'reading ldif from file')
    elif ldif_from_cmd:
        proc = subprocess.Popen(ldif_cmd, stdout=subprocess.PIPE)
        fin = proc.stdout
        if args['verbose']:
            verbose(starttime, 'reading ldif from subprocess')
    else:
        fin = sys.stdin
        if args['verbose']:
            verbose(starttime, 'reading ldif from stdin')

    # Stream from LDIF input and write LDIF output
    entry = ''
    attr = ''
    fname_attr_val = None
    fname_attr_search = ''.join([ldif_attr, ': '])
    if single_ldif:
        # Open LDIF file for writing
        fname = ''.join([param['ldif_name'], '.ldif'])
        fpath = ''.join([path_prefix, fname])
        new_commit_files.append(fname)
        fout = open(fpath, 'w')
        if args['verbose']:
            verbose(starttime, 'single-ldif mode, writing to:', fname)
    else:
        if args['verbose']:
            verbose(starttime, 'multi-ldif mode, writing to:',
                    ''.join(['<', ldif_attr, '>', '.ldif']))
    if args['verbose']:
        verbose(starttime, 'processing ldif...')
    while True:
        line = fin.readline()
        # Exit the loop when finished reading
        if not line:
            break
        # Optional decode bytes from subprocess
        if ldif_from_cmd:
            line = line.decode('utf-8')
        # End of an entry
        if line == '\n':
            if ldif_wrapped:
                # Add last attribute (part)
                entry = ''.join([entry, attr])
            # Write LDIF file
            if single_ldif:
                # Add entry to single LDIF file
                fout.write(''.join([entry, '\n']))
            else:
                # Write entry to new LDIF file
                if fname_attr_val:
                    fname = ''.join([fname_attr_val, '.ldif'])
                    fpath = ''.join([path_prefix, fname])
                    with open(fpath, 'w') as fout:
                        fout.write(''.join([entry, '\n']))
                    new_commit_files.append(fname)
            # Prepare local variables for next entry
            entry = ''
            attr = ''
            fname_attr_val = None
            continue
        # Get the entryUUID
        elif line.startswith(fname_attr_search):
            fname_attr_val = line.split(fname_attr_search, 1)[1].rstrip()
        # Filter out attributes
        if excl_attrs:
            match_excl = rgx_excl.match(line)
            if match_excl:
                continue
        # Append the lines to entry
        if ldif_wrapped:
            if line.startswith(' '):
                attr = ''.join([attr.rstrip(), line[1:]])
            else:
                entry = ''.join([entry, attr])
                attr = line
        else:
            entry = ''.join([entry, line])

    # Close files
    if ldif_from_file:
        fin.close()
    if single_ldif:
        fout.close()

    # Add new LDIF files to index (stage)
    if not param['no_add']:
        if args['verbose']:
            verbose(starttime, 'adding git files:', str(len(new_commit_files)))
        repo.index.add(new_commit_files)

    # Remove unneeded LDIF files from index
    if not param['no_rm']:
        to_remove_files = set(last_commit_files) - set(new_commit_files)
        if args['verbose']:
            verbose(starttime, 'removing git files:', str(len(to_remove_files)))
        if to_remove_files:
            repo.index.remove(to_remove_files, working_tree=True)

    # Commit the changes
    if not param['no_commit']:
        if args['verbose']:
            verbose(starttime, 'commiting git files')
        repo.index.commit(param['commit_msg'])

    # Clean up the repo
    if not param['no_gc']:
        if args['verbose']:
            verbose(starttime, 'triggering git garbage collection')
        repo.git.gc('--auto')

    # Print execution time
    if args['verbose']:
        verbose(starttime, 'exiting...')


if __name__ == "__main__":
    main()
