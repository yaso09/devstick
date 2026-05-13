"""
proot_distro_api.py
~~~~~~~~~~~~~~~~~~~
proot-distro CLI komutlarının tamamını saran saf Python API'si.
Her fonksiyon, altta yatan komut modüllerini doğrudan çağırır;
CLI ayrıştırma katmanını (main.py) tamamen bypass eder.

Kullanım örneği:
    from proot_distro_api import ProotDistro
    pd = ProotDistro()
    pd.install("ubuntu:24.04", custom_name="myubuntu")
    pd.login("myubuntu", user="root", isolated=True)
"""

import argparse
import sys
from dataclasses import dataclass, field
from typing import Optional

# Komut modüllerini içe aktar (proot_distro paketi kurulu olmalı)
from proot_distro.commands.install import command_install
from proot_distro.commands.remove import command_remove
from proot_distro.commands.rename import command_rename
from proot_distro.commands.reset import command_reset
from proot_distro.commands.login import command_login
from proot_distro.commands.list import command_list
from proot_distro.commands.backup import command_backup
from proot_distro.commands.restore import command_restore
from proot_distro.commands.clear_cache import command_clear_cache
from proot_distro.commands.copy import command_copy
from proot_distro.commands.sync import command_sync
from proot_distro.commands.run import command_run


def _ns(**kwargs) -> argparse.Namespace:
    """Anahtar-değer çiftlerinden argparse.Namespace nesnesi oluşturur."""
    return argparse.Namespace(**kwargs)


