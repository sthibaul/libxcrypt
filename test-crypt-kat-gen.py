#! /usr/bin/python3
# Compute test cases for test-crypt-kat.
#
# Written by Zack Weinberg <zackw at panix.com> in 2019.
# To the extent possible under law, Zack Weinberg has waived all
# copyright and related or neighboring rights to this work.
#
# See https://creativecommons.org/publicdomain/zero/1.0/ for further
# details.

# This program generates test-crypt-kat.inc, which defines the set
# of tests performed by test-crypt-kat.c.  It is not run automatically
# during the build for two reasons: it's very slow, and it requires Python
# 3.6 or greater with Passlib <https://passlib.readthedocs.io/en/stable/>
# available.
#
# If you modify this program, make sure to update test-crypt-kat.inc,
# by running 'make regen-test-crypt-kat' (libcrypt.so must already
# have been built), and then check in the updates to that file in the
# same commit as your changes to this program.  You will need to
# install Passlib itself, but not any other libraries.  (This program
# intentionally uses Passlib's slow pure-Python back ends, rather than
# accelerated C modules that tend to be, at their core, the same code
# libxcrypt uses itself, so that we really are testing libxcrypt
# against known answers generated with a different implementation.)

import ctypes
import multiprocessing
import os
import re
import sys

# force passlib to allow use of its built-in bcrypt implementation
import os
os.environ["PASSLIB_BUILTIN_BCRYPT"] = "enabled"

import passlib.hash

