"""Realistic captured output from Linux package managers, used as parse fixtures.

Formats mirror actual tools with LC_ALL=C set:
- apt-cache show/search, dpkg-query -W
- flatpak search/list (columns=...)
- dnf search -q
- pacman -Ss / -Q
- zypper -q search
- nix search nixpkgs / nix-env -q
- apk search -d / apk info -v
- snap find --color=never / snap list / snap refresh
"""

APT_CACHE_SHOW = """\
Package: vlc
Status: install ok installed
Priority: optional
Section: video
Installed-Size: 952
Maintainer: Debian Multimedia Maintainers <debian-multimedia@lists.debian.org>
Architecture: amd64
Version: 3.0.20-0+deb12u1
Depends: libc6 (>= 2.34), libvlccore9 (>= 3.0.20)
Homepage: https://www.videolan.org/
Description: multimedia player and streamer
 VLC is the VideoLAN project's media player.
 It supports MPEG-1, MPEG-2, MPEG-4, H.264, WebM,
 DVD, Blu-ray, VCD, and more.

Package: git
Status: deinstall ok config-files
Priority: optional
Section: vcs
Installed-Size: 2320
Maintainer: Gerrit Pape <pape@smarden.org>
Architecture: amd64
Version: 1:2.39.2-1.1
Description: fast, scalable, distributed revision control system
 Git is popular version control system designed to handle
 very large projects with speed and efficiency.
"""

APT_CACHE_SEARCH = """\
vlc
vlc-bin
vlc-plugin-access-extra
vlc-plugin-qt
"""

DPKG_QUERY_W = """\
adduser\t3.134
bash\t5.2.15-2+b2
vlc\t3.0.20-0+deb12u1
zlib1g\t1:1.2.13.dfsg-1
"""

FLATPAK_SEARCH = """\
org.videolan.VLC\t3.0.20\tstable\tflathub\tVLC media player, the open-source multimedia player
org.mozilla.firefox\t130.0\tstable\tflathub,gnome\tStandalone web browser from mozilla.org
com.spotify.Client\t1.2.47.526\tstable\tflathub\tMusic player for desktop
"""

FLATPAK_SEARCH_REMOTES = """\
org.videolan.VLC\tflathub
org.mozilla.firefox\tflathub,gnome
com.spotify.Client\tflathub
"""

FLATPAK_LIST_USER = """\
org.mozilla.firefox\t130.0\tstable\tStandalone web browser from mozilla.org
"""

FLATPAK_LIST_SYSTEM = """\
org.mozilla.firefox\t129.0\tstable\tStandalone web browser from mozilla.org
"""

FLATPAK_SEARCH_NO_MATCH = ("", "error: No matches found\n", 1)

DNF_SEARCH = """\
============================================= Name Exactly Matched: vlc =============================================
vlc : The portable version of VLC media player
============================================== Name Matched: vlc ==================================================
vlc-core : The core components of VLC media player
vlc-plugin-base : Base plugins for VLC media player
============================================== Summary Matched: vlc ================================================
libvlc5 : library for the VLC media player
"""

DNF_SEARCH_NO_MATCH = """\
No matches found.
"""

PACMAN_SS = """\
extra/vlc 3.0.20-2 (multimedia)
    A multi-platform free and open-source media player
community/firefox 130.0-1 (network)
    Standalone web browser from mozilla.org
community/neovim 0.10.0-1 (editors)
    Fork of Vim aiming to improve user experience, plugins, and GUIs
"""

PACMAN_Q = """\
bash 5.2.026-2
vlc 3.0.20-2
zlib 1:1.3.1-1
"""

ZYPPER_SEARCH = """\
S  | Name           | Summary                        | Type
---+----------------+--------------------------------+--------
i  | vlc            | The portable version of VLC    | package
   | vlc-codecs     | Additional codecs for VLC      | package
   | vlc-qt         | Qt frontend for VLC            | package
"""

RPM_QA = """\
bash\t5.2.26-1.fc40.x86_64
vlc\t3.0.20-1.fc40.x86_64
zlib\t1.3.1-1.fc40.x86_64
"""

NIX_SEARCH = """\
* legacyPackages.x86_64-linux.vlc (3.0.20)
  VideoLAN Client
* legacyPackages.x86_64-linux.vlc-nox (3.0.20)
  VideoLAN Client (without X support)
* legacyPackages.x86_64-linux.vlc-plugin (3.0.20)
  VLC plugin
"""

NIX_ENV_Q = """\
vlc-3.0.20
htop-3.3.0
cura-5.7.0
"""

APK_SEARCH = """\
vlc - VideoLAN Client (new version)
vlc-qt - Qt bindings for VLC
"""

APK_INFO_V = """\
musl-1.2.5-r0
vlc-3.0.20-r0
zlib-1.3.1-r1
"""

SNAP_FIND = """\
Name                      Version    Publisher     Notes    Summary
7kaa                      2.15.4     7kaa✓         -        7 Days to Die game
vlc                       3.0.20     videolan✓     -        VLC media player
gimp                      2.10.38    snapcrafters✓  classic  GNU Image Manipulation Program
"""

SNAP_FIND_NO_MATCH = ("", "No matching snaps for \"zzz\"\n", 1)

SNAP_LIST = """\
Name     Version  Rev  Tracking     Publisher   Notes
vlc      3.0.20   10   latest/stable videolan✓   -
firefox  130.0    5    latest/stable mozilla✓    -
"""

SNAP_REFRESH = """\
vlc 3.0.20 3.1.0 10 from snap-store
firefox 130.0 131.0 5 from snap-store
"""

SNAP_REFRESH_NONE = "All snaps up to date.\n"
