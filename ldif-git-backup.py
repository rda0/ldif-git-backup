#!/usr/bin/env python3

import sys
import subprocess
import re
import argparse
import pathlib
import git
import collections
import configparser

def main( argv ):
    # Define default parameter values
    defaults = {
        'ldif_cmd': '/usr/sbin/slapcat -n 1 -o ldif-wrap=no',
        'backup_dir': '/var/backups/ldap',
        'commit_msg': 'ldif-git-backup',
        'no_gc': False,
        'no_rm': False,
        'exclude_attrs': '',
    }

    # Parse cmd-line arguments
    parser = argparse.ArgumentParser(add_help=False,
            description='Backup OpenLDAP databases using Git')
    parser.add_argument('-c', '--ldif-cmd',
            dest='ldif_cmd',
            type=str,
            help='A command which returns an LDAP database in LDIF format '
            'including operational attributes or at least entryUUID')
    parser.add_argument('-d', '--backup-dir',
            dest='backup_dir',
            type=str,
            help='The directory for the git backup repository')
    parser.add_argument('-m', '--commit-msg',
            dest='commit_msg',
            type=str,
            help='The commit message')
    parser.add_argument('--no-gc',
            dest='no_gc',
            action='store_const',
            const=True,
            help='Do not perform a garbage collection')
    parser.add_argument('--no-rm',
            dest='no_rm',
            action='store_const',
            const=True,
            help='Do not perform a git rm')
    parser.add_argument('-e', '--exclude-attrs',
            dest='exclude_attrs',
            type=str,
            help='Exclude all attributes matching the regular expression')
    parser.add_argument('--config-file',
            dest='config_file',
            default='ldif-git-backup.conf',
            type=str,
            help='Path to the config file')
    parser.add_argument('-h', '--help',
            action='help',
            help='Show this help message and exit')
    args = vars(parser.parse_args())
    filtered_args = {k: v for k, v in args.items() if v}

    # Parse configuration file
    parsed_config = configparser.ConfigParser()
    parsed_config.sections()
    parsed_config.read(args['config_file'])
    parsed_config.sections()
    try:
        config = {k: v for k, v in parsed_config['default'].items() if v}
    except KeyError:
        config = {}
    defaults_bool = [k for k, v in defaults.items() if type(v) == bool]
    for k in defaults_bool:
        if k in config:
            if config[k].lower() == 'true':
                config[k] = True
            elif config[k] == 'false':
                config[k] = False
            else:
                del config[k]

    # Create param dict with chained default values
    param = collections.ChainMap(filtered_args, config, defaults)

    # Define constants, compile regular expressions
    ENTRY_SEP = '\n\n'
    ATTR_WRAP = '\n '
    rgx_uuid = re.compile(r'\nentryUUID: ([^\n]+)')
    if param['exclude_attrs']:
        regex = r'\n(' + param['exclude_attrs'] + r'): [^\n]+'
        rgx_excl = re.compile(regex)

    # Clean up ldif command
    ldif_cmd = re.sub('\s+', ' ', param['ldif_cmd']).split(' ')

    # Create backup directory
    dpath = pathlib.PosixPath(param['backup_dir'])
    dpath.mkdir(mode=0o700, parents=True, exist_ok=True)
    dpath = ''.join([dpath.as_posix(), '/'])

    # Initialize git repo, get file list from last commit
    repo = git.Repo.init(dpath)
    if not param['no_rm']:
        if len(repo.heads) == 0:
            last_commit_files = []
        else:
            last_commit_files = [f.name for f in repo.head.commit.tree.blobs]

    # Dump LDAP database to memory
    raw = subprocess.Popen(ldif_cmd,
            stdout=subprocess.PIPE).communicate()[0]
    ldif = raw.decode('utf-8')
    ldif_unwrapped = ldif.replace(ATTR_WRAP, '')
    if param['exclude_attrs']:
        ldif_filtered = rgx_excl.sub('', ldif_unwrapped)
        entries = ldif_filtered.split(ENTRY_SEP)
    else:
        entries = ldif_unwrapped.split(ENTRY_SEP)

    # Write LDIF files
    new_commit_files = []
    for entry in entries[:-1]:
        match_uuid = rgx_uuid.search(entry)
        if not match_uuid:
            sys.exit('Error: no entryUUID attribute found!' +
                    '\n\nEntry:\n\n' + entry)
        uuid = match_uuid.group(1)
        fname = ''.join([uuid, '.ldif'])
        fpath = ''.join([dpath, fname])
        fout = open(fpath, 'w')
        fout.write(''.join([entry, ENTRY_SEP]))
        fout.close()
        new_commit_files.append(fname)

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

if __name__== "__main__":
    main(sys.argv)
