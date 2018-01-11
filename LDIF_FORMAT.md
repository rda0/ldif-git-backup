# LDIF format specification (for directory entries)

This file only lists the specifcation of an LDIF file which specifies a set of directory entries.  
The LDIF file format is specifed in [RFC 2849](https://tools.ietf.org/html/rfc2849).

The following definition uses the augmented Backus-Naur Form specified in [RFC 2234](https://tools.ietf.org/html/rfc2234).

## Syntax subset needed py parser in `ldif-git-backup`

```
# version spec

ldif-file                = ldif-content
ldif-content             = version-spec 1*(1*SEP ldif-attrval-record)
version-spec             = "version:" FILL version-number
version-number           = "1"

# entry spec

ldif-attrval-record      = dn-spec SEP 1*attrval-spec
dn-spec                  = "dn:" VALUE
attrval-spec             = attrname value-spec SEP
value-spec               = ":" VALUE
```

Tthis leads to:

```
version-spec 1*(1*SEP ("dn:" VALUE) SEP 1*(attrname ":" VALUE SEP)))
```

To support LDIFv1 without the `version-spec`, this leads to:

```
0*1(version-spec 1*SEP)
"dn:" VALUE SEP 1*(attrname ":" VALUE SEP)
*(1*SEP ("dn:" VALUE) SEP 1*(attrname ":" VALUE SEP)))
```

As we do not need `dn-spec`, the `dn` line can be interpreted as `attrval-spec`
and the simplified result leads to:

```
0*1(version-spec 1*SEP)
1*(attrname ":" VALUE SEP)
*(1*SEP 1*(attrname ":" VALUE SEP)))
```

The `entries` will be parsed as follows:

```
entries = entry *(1*SEP entry)
entry   = 1*(attrname ":" VALUE SEP)
```

## Formal Syntax Definition (subset to parse `ldif-attrval-record`s)


```
ldif-file                = ldif-content / ldif-changes

ldif-content             = version-spec 1*(1*SEP ldif-attrval-record)

ldif-attrval-record      = dn-spec SEP 1*attrval-spec

version-spec             = "version:" FILL version-number

version-number           = 1*DIGIT
                           ; version-number MUST be "1" for the
                           ; LDIF format described in this document.

dn-spec                  = "dn:" (FILL distinguishedName /
                                  ":" FILL base64-distinguishedName)

attrval-spec             = AttributeDescription value-spec SEP

value-spec               = ":" (    FILL 0*1(SAFE-STRING) /
                                ":" FILL (BASE64-STRING) /
                                "<" FILL url)
                           ; See notes 7 and 8, below

url                      = <a Uniform Resource Locator,
                            as defined in [6]>
                                   ; (See Note 6, below)

AttributeDescription     = AttributeType [";" options]
                           ; Definition taken from [4]

AttributeType            = ldap-oid / (ALPHA *(attr-type-chars))

options                  = option / (option ";" options)

option                   = 1*opt-char

attr-type-chars          = ALPHA / DIGIT / "-"

opt-char                 = attr-type-chars

SPACE                    = %x20
                           ; ASCII SP, space

FILL                     = *SPACE

SEP                      = (CR LF / LF)

CR                       = %x0D
                           ; ASCII CR, carriage return

LF                       = %x0A
                           ; ASCII LF, line feed

ALPHA                    = %x41-5A / %x61-7A
                           ; A-Z / a-z

DIGIT                    = %x30-39
                           ; 0-9

```

## Notes on LDIF Syntax

1)  For the LDIF format described in this document, the version
    number MUST be `1`. If the version number is absent,
    implementations MAY choose to interpret the contents as an
    older LDIF file format, supported by the University of
    Michigan ldap-3.3 implementation.

2)  Any non-empty line, including comment lines, in an LDIF file
    MAY be folded by inserting a line separator (`SEP`) and a `SPACE`.
    Folding MUST NOT occur before the first character of the line.
    In other words, folding a line into two lines, the first of
    which is empty, is not permitted. Any line that begins with a
    single space MUST be treated as a continuation of the previous
    (non-empty) line. When joining folded lines, exactly one space
    character at the beginning of each continued line must be
    discarded. Implementations SHOULD NOT fold lines in the middle
    of a multi-byte UTF-8 character.

3)  Any line that begins with a pound-sign (`#`, ASCII 35) is a
    comment line, and MUST be ignored when parsing an LDIF file.
