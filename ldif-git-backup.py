#!/usr/bin/env python3

import sys
import subprocess
import re
import argparse
import pathlib
import git
import collections
import configparser
import time

def main(argv):
    starttime = time.perf_counter()

    # Define default parameter values
    defaults = {
        'ldif_cmd': '',
        'ldif_file': '',
        'ldif_stdin': False,
        'backup_dir': '/var/backups/ldap',
        'commit_msg': 'ldif-git-backup',
        'excl_attrs': '',
        'no_gc': False,
        'no_rm': False,
        'single_ldif': False,
        'ldif_name': 'db',
        'ldif_wrap': False,
    }

    # Parse cmd-line arguments
    parser = argparse.ArgumentParser(add_help=False,
            description='Backup OpenLDAP databases using Git')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-x', '--ldif-cmd',
            dest='ldif_cmd',
            type=str,
            help='A command which returns an LDAP database in LDIF format '
            'including operational attributes or at least entryUUID')
    group.add_argument('-l', '--ldif-file',
            dest='ldif_file',
            type=str,
            help='Read LDIF from file')
    group.add_argument('-i', '--ldif-stdin',
            dest='stdin',
            action='store_const',
            const=True,
            help='Read LDIF from stdin (default)')
    parser.add_argument('-d', '--backup-dir',
            dest='backup_dir',
            type=str,
            help='The directory for the git backup repository')
    parser.add_argument('-m', '--commit-msg',
            dest='commit_msg',
            type=str,
            help='The commit message')
    parser.add_argument('-e', '--excl-attrs',
            dest='excl_attrs',
            type=str,
            help='Exclude all attributes matching the regular expression')
    parser.add_argument('-c', '--config',
            dest='config',
#            default='default',
            type=str,
            help='Use configuration named CONFIG (section name)')
    parser.add_argument('-f', '--config-file',
            dest='config_file',
            type=str,
            help='Path to the configuration file')
    parser.add_argument('-G', '--no-gc',
            dest='no_gc',
            action='store_const',
            const=True,
            help='Do not perform garbage collection')
    parser.add_argument('-R', '--no-rm',
            dest='no_rm',
            action='store_const',
            const=True,
            help='Do not perform git rm')
    parser.add_argument('-s', '--single-ldif',
            dest='single_ldif',
            action='store_const',
            const=True,
            help='Store in single LDIF, do not split to files')
    parser.add_argument('-n', '--ldif-name',
            dest='ldif_name',
            type=str,
            help='Filename to use in single-ldif mode (default: db)')
    parser.add_argument('-w', '--ldif-wrap',
            dest='ldif_wrap',
            action='store_const',
            const=True,
            help='Set if LDIF input is wrapped, this will unwrap any wrapped '
            'attributes. By default the input LDIF is expected to be unwrapped '
            'for optimal performance')
    parser.add_argument('-h', '--help',
            action='help',
            help='Show this help message and exit')
    args = vars(parser.parse_args())
    filtered_args = {k: v for k, v in args.items() if v}

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
            print('section', args['config'])
        else:
            sys.exit('Error: no config section named %s' % args['config'])
    elif cparser.has_section('ldif-git-backup'):
        config_params = cparser['ldif-git-backup'].items()
        print('section', 'ldif-git-backup')
    else:
        config_params = None
        print('no config')
    if config_params:
        config = {k: v for k, v in config_params if v}
    else:
        config = {}
    defaults_bool = [k for k, v in defaults.items() if type(v) == bool]
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

    for k, v in param.items():
        print(k + ':', v)
#    sys.exit('stop')

    # Define flags, compile regular expressions
    ldif_from_cmd = False
    ldif_from_file = False
    ldif_wrapped = False
    excl_attrs = False
    single_ldif = False
    if not param['ldif_stdin']:
        if not param['ldif_cmd']:
            if param['ldif_file']:
                ldif_from_file = True
        elif param['ldif_cmd']:
            ldif_from_cmd = True
    if param['ldif_wrap']:
        ldif_wrapped = True
    rgx_uuid = re.compile(r'\nentryUUID: ([^\n]+)')
    if param['excl_attrs']:
        regex = r'(' + param['excl_attrs'] + r'): '
        rgx_excl = re.compile(regex)
        excl_attrs = True
    if param['single_ldif']:
        single_ldif = True

    # Clean up ldif command
    ldif_cmd = re.sub('\s+', ' ', param['ldif_cmd']).split(' ')
    print('clean_ldif_cmd', ldif_cmd)

    # Create backup directory
    dpath = pathlib.PosixPath(param['backup_dir'])
    dpath.mkdir(mode=0o700, parents=True, exist_ok=True)
    dpath = ''.join([dpath.as_posix(), '/'])

    # Initialize git repo, get file list from last commit
    repo = git.Repo.init(dpath)
    new_commit_files = []
    if not param['no_rm']:
        if len(repo.heads) == 0:
            last_commit_files = []
        else:
            last_commit_files = [f.name for f in repo.head.commit.tree.blobs]

    # Determine LDIF input method
    if ldif_from_file:
        fin = open(param['ldif_file'], 'r')
    elif ldif_from_cmd:
        p = subprocess.Popen(ldif_cmd, stdout=subprocess.PIPE)
        fin = p.stdout
    else:
        fin = sys.stdin

    # Stream from LDIF input and write LDIF output
    if single_ldif:
        # Open LDIF file for writing
        fname = ''.join([param['ldif_name'], '.ldif'])
        fpath = ''.join([dpath, fname])
        new_commit_files.append(fname)
        fout = open(fpath, 'w')
    entry = ''
    attr = ''
    uuid = None
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
                entry = ''.join([entry, attr])
            # Write LDIF file
            if not single_ldif:
                if not uuid:
                    sys.exit('Error: no entryUUID attribute found!' +
                        '\n\nEntry:\n\n' + entry)
                fname = ''.join([uuid, '.ldif'])
                fpath = ''.join([dpath, fname])
                with open(fpath, 'w') as fout:
                    fout.write(''.join([entry, '\n']))
                new_commit_files.append(fname)
            else:
                fout.write(''.join([entry, '\n']))
            # Prepare local variables for next entry
            entry = ''
            attr = ''
            uuid = None
            continue
        # Get the entryUUID
        elif line.startswith('entryUUID: '):
            uuid = line.split('entryUUID: ', 1)[1].rstrip()
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
                attr = ''
                attr = ''.join([attr, line])
        else:
            entry = ''.join([entry, line])

    # Close files
    if ldif_from_file:
        fin.close()
    if single_ldif:
        fout.close()

    # Add new LDIF files to index (stage)
    repo.index.add(new_commit_files)

    # Remove unneeded LDIF files from index
    if not param['no_rm']:
        to_remove_files = set(last_commit_files) - set(new_commit_files)
        if to_remove_files:
            repo.index.remove(to_remove_files, working_tree=True)

    # Commit the changes
    repo.index.commit(param['commit_msg'])

    # Clean up the repo
    if not param['no_gc']:
        repo.git.gc('--auto')

    # Measure execution time
    endtime = time.perf_counter()
    runtime = endtime - starttime
    print('runtime:', str(runtime), 's')

if __name__== "__main__":
    main(sys.argv)
