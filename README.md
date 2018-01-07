# ldif-git-backup

Backup LDIF files from LDAP database dumps in a Git repository

Based on [ldap-git-backup](https://github.com/elmar/ldap-git-backup), modified and rewritten in python.

## Requirements

- `python3`
- `python3-git`

## Usage

```
usage: ldif-git-backup.py [-x LDIF_CMD | -l LDIF_FILE | -i] [-d BACKUP_DIR]
                          [-m COMMIT_MSG] [-e EXCL_ATTRS] [-a LDIF_ATTR]
                          [-c CONFIG] [-f CONFIG_FILE] [-G] [-R] [-A] [-C]
                          [-s] [-n LDIF_NAME] [-w] [-v] [-p] [-h]

Backup LDAP databases in LDIF format using Git. The LDIF (Lightweight
Directory Interchange Format) input can be read either from stdin, subprocess
or file. Care must be taken to use the correct parameters, which create the
LDIF input. By default ldif-git-backup will split the LDIF to entries and save
each entry in a file named after the entry's UUID. If these defaults are used,
the LDIF must contain operational attributes or at least `entryUUID`.

optional arguments:
  -x LDIF_CMD, --ldif-cmd LDIF_CMD
                        Read LDIF from subprocess
  -l LDIF_FILE, --ldif-file LDIF_FILE
                        Read LDIF from file
  -i, --ldif-stdin      Read LDIF from stdin (default)
  -d BACKUP_DIR, --backup-dir BACKUP_DIR
                        The directory for the git backup repository
  -m COMMIT_MSG, --commit-msg COMMIT_MSG
                        The commit message
  -e EXCL_ATTRS, --excl-attrs EXCL_ATTRS
                        Exclude all attributes matching the regular expression
  -a LDIF_ATTR, --ldif-attr LDIF_ATTR
                        Attribute to use as filename. The value of this
                        attribute will be used as filename. Attribute must be
                        present in all entries and must be unique in the LDIF.
                        This parameter has no effect if combined with `-s`. If
                        the attribute is not present in the entry, the whole
                        entry will be silently skipped. If the attribute is
                        not unique, bad things could happen as entries will
                        overwrite eachother. Default: `entryUUID` (always
                        unique)
  -c CONFIG, --config CONFIG
                        Use configuration named CONFIG (section name)
  -f CONFIG_FILE, --config-file CONFIG_FILE
                        Path to the configuration file
  -G, --no-gc           Do not perform garbage collection
  -R, --no-rm           Do not perform git rm
  -A, --no-add          Do not perform git add
  -C, --no-commit       Do not perform git commit
  -s, --single-ldif     Store in single LDIF, do not split to files
  -n LDIF_NAME, --ldif-name LDIF_NAME
                        Filename to use in single-ldif mode (default: db)
  -w, --ldif-wrap       Set if LDIF input is wrapped, this will unwrap any
                        wrapped attributes. By default the input LDIF is
                        expected to be unwrapped for optimal performance
  -v, --verbose         enable verbose mode
  -p, --print-params    print parameters and exit
  -h, --help            Show this help message and exit
```
