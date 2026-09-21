# gits — «Призрак в доспехах» для Hyprland

Самодостаточный рабочий стол в стиле *Ghost in the Shell* для Hyprland (Lua-конфиг, 0.55+), без dotfiles-фреймворков и переключателей тем:
тёмно-синяя палитра с циановым «люминофором», квадратные углы, тонкие рамки, иероглифы-метки.
Один установщик, один деинсталлятор, каждый заменённый файл сохраняется в бэкап. [English version](README.md)

## Что внутри

Свой конфиг Hyprland (`~/.config/hypr/gits/*.lua`: бинды, правила, 4 раскладки, 5 workflow, анимации `gits`), сервисы сессии как systemd-юниты, waybar (свой макет, переключатель workflow), виджеты рабочего стола (часы, календарь, плеер, погода,
сеть, батарея, нагрузка, to-do, визуализатор звука, редкие глитчи на обоях), hyprlock, темы SDDM / Plymouth / GRUB, GTK-лаунчер (Super+A), буфер обмена, переключатель окон, эмодзи и меню (действия уведомлений, Wi-Fi, Bluetooth, профиль питания), звуки интерфейса, всплывающие панели (управление, плеер, центр уведомлений), OSD громкости/яркости/подсветки, dunst,
wlogout, терминал (баннер с картинкой, в том числе внутри tmux; автозапуск tmux по желанию: `export GITS_TMUX=1`; starship, fzf, bat, btop, lazygit, tmux, yazi), курсор `GitS-Cursors`, Neovim, VS Code, Zen,
Logseq, Qt/Dolphin (Kvantum), сборщик темы Telegram, радио (`gits-radio`, попап на Super+R: обложка, спектр самого радио, слушатели; играет в фоне, работает с медиа-клавишами), обои через awww (`gits-wall --pick`, в том числе анимированные GIF, примерно 2-5% одного ядра и 20-100 МБ в зависимости от петли; выбор запоминается), а также `gits-doctor` — отчёт о состоянии системы и опциональная настройка снапшотов btrfs.

## Галерея

![Попапы один за другим: лаунчер, буфер обмена, горячие клавиши, плеер, микшер](docs/img/demo.gif)

![Рабочий стол](docs/img/desktop.jpg)
Рабочий стол с виджетами (демо-данные, без личного).

![Тайлинг](docs/img/tiling.jpg)
Тайлинг с зазорами и неоновыми рамками: баннер kitty, yazi и Neovim рядом.

![Панель](docs/img/bar.jpg)
Панель: воркспейсы, часы, плеер, нагрузка и температура, Wi-Fi, Bluetooth, громкость, раскладка, режим, счётчик уведомлений, батарея, трей, кнопка питания.

### Лаунчер и быстрые инструменты
| | |
|---|---|
| ![Лаунчер](docs/img/launcher.jpg) лаунчер (Super+A): приложения, настройки, проекты, окна, заметки, калькулятор и веб-поиск в одном поле | ![Калькулятор](docs/img/calculator.jpg) калькулятор в том же поле: `sqrt(1764) * 2`, `2^10`; Enter копирует результат |
| ![Буфер обмена](docs/img/clipboard.jpg) история буфера обмена (Super+V): текст и картинки | ![Окна](docs/img/windows.jpg) переключатель окон (Super+Tab) |
| ![Эмодзи](docs/img/emoji.jpg) эмодзи и символы (Super+запятая): поиск по названию, Enter копирует | ![Клавиши](docs/img/keys.jpg) все горячие клавиши с описанием (Super+/) |
| ![Заметка](docs/img/note.jpg) быстрая заметка (Super+N) в `~/notes/inbox.md` | ![Фокус](docs/img/focus.jpg) таймер фокуса (Super+F): помодоро со счётчиком в панели |

### Панели и меню
| | |
|---|---|
| ![Панель управления](docs/img/control-panel.jpg) панель управления (кнопка питания, Super+Shift+C) | ![Плеер](docs/img/player.jpg) плеер (Super+Shift+M) |
| ![Радио](docs/img/radio.jpg) радио (Super+R): что в эфире, обложка, спектр самого радио, слушатели, включить / выключить, пауза, громкость | ![Микшер](docs/img/mixer.jpg) микшер (Super+Alt+V) |
| ![Уведомления](docs/img/notifications.jpg) центр уведомлений (Super+Shift+N) | ![Wi-Fi](docs/img/wifi.jpg) меню Wi-Fi (клик по иконке в панели) |
| ![Bluetooth](docs/img/bluetooth.jpg) меню Bluetooth (клик по иконке в панели) | ![Настройки](docs/img/settings-menu.jpg) все настройки (Super+I) |
| ![OSD](docs/img/osd.jpg) OSD громкости, яркости, подсветки, тачпада | ![Всплывающие уведомления](docs/img/notification-popups.jpg) всплывающие уведомления (dunst) |
| ![Меню выключения](docs/img/wlogout.jpg) меню выключения (wlogout) |  |

### Терминал и инструменты
| | |
|---|---|
| ![Терминал](docs/img/terminal.jpg) баннер терминала + fastfetch, промпт starship | ![gits-doctor](docs/img/doctor.jpg) отчёт `gits-doctor` |
| ![Заставка Neovim](docs/img/nvim-dashboard.jpg) заставка Neovim | ![Neovim](docs/img/nvim.jpg) Neovim (LazyVim) |
| ![tmux](docs/img/tmux.jpg) tmux с баннером в панели | ![lazygit](docs/img/lazygit.jpg) lazygit |
| ![yazi](docs/img/yazi.jpg) yazi | ![btop](docs/img/btop.jpg) btop |

### Приложения и вход
| | |
|---|---|
| ![Dolphin](docs/img/dolphin.jpg) Dolphin с циановыми папками | ![VS Code](docs/img/vscode.jpg) тема VS Code / Code-OSS |
| ![SDDM](docs/img/sddm.jpg) экран входа SDDM |  |

Экран блокировки, Plymouth, GRUB, а также темы Zen, Logseq и Telegram не показаны: их нельзя безопасно и надёжно снять на живой сессии
(Logseq откроет ваши заметки). Картинки и GIF пересобирает `tools/screenshots.sh` на пустом воркспейсе с демо-данными.

## Установка

```bash
git clone https://github.com/electrocrem/gits.git && cd gits
./install.sh --dry-run          # посмотреть, что будет сделано
./install.sh                    # установка на уровне пользователя, без sudo
./install.sh --system           # темы SDDM + Plymouth + GRUB (нужен sudo)
```

Ключи: `--deps` (поставить пакеты pacman'ом), `--login-guards` (защита от «слепого» входа на ноутбуках с AMD+NVIDIA),
`--telegram` (собрать тему Telegram в `~/Downloads`), `--fix-grub` (см. ниже), `--dry-run`.

Затем **выйдите и войдите заново** (сессия Hyprland): конфиг компоситора читается при входе. Посмотреть его заранее можно прямо в
текущей сессии: `GITS_NESTED=1 Hyprland -c ~/.config/hypr/hyprland.lua` (окно внутри окна, сервисы не запускаются). Если модуль конфига не
загрузился, остальные работают, а ошибка попадает в `~/.local/state/gits/config-errors.log` (и в `gits-doctor`).

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