# In order to tickle various bugs and limitations in older hashing
# methods precisely, we need to test several passphrases whose byte
# sequences are not valid Unicode text in any encoding.  We therefore
# use exclusively byte strings in this array.
PHRASES = [
    # All ASCII printable, various lengths.  Most of these were taken
    # from older known-answer tests for specific hashing methods.
    b'',
    b' ',
    b'a',
    b'ab',
    b'abc',
    b'U*U',
    b'U*U*',
    b'U*U*U',
    b'.....',
    b'dragon',
    b'dRaGoN',
    b'DrAgOn',
    b'PAROLX',
    b'U*U***U',
    b'abcdefg',
    b'01234567',
    b'726 even',
    b'zyxwvuts',
    b'ab1234567',
    b'alexander',
    b'beautiful',
    b'challenge',
    b'chocolate',
    b'cr1234567',
    b'katherine',
    b'stephanie',
    b'sunflower',
    b'basketball',
    b'porsche911',
    b'|_337T`/p3',
    b'thunderbird',
    b'Hello world!',
    b'pleaseletmein',
    b'a short string',
    b'zxyDPWgydbQjgq',
    b'photojournalism',
    b'ecclesiastically',
    b'congregationalism',
    b'dihydrosphingosine',
    b'semianthropological',
    b'palaeogeographically',
    b'electromyographically',
    b'noninterchangeableness',
    b'abcdefghijklmnopqrstuvwxyz',
    b'electroencephalographically',
    b'antidisestablishmentarianism',
    b'cyclotrimethylenetrinitramine',
    b'dichlorodiphenyltrichloroethane',
    b'multiple words seperated by spaces',
    b'supercalifragilisticexpialidocious',
    b'we have a short salt string but not a short password',
    b'multiple word$ $eperated by $pace$ and $pecial character$',
    b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
    (b'1234567890123456789012345678901234567890'
     b'1234567890123456789012345678901234567890'),
    (b'a very much longer text to encrypt.  This one even stretches over more'
     b'than one line.'),

    # ASCII printables with their high bits flipped - DES-based hashes collide.
    # All of these have an exact counterpart above.
    b'\xd0\xc1\xd2\xcf\xcc\xd8',              # 'PAROLX'
    b'\xd5\xaa\xd5\xaa\xaa\xaa\xd5\xaa',      # 'U*U***U*'
    b'\xe1\xec\xe5\xf8\xe1\xee\xe4\xe5\xf2',  # 'alexander'
    b'\xf3\xf4\xe5\xf0\xe8\xe1\xee\xe9\xe5',  # 'stephanie'
    # '*U*U*U*U*U*U*U*U*'
    b'\xaa\xd5\xaa\xd5\xaa\xd5\xaa\xd5\xaa\xd5\xaa\xd5\xaa\xd5\xaa\xd5\xaa',

    # A few UTF-8 strings and what they will collide with for
    # DES-based hashes.
    b'\xC3\xA9tude', b'C)tude', # UTF-8(NFC(étude))
    b'Chl\xC3\xB6e', b'ChlC6e', # UTF-8(NFC(Chlöe))
    # Eight letters, but 10 bytes: UTF-8(NFC(Ångström))
    b'\xC3\x85ngstr\xC3\xB6m', b'C\x05ngstrC6m', b'C\x05ngstrC'

    # descrypt truncates everything to 8 characters.
    b'U*U***U*', b'U*U***U*ignored',
    b'U*U*U*U*', b'U*U*U*U*ignored',
    b'*U*U*U*U', b'*U*U*U*U*', b'*U*U*U*U*U*U*U*U', b'*U*U*U*U*U*U*U*U*',

    # Patterns designed to tickle the bcrypt $2x$ sign-extension bug.
    b'\xa3',
    b'\xa3a',
    b'\xd1\x91',
    b'\xa3ab',
    b'\xff\xff\xa3',
    b'1\xa3345',
    b'\xff\xa3345',
    b'\xff\xa334\xff\xff\xff\xa3345',

    (b'\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff'
     b'\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff'
     b'\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff'
     b'\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff'
     b'\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff'
     b'\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff\x55\xaa\xff'),

    (b'\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55'
     b'\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55'
     b'\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55'
     b'\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55'
     b'\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55'
     b'\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55'),

    # bcrypt truncates to 72 characters
    (b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
     b'0123456789'),
    (b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
     b'0123456789chars after 72 are ignored'),

    (b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'),

    (b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa'
     b'chars after 72 are ignored as usual'),

    # bigcrypt truncates to 128 characters
    # (first sentence of _Twenty Thousand Leagues Under The Sea_)
    (b'THE YEAR 1866 was marked by a bizarre development, an unexplained and '
     b'downright inexplicable phenomenon that surely no one has forgotten.'),

    # first 8 characters of above (des)
    b'THE YEAR',
    # first 72 characters (bcrypt)
    b'THE YEAR 1866 was marked by a bizarre development, an unexplained and do',
    # first 128 characters (bigcrypt)
    (b'THE YEAR 1866 was marked by a bizarre development, an unexplained and '
     b'downright inexplicable phenomenon that surely no one has f')
]

# passlib does not support all of the hashing methods we do, no longer
# supports generation of bare setting strings, and in some cases does
# not support all of the variants we need to generate.  Therefore,
# there is a shim for each hashing method (variant).  Shims must be
# named 'h_METHOD' where METHOD is the name for the method used by the
# INCLUDE_method macros.
#
# Each shim function takes at least the arguments phrase, rounds, and
# salt, in that order.  Additional optional arguments are allowed.  It
# should do 'yield format_case(phrase, setting, expected)' at least
# once, where phrase is the phrase argument, setting is a setting
# string generated from rounds and salt, and expected is the hashed
# passphrase expected to be generated from that combination of phrase
# and setting.  format_case is defined far below.
#
# When implementing new shims, use of passlib's pure-Python "backends"
# is strongly preferred where possible, because the speed of this
# program does not matter, and the C backends tend to be based on some
# incarnation of the same code that libxcrypt uses itself, so it
# wouldn't be a proper interop test.

# straightforward passlib wrappers, sorted by age of algorithm
DES_CRYPT = passlib.hash.des_crypt
DES_CRYPT.set_backend("builtin")
def h_descrypt(phrase, rounds, salt):
    expected = DES_CRYPT.using(
        salt=salt, truncate_error=False
    ).hash(phrase)
    setting = expected[:2]
    yield format_case(phrase, setting, expected)

BIGCRYPT = passlib.hash.bigcrypt
# BIGCRYPT.set_backend("builtin") # currently p.h.bigcrypt always uses builtin
def h_bigcrypt(phrase, rounds, salt):
    # p.h.bigcrypt doesn't truncate to 128 chars.
    # The bigcrypt implementation in libxcrypt was reverse engineered
    # from a closed-source original and it's possible that they could
    # have gotten it wrong, but let's stick to what we have.
    expected = BIGCRYPT.using(
        salt=salt
    ).hash(phrase[:128])
    # bigcrypt has no prefix, so our crypt() looks at the length of
    # the setting string to decide whether it should use bigcrypt or
    # descrypt.  For bigcrypt to be used, the setting must be too long
    # to be a traditional DES hashed password.
    setting = expected[:2] + ".............."
    yield format_case(phrase, setting, expected)

BSDI_CRYPT = passlib.hash.bsdi_crypt
BSDI_CRYPT.set_backend("builtin")
def h_bsdicrypt(phrase, rounds, salt):
    expected = BSDI_CRYPT.using(
        salt=salt, rounds=rounds
    ).hash(phrase)
    setting = expected[:9]
    yield format_case(phrase, setting, expected)

MD5_CRYPT = passlib.hash.md5_crypt
MD5_CRYPT.set_backend("builtin")
def h_md5crypt(phrase, rounds, salt):
    expected = MD5_CRYPT.using(
        salt=salt
    ).hash(phrase)
    setting = expected[:expected.rfind('$')]
    yield format_case(phrase, setting, expected)

BSD_NTHASH = passlib.hash.bsd_nthash
#BSD_NTHASH.set_backend("builtin") # has only the built-in backend
def h_nt(phrase, rounds, salt):
    # passlib.hash.bsd_nthash attempts to decode byte strings as UTF-8, which
    # is Not What We Want.  Python's iso_8859_1 is an identity map from 00..FF
    # to U+0000..U+00FF, which is correct for this application.
    expected = BSD_NTHASH.hash(phrase.decode("iso_8859_1"))
    # NTHash doesn't have a salt.
    # Older versions of libxcrypt generated a fake salt which
    # we should ensure is ignored.
    yield format_case(phrase, "$3$", expected)
    yield format_case(phrase, "$3$__not_used__0123456789abcdef", expected)

SHA1_CRYPT = passlib.hash.sha1_crypt
SHA1_CRYPT.set_backend("builtin")
def h_sha1crypt(phrase, rounds, salt):
    expected = SHA1_CRYPT.using(
        salt=salt, rounds=rounds
    ).hash(phrase)
    setting = expected[:expected.rfind('$')]
    yield format_case(phrase, setting, expected)

SHA256_CRYPT = passlib.hash.sha256_crypt
SHA256_CRYPT.set_backend("builtin")
def h_sha256crypt(phrase, rounds, salt):
    expected = SHA256_CRYPT.using(
        salt=salt, rounds=rounds
    ).hash(phrase)
    setting = expected[:expected.rfind('$')]
    yield format_case(phrase, setting, expected)

SHA512_CRYPT = passlib.hash.sha512_crypt
SHA512_CRYPT.set_backend("builtin")
def h_sha512crypt(phrase, rounds, salt):
    expected = SHA512_CRYPT.using(
        salt=salt, rounds=rounds
    ).hash(phrase)
    setting = expected[:expected.rfind('$')]
    yield format_case(phrase, setting, expected)

# these need to do more work by hand

# We need to test setting strings both with and without the suffix
# that triggers the off-by-one error in the original Sun hash parser
# (which must be preserved by all interoperable implementations).
# passlib.hash.sun_md5_crypt.using(..., bare_salt=True) does not
# actually work.
from passlib.handlers.sun_md5_crypt import raw_sun_md5_crypt
def h_sunmd5(phrase, rounds, salt):
    if rounds == 0:
        bare_setting = "$md5$" + salt
    else:
        bare_setting = "$md5,rounds={}${}".format(rounds, salt)

    suff_setting = bare_setting + "$"
    bare_cksum = raw_sun_md5_crypt(phrase, rounds, bare_setting.encode("ascii"))
    suff_cksum = raw_sun_md5_crypt(phrase, rounds, suff_setting.encode("ascii"))

    bare_cksum = bare_cksum.decode("ascii")
    suff_cksum = suff_cksum.decode("ascii")

    yield format_case(phrase, bare_setting, bare_setting + "$" + bare_cksum)
    yield format_case(phrase, bare_setting + "$x",
                      bare_setting + "$" + bare_cksum)
    yield format_case(phrase, suff_setting, suff_setting + "$" + suff_cksum)
    yield format_case(phrase, suff_setting + "$",
                      suff_setting + "$" + suff_cksum)

# testing bcrypt $2b$ and $2y$ is easy, but ...
BCRYPT = passlib.hash.bcrypt
BCRYPT.set_backend("builtin")
def h_bcrypt(phrase, rounds, salt):
    expected = BCRYPT.using(
        salt=salt, rounds=rounds, ident="2b"
    ).hash(phrase)
    setting = expected[:-31]
    yield format_case(phrase, setting, expected)

def h_bcrypt_y(phrase, rounds, salt):
    expected = BCRYPT.using(
        salt=salt, rounds=rounds, ident="2y"
    ).hash(phrase)
    setting = expected[:-31]
    yield format_case(phrase, setting, expected)

# ...passlib doesn't implement the quirks of crypt_blowfish's $2a$ or
# $2x$, but we really must test them.  It is theoretically possible to
# implement the $2x$ quirk by a transformation on the input
# passphrase, but it would be hard to get right, and the $2a$ quirk
# cannot be implemented this way.  The path of least resistance is to
# compute the $2b$ hash and then look up its output in a table of
# substitutions for each quirk.  The collision resistance of the $2b$
# hash should protect us from false hits in these tables.  (Remember
# that the $2x$ quirk is a _bug_, preserved for backward compatibility's
# sake, that causes output collisions; duplicate entries on the
# right-hand side of the $2x$ substitution table are expected.)
bcrypt_a_substitutions = {
    'HdhhdUXVgLADnbTYf12kvsasO1gS51C': '5jlqAXzFdq.3//pJFBa432Pepsclbdu',
    'caGU5ROXj4M8Tgsx3s/D5BQIuhazIWa': '7N5c8AaH.dbqz7.2o.V2mRkUDV0TZnO',
    '8jdeg8QqT4CX3ERA9vZPFZAkxZRpxJW': 'D8jTC5oJeIumVOhMVpz79BzoGVhCjrW',
    '9f4sA9SRA0scUKcRyC5kce8dao2.GKe': 'E8Lpo1/qkGPTBDBxEsJjeEzh9nkZ9uW',
    'MOaOTHB4gEm.rriBjXNwBNh.Oc4mKGG': 'ZQhQBRpiYJCaQFgyHlB.t/F01cqLCIu',
    'Qjdj3GXX7D0sFE9jji6wxSTWIhqI3US': 'euRNRfAA6e0fjpTfQPPAMU1PCOf9IHq',
    'PIeeyENZVZmrKLAq5lwBUU9fMRVfV2m': 'h87NWu/js59XXaIj1hDyHxnjw7MJ5K6',
    'VmFQpoXeVuKTzkg2ZRsAf.8PZJZg142': 'vrukkCtLqHBLoBDsz6QoBtSwzI9Qxiq',
}
def h_bcrypt_a(phrase, rounds, salt):
    base = BCRYPT.using(
        salt=salt, rounds=rounds, ident="2b"
    ).hash(phrase)
    base_setting = base[4:-31]
    base_output  = base[-31:]
    output = bcrypt_a_substitutions.get(base_output, base_output)

    setting = "$2a$" + base_setting
    expected = setting + output
    yield format_case(phrase, setting, expected)

bcrypt_x_substitutions = {
    'xGPMyJSPyyeICKolPQ2gecm8rOgHwz.': '.sDifhVkUxvjPx6U4yeM2tC411Wuc.W',
    'SRMKxjeMqVSDMhSLhOnvtEZ/p5KhUbq': '1Z0zKnHbUU3q/kk//Pknlv19a4/T8.K',
    'PQInhDOdCKnXeUE.n/L.kQmTKM9ldK2': '25hhqa/GOJGmXui3avNI5MN8lOI2bCW',
    '7UwHe/ywPmdp.nr.ZLQSxd8hqn7qURW': '2E0h7UFL/4fALemA5ApWrCWllQXSPTu',
    'FZEYKXyyMgG13MK0uV8dwNotWf4Wm6e': '2M7Vc.sF98e8DDmnxFjRfAmrudbv6y.',
    'ZHZAnvydiPNiYH2VjRNhEAD6BEiyaWS': '3kVpkKaj1q2TAXm.ptIi98Nj3zVV8A2',
    'I7vjUzDOKf8XqcK8VSCm9b0bwoSm1Qm': '6He0iAS8JsdM.iB4OQ4fbsKMXPagLhy',
    'tLCLEXAt3RUjOgs.yvfWSni4j1JX/JS': '7bLwFi3rlVcl.xfhc7LxjqwOExfxki2',
    'zQPVIDk6wF8XmESji30KDHFabTlu0WK': '8gGm3RkYFflDX50UQs.tJ8InKNy.HGO',
    'KBv1eBM2he2T/QheS8zPHMejn5fMNRe': '8jdeg8QqT4CX3ERA9vZPFZAkxZRpxJW',
    'XEhidoDX1kz.RFnwWIzMJvtW2aP/k4e': '8jdeg8QqT4CX3ERA9vZPFZAkxZRpxJW',
    'UIzecIiCguM2sPh1F7L9IS3zOtmg5Im': '9f4sA9SRA0scUKcRyC5kce8dao2.GKe',
    'Xl2V4mQ7s0zX0b4XXH/b9UkRRCWpq3e': '9f4sA9SRA0scUKcRyC5kce8dao2.GKe',
    'tHwehGUs3q0b/Ejn42MsoM4Yv/iA1rq': '9iflVP0Ezo/iaxO0XS74wFglLNeryTS',
    'K2KXzhsMefB8v6hJJG3bOyKV.XRf6Qe': 'C3nvb4DotHdnRYgOPcdiK0C4q.DkIDO',
    'EuEnx.TyCLYgkTV/uhWL5xJTHV7ZMjG': 'HdhhdUXVgLADnbTYf12kvsasO1gS51C',
    'oaE0x.b2rUEITWgPdg.GEcU4ePHLh6m': 'IZEWKJgp.b.KG29zgOadgd2rUt5iV1e',
    '3cFqlEl7Y0HWaVLHpyyCqG8dBNk1DSm': 'IvJ5WHgSbYKj7g9hhdVsAjyzcnVT/.m',
    'gI4g/1M6K/Sz2bsgu9VDeEl6reszuXa': 'J6Y/kPTV/aHj7iJKuDfD5OPjVTvT2BK',
    'rz1efvzeJjL4mQ813hrZNg3p1.ivOii': 'MOaOTHB4gEm.rriBjXNwBNh.Oc4mKGG',
    'Tp1b9XCEV16BcrQ.0k4xf7V/OGPZLnK': 'N5E4WSTo/R5henexIN1o8xkGwe2V86W',
    'CARhc7ugFdgoPjDb7LUG.yQF2lboK6e': 'NjlOVoE5aHHQGtU9zc25wu0VykHnD1G',
    'nCdKcLO57oLlc6J6sNnGyfT9FrIawiW': 'PIeeyENZVZmrKLAq5lwBUU9fMRVfV2m',
    'DQjlTXDA5PBQ97.qBJY/vsHPQhLJDMe': 'PMOS6ygjFMSbDo.iJJam/G63inGIOBO',
    '1qOUgfpg30XDHLx/zrbWiMRcWyFhwye': 'QZ7A0p9q1Ag9Utfnfl/xif8NiDtVhO.',
    'h0JFRyDXfP0duxAkVxWGr8nMDEDvPca': 'QiT.KUY9PXgIzL2aECMKb0EvVl0Pzw6',
    'BvtRGGx3p8o0C5C36uS442Qqnrwofrq': 'Qjdj3GXX7D0sFE9jji6wxSTWIhqI3US',
    'UTFLPGm29p.YVzcY6pqejGEql1x8Ccq': 'TYqa73Yp3leHe3D6.ysuJtNLwOma87C',
    'YdPam5/ypFIyDUQMyCCEIwzVsTi0Sa6': 'TmFuGBy/Zgc6JVAr667oHeCvGQGyS1q',
    'gbhoNOH4mWxoEhRrQNdeI.rpk9XeuZS': 'UPPO3QqmgMIXGHvbOLe2IkNzHLAToY2',
    'ZkQGqjbMpqQ9oCsxNZjN8LQJaHFqPMC': 'VTMVcF7YBLV2/O6V1PNcQw0BD3hTN6a',
    'RbKkfW2ph8bd8B5yul5E97DxgDw9cT.': 'VmFQpoXeVuKTzkg2ZRsAf.8PZJZg142',
    'WI7ZNXFtzCd9mN1mWoNMQRHEmkDsZnm': 'VmFQpoXeVuKTzkg2ZRsAf.8PZJZg142',
    '2WegkGS5Xr/qYNkfEi6JmnR16WVSwcW': 'Xv3TUB0NdnMpyn4cfg4g48oZxRSIrNC',
    'LN/CEHXLfFeYdOOxbdxKu8ZqSIKgqAu': 'YdqUOXeMKw7X6zbqBXP6c1xqIKun7Oq',
    'VAQY6kySmwStlNY.sut9Y87njVr0mm.': 'Ysbn1VpHCTzInfW/z/8Q3k676rxfmSW',
    'qJn4AY9ch/WAR5JXeeJtVGeovjQrhd2': 'ZH9vItRapPbkFKo0iQqU4v71o0e19Mm',
    '4QrucGf30zIbQA.sO0d1QrU63xBrEYq': 'bqJMLkbvnTFj0OYMu9tPnQXstRzX/e6',
    'HD8RnTmGEavoR3LFVfdHvh3xA0QPka2': 'cYbtH8J2lfpMIiBKfF3pKpMno7JlLui',
    '6WgD2zYQDPgxR2sXlUeEeGKknxt95W.': 'caGU5ROXj4M8Tgsx3s/D5BQIuhazIWa',
    'rPSVExmrZ2WB1xntSbqZ/DRQRlKtVw.': 'caGU5ROXj4M8Tgsx3s/D5BQIuhazIWa',
    'PYLCOpTKZmhFn1CoBM2XNbWgqMX4Jk2': 'cxMAJfIx3T.Fv3O0KjL9VdM/oSSUVRK',
    'w8RVl3rh7sNazq544l0944qGq4GUFUq': 'fOj7giyJz5k22FHTKGVo8o1o5zGzPsq',
    'KHsCqMFVxOAGJObHwEBR3JaEdKVu1.m': 'fRmxM11/x97bxCrhecMENdkPm7YpRbe',
    '3wn02pxRJPnFwvlGt75DURDbt4g7om.': 'fY4v5x6.8txtKUKDP86z1xjlXG/GgZO',
    'k9Hv17Gha84losGKAq61csCZokj5pyy': 'gLfxf5sydYesf658mrFYb51nLrn/4Sm',
    'uTNb9MEHVGI7kd6UnQjYxgRNiKJM01S': 'h.z2vLHB/tYSU5fPXkrYB7TxLHGJnI6',
    'heAts1y/8kcTTP0/vD3yeuMX1ihF8dO': 'j72N2Fi2j3pGalOZvTqtyH3bYGotuju',
    'SqNATdQiNEckAKLsqgsKbAM5.hZoMCq': 'mjGosqV8OkKEcduYTNz5PKN2scswFya',
    'k786rdsOdUP4cRi.dLa3dsYueMj5UnS': 'nQF1kDoMDjBBwXy2wwMni2gJLKqA0ta',
    'G6PeIXKiqeNUPUbqFkMJvvI7G9hd51W': 'oBvt6zJCTP5OED1esTYUYPn31cWqwsa',
    'TszY8.avBpwJ6xbNjwws3SKBbK6kj6S': 'odAvHZH9azlhi1x4pBLF25.hj08RMFi',
    'z4QFggBRTVUeHRGL/CQxlAYHraYPcpa': 'ojiyBkc.4HZ2y5Yh0LxBbI6ZkLiRg0C',
    'PPtdI0NcxZ4Txyv/Y5ORfcP1XFriKT2': 'pjce7u/YRnectNa8DXjsSGzRdyH2PSG',
    'uIZ1Lgb.jHRDU/Z/LVXfpQCK72fTEHq': 'q5NMeQZ0UTyP/bILj02wdQ.Si5KHU1K',
    '51cV.PJOQVwmiao4t4lXsb9Cc3Jnuem': 'rB3dV.fJGdSihNlP0vo5PemoaZRp6LS',
    's6h1E6A2RzVn2KxXLQXsKosQeRo8bLa': 'sND7G4.cx6Dzn6TqbXfK99bElU0a7P.',
    'A96emG/jBf0K1K6vCG.eZGdLkSridom': 'tlD3cmtHgs/TwWAvy5E3F.freZS1bau',
    'hWYb0x3Q3zM0aBkB2G1arbzmWxRQS/i': 'whpbcVuyGrJbgveSSM3XQKa8G5alyRm',
    'AqM0XavJxJXeVlJ3Te3umGJaPOCYmZi': 'xP2lldc1.10LvZDjJZXNBKLzWqnkbOa',
    'UPBzTBMwJb5mKWflQ.5Rid4481RrxVy': 'xSD.pz8Zg3vt0Jiovghl5Dqrs8aw8ni',
    'yM59Cq5iVZDB3u45gTNhRSnOgrY1tdG': 'yED5tIjzyeH90te88BUWvTrMFHsWgCi',
    'k.qekGiJym3QgfeFCwNhPHg0Zk99KSa': 'yphVralDu2JlxYbCqwwGli/H6wBgBtC',
    'iYbzuFNFwSfCgqTGNsUFtSDh8PJAqSe': 'zAUUWh4XGsBGYs6yyUJTSfEgzoLXO6G',
}
def h_bcrypt_x(phrase, rounds, salt):
    base = BCRYPT.using(
        salt=salt, rounds=rounds, ident="2b"
    ).hash(phrase)
    base_setting = base[4:-31]
    base_output  = base[-31:]
    output = bcrypt_x_substitutions.get(base_output, base_output)

    setting = "$2x$" + base_setting
    expected = setting + output
    yield format_case(phrase, setting, expected)

# passlib includes an scrypt implementation, but its encoded password
# format is not the $7$ format we implement, so instead we use the
# stdlib's hashlib.scrypt (this is why 3.6+ is required) and encode
# the setting string by hand.  This may produce strings encoding N/r/p
# combinations that don't normally occur in the wild, but that's OK.
# The algorithm implemented by hashlib.scrypt is standardized as
# RFC 7914, so it's not an issue where that implementation came from.
# Yes, the salt is properly passed to raw_scrypt as-is.
from hashlib import scrypt as raw_scrypt
from passlib.utils.binary import h64 as hash64
def h_scrypt(phrase, rounds, salt):
    p = 1
    r = 8
    log2N = rounds + 7
    N = 1 << log2N

    bytesalt = salt.encode("ascii")
    setting = (b"$7$" +
               hash64.encode_int6(log2N) +
               hash64.encode_int30(r) +
               hash64.encode_int30(p) +
               bytesalt)

    binhash = raw_scrypt(phrase, salt=bytesalt, p=p, r=r, n=N, dklen=32)

    yield format_case(phrase, setting,
              setting + b'$' + hash64.encode_bytes(binhash))

#
# passlib does not support either yescrypt or gost-yescrypt.  In fact,
# as far as I can tell, at the time of writing, there exists only one
# implementation of yescrypt and gost-yescrypt, by Solar Designer et al
# which is the code we use ourselves.  However, a test for round-
# trippability and API consistency is still worthwhile, as is a test
# that the implementation's current behavior is compatible with its
# behavior some time ago.  Therefore, we encode setting strings by
# hand, and ctypes is used to access crypt_ra in the just-built
# libcrypt.so.  This will only work if the library was configured with
# --enable-hashes=yescrypt,gost-yescrypt,[others] and --enable-shared,
# which is OK, since it's not run during a normal build.  Remove this
# once passlib supports these hashes.
#
# crypt_ra is used because it's thread-safe but doesn't require us to
# know how big struct crypt_data is.  There is no good way to arrange
# for the data object to be deallocated.  Oh well.
LIBCRYPT = ctypes.cdll.LoadLibrary(os.path.join(os.getcwd(), ".libs",
                                                "libcrypt.so"))
_xcrypt_crypt_ra = LIBCRYPT.crypt_ra
_xcrypt_crypt_ra.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(ctypes.c_void_p),
                             ctypes.POINTER(ctypes.c_int)]
