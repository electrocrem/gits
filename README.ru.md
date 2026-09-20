# gits-hyde — «Призрак в доспехах» для HyDE

Полноценный рабочий стол в стиле *Ghost in the Shell* для [HyDE](https://github.com/HyDE-Project/HyDE) на Hyprland:
тёмно-синяя палитра с циановым «люминофором», квадратные углы, тонкие рамки, иероглифы-метки.
Один установщик, один деинсталлятор, каждый заменённый файл сохраняется в бэкап. [English version](README.md)

## Что внутри

Тема HyDE, waybar (свой макет, переключатель workflow, watchdog), виджеты рабочего стола (часы, календарь, плеер, погода,
сеть, батарея, нагрузка, to-do, визуализатор звука, редкие глитчи на обоях), hyprlock, темы SDDM / Plymouth / GRUB, rofi-лаунчер и меню (действия уведомлений, Wi-Fi, Bluetooth, профиль питания), звуки интерфейса, всплывающие панели (управление, плеер, центр уведомлений), OSD громкости/яркости/подсветки, dunst,
wlogout, терминал (баннер с картинкой, в том числе внутри tmux; tmux по умолчанию, `GITS_NO_TMUX=1` отключает; starship, fzf, bat, btop, lazygit, tmux, yazi), курсор `GitS-Cursors`, Neovim, VS Code, Zen,
Logseq, Qt/Dolphin (Kvantum), сборщик темы Telegram, а также `gits-doctor` — отчёт о состоянии системы и опциональная настройка снапшотов btrfs.

## Галерея

![Рабочий стол](docs/img/desktop.jpg)

| | |
|---|---|
| ![Лаунчер](docs/img/launcher.jpg) rofi-лаунчер | ![Меню уведомлений](docs/img/notification-menu.jpg) меню действий уведомления |
| ![wlogout](docs/img/wlogout.jpg) меню выключения | ![SDDM](docs/img/sddm.jpg) экран входа SDDM |
| ![Терминал](docs/img/terminal.jpg) баннер терминала | ![Neovim](docs/img/nvim.jpg) Neovim |
| ![Dolphin](docs/img/dolphin.jpg) Dolphin с циановыми папками | ![Logseq](docs/img/logseq.jpg) Logseq |

Экран блокировки, Plymouth и GRUB не показаны: их нельзя безопасно снять на живой сессии. Виджеты умеют «демо-режим» для скриншотов без
личных данных: `GITS_WIDGETS_DEMO=1 GITS_WEATHER_LOCATION=Tokyo ~/.config/gits-widgets/run.sh restart`.

## Установка

```bash
git clone https://github.com/electrocrem/gits-hyde.git && cd gits-hyde
./install.sh --dry-run          # посмотреть, что будет сделано
./install.sh                    # установка на уровне пользователя, без sudo
./install.sh --apply            # ... и сразу переключить HyDE на тему
./install.sh --system           # темы SDDM + Plymouth + GRUB (нужен sudo)
```

Ключи: `--deps` (поставить пакеты pacman'ом), `--login-guards` (защита от «слепого» входа на ноутбуках с AMD+NVIDIA),
`--telegram` (собрать тему Telegram в `~/Downloads`), `--fix-grub` (см. ниже), `--dry-run`.

Без `--apply` установщик только выводит три команды переключения:

```bash
hyde-shell theme.switch.sh -s "Ghost in the Shell"
hyde-shell waybar.py --set ghost-in-the-shell
hyde-shell animations --set gits
```

**Внимание:** при переключении курсор меняется «на лету», и GTK-приложения (waybar, Zen) могут упасть; watchdog поднимает
waybar за несколько секунд. Лучше закрыть браузер заранее или переключить тему и один раз перезайти в сессию.

После установки запустите `gits-doctor`: он ничего не меняет, только проверяет.

### Экран GRUB «sparse file not allowed»

Если при каждой загрузке GRUB пишет `error: commands/loadenv.c:check_blocklists:289:sparse file not allowed. Press any key
to continue` (корень на btrfs и `GRUB_SAVEDEFAULT=true`), выполните `./install.sh --fix-grub`. GRUB будет всегда грузить
первую запись, а не последнюю выбранную. Подробности в [docs/PITFALLS.md](docs/PITFALLS.md).

## Удаление

```bash
./uninstall.sh        # вернёт бэкапы, удалит созданное, уберёт добавленные блоки
```

Системные части (SDDM, GRUB, Plymouth) не трогаются: команды для отката печатаются в конце.

## Лицензия

Код и конфиги — MIT. Картинки из `assets/` и сторонние файлы ей **не покрываются**, см. [NOTICE.md](NOTICE.md).
