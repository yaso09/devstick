import ctypes
import ctypes.util
import os
import signal
from . import arch, syscalls, translator

get_regs_class = arch.get_regs_class
syscall_number = arch.syscall_number
syscall_args = arch.syscall_args
set_return_value = arch.set_return_value

SYSCALL_TABLE = syscalls.SYSCALL_TABLE

PathTranslator = translator.PathTranslator

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

PTRACE_TRACEME = 0
PTRACE_CONT = 7
PTRACE_SYSCALL = 24
PTRACE_GETREGS = 12
PTRACE_SETREGS = 13
PTRACE_SETOPTIONS = 0x4200
PTRACE_O_TRACESYSGOOD = 0x1
PTRACE_O_TRACECLONE = 0x8

RegsClass = get_regs_class()


def ptrace(request, pid, addr=0, data=0):
    ret = libc.ptrace(request, pid, ctypes.c_void_p(addr),
                      ctypes.c_void_p(data))
    if ret == -1:
        err = ctypes.get_errno()
        if err:
            raise OSError(err, os.strerror(err))
    return ret


def read_string(pid: int, addr: int) -> str:
    """Tracee'nin belleu011finden null-terminated string oku."""
    result = bytearray()
    while True:
        # PEEKDATA 8 byte okur (x86_64/arm64)
        word = ptrace(2, pid, addr)  # PTRACE_PEEKDATA
        raw = word.to_bytes(8, "little") if hasattr(word, "to_bytes") else \
            ctypes.c_long(word).value.to_bytes(8, "little", signed=True)
        for byte in raw:
            if byte == 0:
                return result.decode("utf-8", errors="replace")
            result.append(byte)
        addr += 8


def write_string(pid: int, addr: int, s: str):
    """Tracee belleu011fine string yaz (POKEDATA ile, 8 byte hizalu0131)."""
    data = s.encode("utf-8") + b"\x00"
    # 8 byte'a hizala
    padded = data + b"\x00" * (8 - len(data) % 8)
    for i in range(0, len(padded), 8):
        chunk = int.from_bytes(padded[i:i+8], "little")
        libc.ptrace(5, pid, ctypes.c_void_p(addr + i),
                    ctypes.c_void_p(chunk))  # POKEDATA


def allocate_string(pid: int, regs, s: str) -> int:
    """
    Stack'te yer au00e7 ve string'i yaz.
    ARM64: sp, x86_64: rsp
    """
    import platform
    if platform.machine() == "aarch64":
        sp = regs.sp - 256
        regs.sp = sp
    else:
        sp = regs.rsp - 256
        regs.rsp = sp
    write_string(pid, sp, s)
    return sp


class Tracer:
    def __init__(self, rootfs: str, argv: list, bindings: dict = None):
        self.translator = PathTranslator(rootfs, bindings)
        self.argv = argv
        self.in_syscall = {}   # pid u2192 bool (syscall entry mi exit mi)

    def run(self):
        pid = os.fork()
        if pid == 0:
            self._child()
        else:
            self._parent(pid)

    def _child(self):
        ptrace(PTRACE_TRACEME, 0)
        os.kill(os.getpid(), signal.SIGSTOP)
        os.execvp(self.argv[0], self.argv)

    def _parent(self, root_pid: int):
        # u0130lk SIGSTOP'u bekle
        os.waitpid(root_pid, 0)
        ptrace(PTRACE_SETOPTIONS, root_pid, 0,
               PTRACE_O_TRACESYSGOOD | PTRACE_O_TRACECLONE)
        ptrace(PTRACE_SYSCALL, root_pid, 0, 0)

        tracked = {root_pid}

        while tracked:
            try:
                pid, status = os.waitpid(-1, 0)
            except ChildProcessError:
                break

            if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                tracked.discard(pid)
                continue

            if os.WIFSTOPPED(status):
                sig = os.WSTOPSIG(status)

                if sig == (signal.SIGTRAP | 0x80):   # syscall-stop
                    tracked.add(pid)
                    self._handle_syscall(pid)
                else:
                    ptrace(PTRACE_SYSCALL, pid, 0, sig)
                    continue

            ptrace(PTRACE_SYSCALL, pid, 0, 0)

    def _handle_syscall(self, pid: int):
        regs = RegsClass()
        ptrace(PTRACE_GETREGS, pid, 0, ctypes.addressof(regs))

        is_entry = not self.in_syscall.get(pid, False)
        self.in_syscall[pid] = is_entry

        if not is_entry:
            return   # exit: du00f6nu00fcu015f deu011ferini deu011fiu015ftirmek istersen burada

        nr = syscall_number(regs)
        if nr not in SYSCALL_TABLE:
            return

        name, path_arg_indices = SYSCALL_TABLE[nr]

        # Sahte root
        if name in ("getuid", "geteuid", "getgid", "getegid"):
            set_return_value(pid, regs, 0)
            # Syscall'u0131 iptal et: nr'yi geu00e7ersiz yap
            # (mimari bau011fu0131mlu0131 u2014 basitlik iu00e7in burada bu0131raku0131yoruz)
            return

        # chroot: yoksay, zaten rootfs iu00e7indeyiz
        if name == "chroot":
            set_return_value(pid, regs, 0)
            return

        args = syscall_args(regs)

        for idx in path_arg_indices:
            addr = args[idx]
            if addr == 0:
                continue
            try:
                guest_path = read_string(pid, addr)
            except Exception:
                continue

            if not guest_path.startswith("/"):
                continue

            host_path = self.translator.to_host(guest_path)

            # Yeni path'i stack'e yaz ve argu00fcmanu0131 gu00fcncelle
            new_addr = allocate_string(pid, regs, host_path)
            args[idx] = new_addr

            # Regs'i gu00fcncelle
            from arch import set_syscall_arg
            set_syscall_arg(pid, regs, idx, new_addr)
