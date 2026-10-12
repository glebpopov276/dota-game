[app]
title = Сетевая 2D-игра
package.name = netgame
package.domain = org.gleb

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,wav,ttf
source.exclude_exts = spec,pyc,pyo
source.exclude_dirs = tests,bin,venv,.venv,.git,.github,dist,buildozer,.buildozer,__pycache__

version = 0.1
requirements = python3==3.10.12,hostpython3==3.10.12,kivy==2.3.0,pygame

orientation = landscape
fullscreen = 1

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.arch = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1