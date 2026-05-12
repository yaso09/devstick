import os


def is_termux():
    return any("com.termux" in p for p in os.environ.get("PATH", "").split(":"))
