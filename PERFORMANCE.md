# performance ldif-git-backup vs ldap-git-backup

first backup with empty dir (second backup over first backup):

test | ldap-git-backup (elmar) | ldap-git-backup (rda) | ldif-git-backup       | ldif-git-backup (pipe)
---- | ----------------------- | --------------------- | --------------------- | ---------------------
1    | 0m16.305s (0m23.834s)   | 0m16.376s (0m24.470s) | 0m11.783s (0m16.893s) | 0m11.529s (0m15.174s)
2    | -                       | 0m17.229s (0m25.345s) | 0m11.899s (0m16.461s) | 0m11.103s (0m15.335s)
3    | 0m20.875s (0m24.081s)   |                       | 0m11.804s (0m13.875s) |
4    | fail (arg list size)    | 6m8.384s (14m12.746s) | 1m2.369s (1m22.545s)  | 1m2.007s (1m21.285s)
5    | 0m54.848s (2m5.205s)    | 0m54.199s (1m56.029s) | 0m23.435s (0m31.959s) | 0m25.484s (0m31.572s)
6    | fail (arg list size)    | 3m45.994s (8m53.478s) | 0m50.280s (1m5.503s) | 0m50.248s (1m4.494s)
7    |  |  |  |

## using dphys example data

- typical ldap data
- 23478 entries
- 670661 lines
- 24576694 characters

first backup is respectively performed using empty directory

### test 1

ldap-git-backup v.1.0.8 (https://github.com/elmar/ldap-git-backup)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 0m16.305s
user 0m13.176s
sys  0m3.444s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 0m23.834s
user 0m21.000s
sys  0m3.096s
```

ldap-git-backup fixed d3d4bb2ab73241b2c3a0b1d8b04e552304a326c0 (https://github.com/rda0/ldap-git-backup/)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 0m16.376s
user 0m13.136s
sys  0m3.432s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 0m24.470s
user 0m21.488s
sys  0m3.256s
```

ldif-git-backup subprocess

```
time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 0m11.783s
user 0m8.172s
sys  0m3.628s

time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 0m16.893s
user 0m9.228s
sys  0m6.708s
```

ldif-git-backup pipe

```
time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 0m11.529s
user 0m8.328s
sys  0m3.460s

time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 0m15.174s
user 0m9.232s
sys  0m6.060s
```

### test 2

- using dphys example data with regex filter

ldap-git-backup 47a204f2ef6f152e78317c98ca2918bcf08a8a5d (https://github.com/rda0/ldap-git-backup/)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc --exclude-attrs 'lastUse.*?|krb.*?|(entry|context)CSN|modifiersName|modifyTimestamp|creatorsName|createTimestamp'

real 0m17.229s
user 0m13.984s
sys  0m3.604s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc --exclude-attrs 'lastUse.*?|krb.*?|(entry|context)CSN|modifiersName|modifyTimestamp|creatorsName|createTimestamp'

real 0m25.345s
user 0m22.384s
sys  0m3.224s
```

ldif-git-backup subprocess

```
time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G -e 'lastUse.*?|krb.*?|(entry|context)CSN|modifiersName|modifyTimestamp|creatorsName|createTimestamp'

real 0m11.899s
user 0m8.768s
sys  0m3.424s

time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G -e 'lastUse.*?|krb.*?|(entry|context)CSN|modifiersName|modifyTimestamp|creatorsName|createTimestamp'

real 0m16.461s
user 0m9.736s
sys  0m6.884s
```

ldif-git-backup pipe

```
time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | grep -vE '^(lastUse.*?|krb.*?|(entry|context)CSN|modifiersName|modifyTimestamp|creatorsName|createTimestamp): ' | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 0m11.103s
user 0m9.188s
sys  0m3.460s

time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | grep -vE '^(lastUse.*?|krb.*?|(entry|context)CSN|modifiersName|modifyTimestamp|creatorsName|createTimestamp): ' | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 0m15.335s
user 0m10.316s
sys  0m6.668s
```

### test 3

- standard mode with `git gc` (ldap-git-backup) vs `git gc --auto` (ldif-git-backup)

ldap-git-backup v.1.0.8 (https://github.com/elmar/ldap-git-backup)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl

real 0m20.875s
user 0m17.344s
sys  0m6.192s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl

real 0m24.081s
user 0m21.180s
sys  0m3.096s
```

ldif-git-backup

```
time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py

real 0m11.804s
user 0m8.412s
sys  0m3.676s

time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py

real 0m13.875s
user 0m9.208s
sys  0m4.932s
```

### test 4

- using a lot more (tiny) entries
- 123488 entries
- 1770794 lines
- 67659231 characters

ldap-git-backup fixed d3d4bb2ab73241b2c3a0b1d8b04e552304a326c0 (rda0)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 6m8.384s
user 5m50.620s
sys  0m18.080s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 14m12.746s
user 13m57.172s
sys  0m16.024s
```

ldif-git-backup subprocess

```
time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 1m2.369s
user 0m38.676s
sys  0m18.620s

time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 1m22.545s
user 0m45.372s
sys  0m34.688s
```

ldif-git-backup pipe

```
time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real    1m2.007s
user    0m38.560s
sys 0m18.160s

time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real    1m21.285s
user    0m43.596s
sys 0m35.064s
```

### test 5

- using dphys data * 2
- 46956 entries
- 1341319 lines
- 50005297 chars

ldap-git-backup v.1.0.8 (elmar)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 0m54.848s
user 0m48.476s
sys  0m6.996s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 2m5.205s
user 1m58.984s
sys  0m6.544s
```

ldap-git-backup fixed d3d4bb2ab73241b2c3a0b1d8b04e552304a326c0 (rda0)

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 0m54.199s
user 0m47.576s
sys  0m7.080s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 1m56.029s
user 1m49.832s
sys  0m6.436s
```

ldif-git-backup subproc

```
time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 0m23.435s
user 0m16.612s
sys  0m7.120s

time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 0m31.959s
user 0m18.584s
sys  0m13.532s
```

ldif-git-backup pipe

```
time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G
real 0m25.484s
user 0m16.244s
sys  0m7.172s

time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 0m31.572s
user 0m18.060s
sys  0m13.264s
```

test 6

- using dphys data * 4
- 93912 entries
- 2682635 lines
- 100862607 chars

ldap-git-backup elmar

```
fail
```

ldap-git-backup rda

```
time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 3m45.994s
user 3m29.476s
sys  0m14.268s

time ./ldap-git-backup.pl --ldif-cmd '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' --backup-dir /tmp/lgb/perf/pl --no-gc

real 8m53.478s
user 8m41.148s
sys  0m12.828s
```

ldif-git-backup subproc

```
time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 0m50.280s
user 0m32.632s
sys  0m14.592s

time ./ldif-git-backup.py -x '/usr/sbin/slapcat -n 1 -o ldif-wrap=no' -d /tmp/lgb/perf/py -G

real 1m5.503s
user 0m37.608s
sys  0m27.144s
```

ldif-git-backup pipe

```
time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 0m50.248s
user 0m32.756s
sys  0m14.456s

time /usr/sbin/slapcat -n 1 -o ldif-wrap=no | ./ldif-git-backup.py -d /tmp/lgb/perf/py -G

real 1m4.494s
user 0m36.620s
sys  0m26.832s
```

test 7

- using dphys data * 10
- 258258 entries
- 7377241 lines
- 278863192 chars

ldap-git-backup rda

```

```

ldif-git-backup subprocess

```

```

ldif-git-backup pipe

```

```
