import os
import subprocess
import shutil
from pathlib import Path
import sys
import proot_distro_api

pd = proot_distro_api.ProotDistro()

BASE_DIR = Path(__file__).resolve().parent

PROOT_DISTRO_ROOT = os.path.expandvars(
	"$PREFIX/var/lib/proot-distro/installed-rootfs"
)

class TempBindDistro:
	def __init__(self, name: str, rootfs_path: str):
		self.name = name
		self.rootfs_path = os.path.abspath(rootfs_path)
		self.target_path = os.path.join(PROOT_DISTRO_ROOT, name)

	def _attach(self):
		if os.path.islink(self.target_path):
			os.unlink(self.target_path)
		elif os.path.exists(self.target_path):
			raise RuntimeError(f"{self.target_path} gerçek bir dizin — silmiyorum")

		print(f"[*] Binding rootfs: {self.target_path}")
		os.symlink(self.rootfs_path, self.target_path)

	def _detach(self):
		if os.path.islink(self.target_path):
			print("[*] Removing bind link")
			os.unlink(self.target_path)

	def run(self):
		try:
			self._attach()

			print(f"\n[*] Starting proot-distro: {self.name}\n")

			pd.login(
				self.name,
				shared_tmp=True
			)

		finally:
			print("\n[*] Cleaning up session...\n")
			self._detach()

def run_distro_temp(name: str, rootfs_path: str):
	session = TempBindDistro(name, rootfs_path)
	session.run()
