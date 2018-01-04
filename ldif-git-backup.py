#!/usr/bin/env python3

#import os
#import sys
import subprocess
import re
import yaml
#import argparse

class Ldif(object):
    '''Holds LDAP data in LDIF format.'''

    ENTRY_SEPARATOR = '\n\n'

    def __init__(self, raw=''):
        raw_unwrapped = raw.replace('\n ', '')
        self.raw = raw_unwrapped.rstrip()

    def __str__(self):
        return '%s\n\n' % self.raw

    def get_raw_entries(self):
        return self.raw.split(Ldif.ENTRY_SEPARATOR)

    def get_entries(self):
        entries = []
        for raw_entry in self.get_raw_entries():
            entries.append(Entry(raw_entry))
        return entries

class Entry(object):
    '''Represents an entry in the DIT'''

    def __init__(self, raw):
        self.raw = raw

    def __str__(self):
        return '%s\n\n' % self.raw

    def dn(self):
        return self.raw.split('\n', 1)[0].split(': ', 1)[1]

    def uuid(self):
        m = re.search('[\n]entryUUID: ([^\n]+)', self.raw)
        if m:
            return m.group(1)
        else:
            return None

    def ldif(self):
        return self.raw + '\n\n'

class Dit(object):
    '''Represents a DIT'''

    def __init__(self, entries):
        self.entries = entries

    def get_entry_map(self):
        entry_map = {}
        for entry in self.entries:
            entry_map[entry.uuid()] = entry.dn()
        return entry_map

def main():
    slapcat_cmd = '/usr/sbin/slapcat -n 1'
    backup_dir = '/tmp/lgb/py/'
    slapcat_out = subprocess.getoutput(slapcat_cmd)
    ldif = Ldif(slapcat_out)
    dit = Dit(ldif.get_entries())
    for entry in dit.entries:
        fpath = backup_dir + entry.uuid() + '.ldif'
        fout = open(fpath, 'w')
        fout.write(entry.ldif())
        fout.close()
#    with open(backup_dir + 'db.yaml', 'w') as yaml_file:
#        yaml.dump(dit.get_entry_map(), yaml_file, default_flow_style=False)

if __name__== "__main__":
    main()
