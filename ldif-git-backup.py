#!/usr/bin/env python3

#import os
import subprocess
import re
#import yaml
#import argparse

def main():
    ENTRY_SEP = '\n\n'
    ATTR_WRAP = '\n '
    rgx = re.compile(r'\nentryUUID: ([^\n]+)')
#    rgx = re.compile(r'\nentryUUID: (?P<uuid>[^\n]+)')
#    rgx = re.compile(
#            r'^dn:{1,2} (?P<dn>[^\n]+).*?'
#            r'\nentryUUID: (?P<uuid>[^\n]+)',
#            re.DOTALL)
    slapcat_cmd = '/usr/sbin/slapcat -n 1'
    backup_dir = '/tmp/lgb/py/'
    raw = subprocess.Popen(['/usr/sbin/slapcat', '-n', '1'],
            stdout=subprocess.PIPE).communicate()[0]
    ldif = raw.decode('utf-8')
    ldif_unwrapped = ldif.replace(ATTR_WRAP, '')
    entries = ldif_unwrapped.split(ENTRY_SEP)
    for entry in entries[:-1]:
        if entry == '':
            print('is empty')
            continue
#    for entry in entries[:10]:
#        dn = entry.split('\n', 1)[0].split(': ', 1)[1]
#        uuid = entry.split('\nentryUUID: ', 1)[1].split('\n', 1)[0]
        m = rgx.search(entry)
        uuid = None
        if m:
            uuid = m.group(1)
#             uuid = m.group('uuid')
#             dn = m.group('dn')
#             print(uuid, dn)
        fpath = ''.join([backup_dir, uuid, '.ldif'])
#        fout = open(fpath, 'w')
#        fout.write(''.join([entry, ENTRY_SEP]))
#        fout.close()
#    with open(backup_dir + 'db.yaml', 'w') as yaml_file:
#        yaml.dump(dit.get_entry_map(), yaml_file, default_flow_style=False)

if __name__== "__main__":
    main()
