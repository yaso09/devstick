import ctypes, platform

MACHINE = platform.machine()

# ARM64 user_regs_struct
class ARM64Regs(ctypes.Structure):
    _fields_ = [
        ("regs",    ctypes.c_uint64 * 31),
        ("sp",      ctypes.c_uint64),
        ("pc",      ctypes.c_uint64),
        ("pstate",  ctypes.c_uint64),
    ]

# x86_64 user_regs_struct
class X86_64Regs(ctypes.Structure):
    _fields_ = [
        ("r15", ctypes.c_uint64), ("r14", ctypes.c_uint64),
        ("r13", ctypes.c_uint64), ("r12", ctypes.c_uint64),
        ("rbp", ctypes.c_uint64), ("rbx", ctypes.c_uint64),
        ("r11", ctypes.c_uint64), ("r10", ctypes.c_uint64),
        ("r9",  ctypes.c_uint64), ("r8",  ctypes.c_uint64),
        ("rax", ctypes.c_uint64), ("rcx", ctypes.c_uint64),
        ("rdx", ctypes.c_uint64), ("rsi", ctypes.c_uint64),
        ("rdi", ctypes.c_uint64), ("orig_rax", ctypes.c_uint64),
        ("rip", ctypes.c_uint64), ("cs",  ctypes.c_uint64),
        ("eflags", ctypes.c_uint64), ("rsp", ctypes.c_uint64),
        ("ss",  ctypes.c_uint64), ("fs_base", ctypes.c_uint64),
        ("gs_base", ctypes.c_uint64), ("ds", ctypes.c_uint64),
        ("es",  ctypes.c_uint64), ("fs",  ctypes.c_uint64),
        ("gs",  ctypes.c_uint64),
    ]

def get_regs_class():
    if MACHINE == "aarch64":
        return ARM64Regs
    elif MACHINE == "x86_64":
        return X86_64Regs
    else:
        raise NotImplementedError(f"Desteklenmeyen mimari: {MACHINE}")

def syscall_number(regs):
    if MACHINE == "aarch64":
        return regs.regs[8]   # x8 = syscall no
    else:
        return regs.orig_rax

def syscall_args(regs):
    """Syscall argümanlarını sırayla döndür."""
    if MACHINE == "aarch64":
        return [regs.regs[i] for i in range(6)]   # x0–x5
    else:
        return [regs.rdi, regs.rsi, regs.rdx,
                regs.r10, regs.r8,  regs.r9]

def set_syscall_arg(pid, regs, index, value):
    """Bir syscall argümanını değiştir."""
    import tracer
    if MACHINE == "aarch64":
        regs.regs[index] = value
    else:
        fields = ["rdi","rsi","rdx","r10","r8","r9"]
        setattr(regs, fields[index], value)
    tracer.ptrace(tracer.PTRACE_SETREGS, pid, 0, ctypes.addressof(regs))

def set_return_value(pid, regs, value):
    """Syscall dönüş değerini manipüle et (entry öncesi kullanma)."""
    if MACHINE == "aarch64":
        regs.regs[0] = ctypes.c_uint64(value).value
    else:
        regs.rax = ctypes.c_uint64(value).value
    import tracer
    tracer.ptrace(tracer.PTRACE_SETREGS, pid, 0, ctypes.addressof(regs))