_xcrypt_crypt_ra.restype = ctypes.c_char_p
_xcrypt_crypt_ra_data = ctypes.c_void_p(0)
_xcrypt_crypt_ra_datasize = ctypes.c_int(0)

def xcrypt_crypt(phrase, setting):
    global _xcrypt_crypt_ra_data, _xcrypt_crypt_ra_datasize
    if not isinstance(phrase, bytes): phrase = phrase.encode("utf-8")
    if not isinstance(setting, bytes): setting = setting.encode("ascii")
    rv = _xcrypt_crypt_ra(phrase, setting,
                          ctypes.byref(_xcrypt_crypt_ra_data),
                          ctypes.byref(_xcrypt_crypt_ra_datasize))
    if not rv:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return bytes(rv)

def yescrypt_gensalt(ident, rounds, salt):
    if rounds == 1:
        params = "j75"
    elif rounds == 2:
        params = "j85"
    else:
        raise RuntimeError("don't know how to encode rounds={}"
                           .format(rounds))

    return "${}${}${}".format(ident, params, salt)

def h_yescrypt(phrase, rounds, salt):
    setting = yescrypt_gensalt("y", rounds, salt)
    yield format_case(phrase, setting, xcrypt_crypt(phrase, setting))

def h_gost_yescrypt(phrase, rounds, salt):
    setting = yescrypt_gensalt("gy", rounds, salt)
    yield format_case(phrase, setting, xcrypt_crypt(phrase, setting))

