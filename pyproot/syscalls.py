import platform

MACHINE = platform.machine()

# (syscall_adı, path_argümanı_indeksleri)
# Her mimari için ayrı tablo
_ARM64 = {
    56:  ("openat",        [1]),        # openat(dirfd, path, ...)
    80:  ("fstat",         []),         # path yok
    78:  ("readlinkat",    [1]),
    35:  ("unlinkat",      [1]),
    34:  ("mkdirat",       [1]),
    49:  ("chdir",         [0]),
    51:  ("chroot",        [0]),        # fake edeceğiz
    221: ("execve",        [0]),
    59:  ("execveat",      [1]),
    43:  ("statx",         [1]),
    67:  ("fstatat",       [1]),
    38:  ("renameat",      [1, 3]),
    174: ("getuid",        []),         # fake root
    175: ("geteuid",       []),
    176: ("getgid",        []),
    177: ("getegid",       []),
}

_X86_64 = {
    2:   ("open",          [0]),
    4:   ("stat",          [0]),
    6:   ("lstat",         [0]),
    257: ("openat",        [1]),
    89:  ("readlink",      [0]),
    267: ("readlinkat",    [1]),
    87:  ("unlink",        [0]),
    263: ("unlinkat",      [1]),
    83:  ("mkdir",         [0]),
    258: ("mkdirat",       [1]),
    80:  ("chdir",         [0]),
    161: ("chroot",        [0]),
    59:  ("execve",        [0]),
    322: ("execveat",      [1]),
    332: ("statx",         [1]),
    262: ("newfstatat",    [1]),
    82:  ("rename",        [0, 1]),
    316: ("renameat2",     [1, 3]),
    102: ("getuid",        []),
    107: ("geteuid",       []),
    104: ("getgid",        []),
    108: ("getegid",       []),
}

SYSCALL_TABLE = _ARM64 if MACHINE == "aarch64" else _X86_64

# Sahte root döndürecek syscall'lar
FAKE_ROOT_SYSCALLS = {
    name for name, _ in SYSCALL_TABLE.values()
    if name in ("getuid","geteuid","getgid","getegid")
}