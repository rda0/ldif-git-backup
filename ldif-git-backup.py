#!/usr/bin/env python3

import os
import sys
import subprocess
import re
import argparse
import pathlib

def main( argv ):
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
    parser.add_argument('-h', '--help',
            action='help',
            help='Show this help message and exit')
    args = parser.parse_args()

    ENTRY_SEP = '\n\n'
    ATTR_WRAP = '\n '

    rgx = re.compile(r'\nentryUUID: ([^\n]+)')
#    ldif_cmd_in = '/usr/sbin/slapcat  -n   1'
    print(args.ldif_cmd)
    ldif_cmd = re.sub('\s+', ' ', args.ldif_cmd).split(' ')
    print(args.backup_dir)
#    abspath = os.path.abspath(args.backup_dir)
#    print(abspath)
    backup_dir = pathlib.PosixPath(args.backup_dir)
    print(backup_dir)
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    sys.exit('stop')
    raw = subprocess.Popen(ldif_cmd,
            stdout=subprocess.PIPE).communicate()[0]
    ldif = raw.decode('utf-8')
    ldif_unwrapped = ldif.replace(ATTR_WRAP, '')
    entries = ldif_unwrapped.split(ENTRY_SEP)
    for entry in entries[:-1]:
        m = rgx.search(entry)
        if m:
            uuid = m.group(1)
            fpath = ''.join([backup_dir, uuid, '.ldif'])
#            fout = open(fpath, 'w')
#            fout.write(''.join([entry, ENTRY_SEP]))
#            fout.close()
        else:
            sys.exit('Error: no entryUUID attribute found!' + 
                    '\n\nEntry:\n\n' + entry)

if __name__== "__main__":
    main(sys.argv)
