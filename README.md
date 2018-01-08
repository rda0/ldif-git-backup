# ldif-git-backup

Backup LDIF files from LDAP database dumps in a Git repository

Based on [ldap-git-backup](https://github.com/elmar/ldap-git-backup), modified and rewritten in python.

## Requirements

- `python3`
- `python3-git`

## Usage

```
usage: ldif-git-backup.py [-i | -x LDIF_CMD | -l LDIF_FILE] [-d BACKUP_DIR]
                          [-m COMMIT_MSG] [-e EXCL_ATTRS] [-a LDIF_ATTR] [-s]
                          [-n LDIF_NAME] [-c CONFIG] [-f CONFIG_FILE] [-G]
                          [-R] [-A] [-C] [-w] [-v] [-p] [-h]

Backup LDAP databases in LDIF format using Git. The LDIF (Lightweight
Directory Interchange Format) input can be read either from stdin, subprocess
or file. Care must be taken to use the correct parameters, which create the
LDIF input. By default ldif-git-backup will split the LDIF to entries and save
each entry in a file named after the entry's UUID. If these defaults are used,
the LDIF must contain operational attributes or at least the `entryUUID`
attribute.

optional arguments:
  -i, --ldif-stdin      Read LDIF from stdin (default)
  -x LDIF_CMD, --ldif-cmd LDIF_CMD
                        Read LDIF from subprocess
  -l LDIF_FILE, --ldif-file LDIF_FILE
                        Read LDIF from file
  -d BACKUP_DIR, --backup-dir BACKUP_DIR
                        The directory for the git backup repository
                        (default:`/var/backups/ldap`)
  -m COMMIT_MSG, --commit-msg COMMIT_MSG
                        The commit message (default: `ldif-git-backup`)
  -e EXCL_ATTRS, --excl-attrs EXCL_ATTRS
                        Exclude all attributes matching the regular expression
                        `^(EXCLUDE_ATTRS): `
  -a LDIF_ATTR, --ldif-attr LDIF_ATTR
                        The value of attribute LDIF_ATTR will be used as
                        filename. This attribute must be unique in the LDIF.
                        If the attribute is not present in the entry, the
                        whole entry will be silently skipped. This parameter
                        has no effect if combined with `-s`. If the attribute
                        is not unique, bad things will happen, as entries will
                        overwrite eachother. (default: `entryUUID`)
  -s, --single-ldif     Use single LDIF mode, do not split entries to files
  -n LDIF_NAME, --ldif-name LDIF_NAME
                        Use LDIF_NAME as filename in single-ldif mode
                        (default: `db`)
  -c CONFIG, --config CONFIG
                        Use configuration with saection name CONFIG (default:
                        `ldif-git-backup`)
  -f CONFIG_FILE, --config-file CONFIG_FILE
                        Path to the configuration file (default: `./ldif-git-
                        backup.conf`)
  -G, --no-gc           Do not perform garbage collection
  -R, --no-rm           Do not perform git rm
  -A, --no-add          Do not perform git add
  -C, --no-commit       Do not perform git commit
  -w, --ldif-wrap       Set if LDIF input is wrapped, this will unwrap any
                        wrapped attributes. By default the input LDIF is
                        expected to be unwrapped for optimal performance
  -v, --verbose         Enable verbose mode
  -p, --print-params    Print active parameters and exit
  -h, --help            Show this help message and exit
```

## Example usage

### Basic usage

The standard mode will read an LDIF from the given input method and save each entry in a file with the name `<entryUUID>.ldif`.
If these defaults are used, the LDIF must contain operational attributes or at least the `entryUUID` attribute.
The `entryUUID` attribute should be present in all entries in most modern LDAP servers like `slapd` (OpenLDAP).
If no such attribute is present in the entry, it will be silently skipped.
The default method is to read the LDIF from stdin, while it is also possible to read from a subprocess or from a file.
For maximum performance, the LDIF input method `stdin` should be preferred over `subprocess`.

**Important**: The LDIF input is expected to be without linebreaks by default for optimal performance.

Read LDIF from standard input:

```
/usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py
```

Read LDIF from subprocess:

```
./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no'
```

Read LDIF from file:

```
./ldif-git-backup.py -l db_dump.ldif
```

### Advanced usage

Read LDIF from stdin and write files named after custom attribute (`<uid>.ldif`). The attribute has to be unique in the LDIF, otherwise entries might overwrite eachother:

```
/usr/sbin/slapcat -n 1 -o ldif-wrap=no -s ou=people,dc=phys,dc=ethz,dc=ch | ./ldif-git-backup.py -d /var/backups/ldap/users -a uid
```

Backup the `slapd` configuration and store it in a single LDIF named `db.ldif`:

```
/usr/sbin/slapcat -n 0 -o ldif-wrap=no | ./ldif-git-backup.py -s
```

Do the same using LDIF filename `config.ldif`:

```
/usr/sbin/slapcat -n 0 -o ldif-wrap=no | ./ldif-git-backup.py -s -n config
```

Do the same using `ldapsearch`:

```
/usr/bin/ldapsearch -QLLL -Y EXTERNAL -H ldapi:// -o ldif-wrap=no -b cn=config '*' + | ./ldif-git-backup.py -s -n config
```

### Filtering out attributes using regex

For best performance use method `stdin` and `grep`:

```
/usr/sbin/slapcat -n 1 -o ldif-wrap=no | grep -vE '(entry|context)CSN|.*?Timestamp' | ./ldif-git-backup.py
```

Or without `grep`:

```
./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -e '(entry|context)CSN|.*?Timestamp'
```

### Working with wrapped LDIF input

If the LDIF input is wrapped as when not using the `slapcat` or `ldapsearch` parameter `-o ldif-wrap=no` use the option `-w`.
This will unwrap all attributes. Otherwise any attribute filtering will not work as expected and the backup will be useless.

```
/usr/sbin/slapcat -n 1 | ./ldif-git-backup.py -w -e '(enetry|context)CSN|.*?Timestamp'
```

### Using the configuration file

By default the configuration file `./ldif-git-backup.conf` is read and parsed if present.
To specify a configuration from another location use:

```
./ldif-git-backup.py -f path/to/config.conf
```

The special configuration section named `DEFAULT` can be used to set the default options for all other named configuration sections if they do not explicitly specify a configuration option. The special configuration section named `ldif-git-backup` can be used to specify the default paramters for `ldif-git-backup.py` if not specified as command-line arguments. Any command-line arguments take precedence over configuration options.
Any other configuration section names can be used to specify sets of configurations to be used with the option `-c <section_name>`.

The example configuration [ldif-git-backup.conf](ldif-git-backup.conf) contains some example named configuration sections and explanations.
ldif-git-backup uses the `configparser` paython module with extended interpolation enabled. See [python docs](https://docs.python.org/3/library/configparser.html) for more details on how to use this syntax.
To use the example named configurations, use the following parameters.

To backup the `slapd` configuration using `slapcat` subprocess:

```
./ldif-git-backup.py -c config_slapcat
```

To backup the `slapd` configuration using `ldapsearch` subprocess:

```
./ldif-git-backup.py -c config_ldapsearch
```