# Each method should contribute a group of parameters to the array
# below.  Each block has the form
#
#  ('method', [
#     (rounds, salt),
#     (rounds, salt),
#     ...
#  ])
#
# where 'method' is the method name used in the INCLUDE_ macros,
# rounds is a number and salt is a salt string.  The appropriate
# h_method function will be called with arguments (phrase, *params)
# where params is one of the tuples from its block, so it is OK to add
# extra arguments after the salt if necessary.
#
# If the method has a tunable rounds parameter, its array of
# (rounds, salt) pairs should have two salts * at least two values of
# the rounds parameter.  If it does not, it should have two salts and
# use 0 for the rounds parameter.
#
# The point of this test is not to exercise brute force resistance,
# so keep cost parameters low.
#
# Methods should be in alphabetical order by their INCLUDE_macro name.

SETTINGS = [
    ('bcrypt', [
        (5, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (5, 'abcdefghijklmnopqrstuu'),
        (4, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (4, 'abcdefghijklmnopqrstuu'),
    ]),

    ('bcrypt_y', [
        (5, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (5, 'abcdefghijklmnopqrstuu'),
        (4, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (4, 'abcdefghijklmnopqrstuu'),
    ]),

    ('bcrypt_a', [
        (5, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (5, 'abcdefghijklmnopqrstuu'),
        (4, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (4, 'abcdefghijklmnopqrstuu'),
    ]),

    ('bcrypt_x', [
        (5, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (5, 'abcdefghijklmnopqrstuu'),
        (4, 'CCCCCCCCCCCCCCCCCCCCC.'),
        (4, 'abcdefghijklmnopqrstuu'),
    ]),

    ('bigcrypt', [
        (0, 'CC'),
        (0, 'ab'),
    ]),

    # The bsdicrypt round count is required to be odd.
    ('bsdicrypt', [
        (1, 'CCCC'),
        (1, 'abcd'),
        (13, 'CCCC'),
        (13, 'abcd'),
    ]),

    ('descrypt', [
        (0, 'CC'),
        (0, 'ab'),
    ]),

    ('gost_yescrypt', [
        (1, '.......'),
        (1, 'LdJMENpBABJJ3hIHjB1Bi.'),
        (2, '.......'),
        (2, 'LdJMENpBABJJ3hIHjB1Bi.'),
    ]),

    ('md5crypt', [
        (0, 'CCCCCCCC'),
        (0, 'abcdefgh'),
    ]),

    ('nt', [
        (0, ''),
    ]),

    ('scrypt', [
        (1, 'SodiumChloride'),
        (1, 'unUNunUNunUNun'),
        (2, 'SodiumChloride'),
        (2, 'unUNunUNunUNun'),
    ]),

    ('sha1crypt', [
        (12, 'GGXpNqoJvglVTkGU'),
        (12, 'xSZGpk6Bp4SA3.cR'),
        (456, 'GGXpNqoJvglVTkGU'),
        (456, 'xSZGpk6Bp4SA3.cR'),
    ]),

    ('sha256crypt', [
        (1000, 'saltstring'),
        (1000, 'short'),
        (5000, 'saltstring'),
        (5000, 'short'),
    ]),

    ('sha512crypt', [
        (1000, 'saltstring'),
        (1000, 'short'),
        (5000, 'saltstring'),
        (5000, 'short'),
    ]),

    ('sunmd5', [
        (0, '9ZLwtuTO'),
        (0, '1xMeE.at'),
        (12, '9ZLwtuTO'),
        (12, '1xMeE.at'),
    ]),

    ('yescrypt', [
        (1, '.......'),
        (1, 'LdJMENpBABJJ3hIHjB1Bi.'),
        (2, '.......'),
        (2, 'LdJMENpBABJJ3hIHjB1Bi.'),
    ]),
]

# Python specifies that an \x escape in a string literal consumes
# exactly two subsequent hexadecimal digits.  C, on the other hand,
# specifies that \x in a string literal consumes *any number of*
# hexadecimal digits, and if the hexadecimal number is larger than the
# range representable by 'unsigned char' the result is
# implementation-defined.  For instance, "\x303" == "03" in Python,
# but in C the string on the left could be anything.  The simplest way
# to deal with this is to escape the string Python's way and then
# replace sequences like '\x303' with '\x30""3'.
c_hex_escape_fixup_re_ = re.compile(
    r"(\\x[0-9a-fA-F]{2})([0-9a-fA-F])")

def c_hex_escape(s):
    if isinstance(s, bytes):
        s = s.decode("iso_8859_1")
    s = s.encode("unicode_escape").decode("ascii")

    return c_hex_escape_fixup_re_.sub(r'\1""\2', s)

def format_case(phrase, setting, expected):
    if expected is None:
        return ('  {{ "{}", 0, "{}" }},\n'
                .format(c_hex_escape(setting),
                        c_hex_escape(phrase)))
    else:
        return ('  {{ "{}", "{}", "{}" }},\n'
                .format(c_hex_escape(setting),
                        c_hex_escape(expected),
                        c_hex_escape(phrase)))

# To reduce the painful slowness of this program _somewhat_,
# we use a multiprocessing pool to compute all of the hashes.

def generate_phrase_setting_combs():
    for macro_name, settings in SETTINGS:
        for phrase in PHRASES:
            for setting in settings:
                yield (macro_name, phrase, setting)

def worker_compute_one(args):
    method, phrase, setting = args

    import __main__
    sfunc = getattr(__main__, 'h_' + method)
    return [(method, case) for case in sfunc(phrase, *setting)]

def main():
    sys.stdout.write(
        "/* Automatically generated by test-crypt-kat-gen.py.\n"
        "   Do not edit this file by hand.  */\n\n")

    with multiprocessing.Pool() as pool:
        prev_method = None
        for items in pool.imap(worker_compute_one,
                               generate_phrase_setting_combs(),
                               chunksize=100):
            for method, case in items:
                if method != prev_method:
                    if prev_method is not None:
                        sys.stdout.write("#endif // {}\n\n"
                                         .format(prev_method))
                    sys.stdout.write("#if INCLUDE_{}\n".format(method))
                    prev_method = method
                sys.stdout.write(case)

        if prev_method is not None:
            sys.stdout.write("#endif // {}\n".format(prev_method))

if __name__ == '__main__':
    main()
