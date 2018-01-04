#!/usr/bin/env python3

import sys
import subprocess
import re
import argparse
import pathlib
import git

def main( argv ):
    # Parse cmd-line arguments
    parser = argparse.ArgumentParser(add_help=False,
            description='Backup OpenLDAP databases using Git')
    parser.add_argument('-c', '--ldif-cmd',
            dest='ldif_cmd',
            type=str,
            default='/usr/sbin/slapcat -n 1 -o ldif-wrap=no',
            help='A command which returns an LDAP database in LDIF format '
            'including operational attributes or at least entryUUID')
    parser.add_argument('-d', '--backup-dir',
            dest='backup_dir',
            type=str,
            default='/var/backups/ldap',
            help='The directory for the git backup repository')
    parser.add_argument('-m', '--commit-msg',
            dest='commit_msg',
            type=str,
            default='ldap-git-backup',
            help='The commit message')
    parser.add_argument('--no-gc',
            dest='no_gc',
            action='store_true',
            help='Do not perform a garbage collection')
#    parser.add_argument('-e', '--exclude-attrs',
#            dest='exclude_attrs',
#            type=str,
#            help='Exclude all attributes matching the regular expression')
    parser.add_argument('-h', '--help',
            action='help',
            help='Show this help message and exit')
    args = parser.parse_args()

    # Define constants, compile regular expressions
    ENTRY_SEP = '\n\n'
    ATTR_WRAP = '\n '
    rgx_uuid = re.compile(r'\nentryUUID: ([^\n]+)')
#    if args.exclude_attrs:
#        rgx_excl = re.compile(r'\n' + args.exclude_attrs + r': [^\n]+')

    # Clean up ldif command
    ldif_cmd = re.sub('\s+', ' ', args.ldif_cmd).split(' ')

    # Create backup directory
    dpath = pathlib.PosixPath(args.backup_dir)
    dpath.mkdir(mode=0o700, parents=True, exist_ok=True)
    dpath = ''.join([dpath.as_posix(), '/'])

    # Initialize git repo, get file list from last commit
    repo = git.Repo.init(dpath)
    if len(repo.heads) == 0:
        last_commit_files = []
    else:
        last_commit_files = [f.name for f in repo.head.commit.tree.blobs]

    # Dump LDAP database to memory
    raw = subprocess.Popen(ldif_cmd,
            stdout=subprocess.PIPE).communicate()[0]
    ldif = raw.decode('utf-8')
    ldif_unwrapped = ldif.replace(ATTR_WRAP, '')
#    if args.exclude_attrs:
#        ldif_filtered = rgx_excl.sub('', ldif_unwrapped)
#        entries = ldif_filtered.split(ENTRY_SEP)
#    else:
#        entries = ldif_unwrapped.split(ENTRY_SEP)
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
    to_remove_files = set(last_commit_files) - set(new_commit_files)
    if to_remove_files:
        repo.index.remove(to_remove_files, working_tree=True)

    # Commit the changes
    repo.index.commit(args.commit_msg)

    # Clean up the repo
    if not args.no_gc:
        repo.git.gc('--auto')

if __name__== "__main__":
    main(sys.argv)