class ProotDistro:
    """
    proot-distro CLI komutlarına karşılık gelen Python metodları.

    Her metod, CLI handler fonksiyonunu doğrudan çağırır;
    böylece kabuk süreçleri başlatılmaz ve çıktı akışları
    tamamen Python tarafından kontrol edilebilir.
    """

    # ------------------------------------------------------------------ #
    # install                                                              #
    # ------------------------------------------------------------------ #
    def install(
        self,
        image: str,
        *,
        custom_name: Optional[str] = None,
        override_arch: Optional[str] = None,
    ) -> None:
        """
        Bir container imajını indir ve kur.

        :param image:         Docker imaj referansı, örn. 'ubuntu:24.04'
        :param custom_name:   Kurulacak container için özel takma ad
        :param override_arch: Hedef mimari (aarch64/arm/i686/riscv64/x86_64)
        """
        args = _ns(
            alias=image,
            custom_dist_name=custom_name,
            override_arch=override_arch,
        )
        command_install(args, {})

    # ------------------------------------------------------------------ #
    # remove                                                               #
    # ------------------------------------------------------------------ #
    def remove(self, name: str, *, verbose: bool = False) -> None:
        """
        Kurulu bir container'ı sil.

        :param name:    Container takma adı
        :param verbose: Ayrıntılı çıktı
        """
        args = _ns(alias=name, verbose=verbose)
        command_remove(args, {})

    # ------------------------------------------------------------------ #
    # rename                                                               #
    # ------------------------------------------------------------------ #
    def rename(self, original: str, new_name: str) -> None:
        """
        Kurulu bir container'ı yeniden adlandır.

        :param original: Mevcut container takma adı
        :param new_name: Yeni takma ad
        """
        args = _ns(orig_alias=original, new_alias=new_name)
        command_rename(args, {})

    # ------------------------------------------------------------------ #
    # reset                                                                #
    # ------------------------------------------------------------------ #
    def reset(self, name: str) -> None:
        """
        Bir container'ı fabrika ayarlarına sıfırla (içerik silinir).

        :param name: Container takma adı
        """
        args = _ns(alias=name)
        command_reset(args, {})

    # ------------------------------------------------------------------ #
    # login                                                                #
    # ------------------------------------------------------------------ #
    def login(
        self,
        name: str,
        *,
        user: str = "root",
        cmd: Optional[list] = None,
        redirect_ports: bool = False,
        isolated: bool = False,
        minimal: bool = False,
        termux_home: bool = False,
        shared_tmp: bool = False,
        shared_x11: bool = False,
        binds: Optional[list] = None,
        no_link2symlink: bool = False,
        no_sysvipc: bool = False,
        no_kill_on_exit: bool = False,
        no_arch_warning: bool = False,
        emulator: Optional[str] = None,
        kernel: Optional[str] = None,
        hostname: Optional[str] = None,
        work_dir: Optional[str] = None,
        env: Optional[list] = None,
        debug: bool = False,
    ) -> None:
        """
        Bir container'a interaktif kabuk veya komut çalıştır (login).

        :param name:            Container takma adı
        :param user:            Giriş yapılacak kullanıcı (varsayılan: root)
        :param cmd:             Kabuğa iletilecek komut listesi
        :param redirect_ports:  Port yönlendirmeyi etkinleştir
        :param isolated:        Ana sistemden yalıtılmış mod
        :param minimal:         Minimal bağ noktalarıyla başlat
        :param termux_home:     Termux home dizinini paylaş
        :param shared_tmp:      /tmp dizinini paylaş
        :param shared_x11:      X11 soketini paylaş
        :param binds:           Ekstra bağ noktaları listesi ['HOST:GUEST', ...]
        :param no_link2symlink: --link2symlink devre dışı
        :param no_sysvipc:      SysV IPC devre dışı
        :param no_kill_on_exit: Çıkışta proot süreçlerini öldürme
        :param no_arch_warning: Mimari uyarısını bastır
        :param emulator:        Özel emülatör yolu
        :param kernel:          Sahte kernel sürüm dizesi
        :param hostname:        Container hostname'i
        :param work_dir:        Başlangıç çalışma dizini
        :param env:             Ortam değişkenleri ['VAR=değer', ...]
        :param debug:           proot hata ayıklama çıktısı
        """
        args = _ns(
            alias=name,
            user=user,
            login_cmd=cmd or [],
            redirect_ports=redirect_ports,
            isolated=isolated,
            minimal=minimal,
            termux_home=termux_home,
            shared_tmp=shared_tmp,
            shared_x11=shared_x11,
            bind=binds,
            no_link2symlink=no_link2symlink,
            no_sysvipc=no_sysvipc,
            no_kill_on_exit=no_kill_on_exit,
            no_arch_warning=no_arch_warning,
            emulator=emulator,
            kernel=kernel,
            hostname=hostname,
            work_dir=work_dir,
            env=env,
            debug=debug,
        )
        command_login(args, {})

    # ------------------------------------------------------------------ #
    # list                                                                 #
    # ------------------------------------------------------------------ #
    def list(self) -> None:
        """
        Kurulu ve kurulabilir container'ları listele.
        """
        args = _ns()
        command_list(args, {})

    # ------------------------------------------------------------------ #
    # backup                                                               #
    # ------------------------------------------------------------------ #
    def backup(
        self,
        name: str,
        *,
        output: Optional[str] = None,
        compression: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        """
        Bir container'ı arşive yedekle.

        :param name:        Container takma adı
        :param output:      Çıktı arşiv dosyası yolu
        :param compression: Sıkıştırma türü: gzip / bzip2 / xz / none
        :param verbose:     Ayrıntılı çıktı
        """
        args = _ns(
            alias=name,
            output=output,
            compression=compression,
            verbose=verbose,
        )
        command_backup(args, {})

    # ------------------------------------------------------------------ #
    # restore                                                              #
    # ------------------------------------------------------------------ #
    def restore(self, archive: str, *, verbose: bool = False) -> None:
        """
        Arşivden container geri yükle.

        :param archive: Arşiv dosyası yolu
        :param verbose: Ayrıntılı çıktı
        """
        args = _ns(archive=archive, verbose=verbose)
        command_restore(args, {})

    # ------------------------------------------------------------------ #
    # clear_cache                                                          #
    # ------------------------------------------------------------------ #
    def clear_cache(self, *, verbose: bool = False) -> None:
        """
        İndirilen imaj önbelleğini temizle.

        :param verbose: Ayrıntılı çıktı
        """
        args = _ns(verbose=verbose)
        command_clear_cache(args, {})

    # ------------------------------------------------------------------ #
    # copy                                                                 #
    # ------------------------------------------------------------------ #
    def copy(
        self,
        source: str,
        destination: str,
        *,
        verbose: bool = False,
        move: bool = False,
        recursive: bool = False,
    ) -> None:
        """
        Container içinde veya container'lar arası dosya/dizin kopyala.

        :param source:      Kaynak yol
        :param destination: Hedef yol
        :param verbose:     Ayrıntılı çıktı
        :param move:        Kopyalama yerine taşı
        :param recursive:   Dizinleri yinelemeli kopyala
        """
        args = _ns(
            source=source,
            destination=destination,
            verbose=verbose,
            move=move,
            recursive=recursive,
        )
        command_copy(args, {})

    # ------------------------------------------------------------------ #
    # sync                                                                 #
    # ------------------------------------------------------------------ #
    def sync(
        self,
        source: str,
        destination: str,
        *,
        verbose: bool = False,
        checksum: bool = False,
        delete: bool = False,
    ) -> None:
        """
        İki dizini senkronize et (rsync benzeri).

        :param source:      Kaynak dizin
        :param destination: Hedef dizin
        :param verbose:     Ayrıntılı çıktı
        :param checksum:    İçerik karşılaştırması için sağlama toplamı kullan
        :param delete:      Hedefte kaynakta olmayan dosyaları sil
        """
        args = _ns(
            source=source,
            destination=destination,
            verbose=verbose,
            checksum=checksum,
            delete=delete,
        )
        command_sync(args, {})

    # ------------------------------------------------------------------ #
    # run                                                                  #
    # ------------------------------------------------------------------ #
    def run(
        self,
        name: str,
        run_args: Optional[list] = None,
        *,
        user: str = "root",
        redirect_ports: bool = False,
        isolated: bool = False,
        minimal: bool = False,
        termux_home: bool = False,
        shared_tmp: bool = False,
        shared_x11: bool = False,
        binds: Optional[list] = None,
        no_link2symlink: bool = False,
        no_sysvipc: bool = False,
        no_kill_on_exit: bool = False,
        no_arch_warning: bool = False,
        emulator: Optional[str] = None,
        kernel: Optional[str] = None,
        hostname: Optional[str] = None,
        work_dir: Optional[str] = None,
        env: Optional[list] = None,
        debug: bool = False,
    ) -> None:
        """
        Container içinde non-interaktif komut çalıştır.

        login() ile aynı seçenekleri destekler; fark olarak interaktif
        kabuk yerine verilen komut doğrudan yürütülür.

        :param name:      Container takma adı
        :param run_args:  Çalıştırılacak komut ve argümanları
        """
        args = _ns(
            alias=name,
            run_args=run_args or [],
            user=user,
            redirect_ports=redirect_ports,
            isolated=isolated,
            minimal=minimal,
            termux_home=termux_home,
            shared_tmp=shared_tmp,
            shared_x11=shared_x11,
            bind=binds,
            no_link2symlink=no_link2symlink,
            no_sysvipc=no_sysvipc,
            no_kill_on_exit=no_kill_on_exit,
            no_arch_warning=no_arch_warning,
            emulator=emulator,
            kernel=kernel,
            hostname=hostname,
            work_dir=work_dir,
            env=env,
            debug=debug,
        )
        command_run(args, {})
