# Перенос настроек VS Code: macOS → Windows 11

Пакет содержит настройки, горячие клавиши и список расширений с текущего Mac,
адаптированные для Windows 11.

## Что внутри

| Файл | Назначение |
|------|------------|
| `settings.windows.json` | Настройки VS Code, адаптированные под Windows (установить как `settings.json`) |
| `keybindings.windows.json` | Горячие клавиши под Windows (`Cmd` → `Ctrl`) |
| `extensions.txt` | 158 расширений с версиями (формат `publisher.name@version`) |
| `install-settings.ps1` | Копирует настройки и клавиши в профиль VS Code с бэкапом |
| `install-extensions.ps1` | Устанавливает все расширения из `extensions.txt` |
| `install-all.ps1` | Запускает оба скрипта подряд |
| `open-settings-folder.bat` | Открывает папку настроек VS Code в Проводнике |
| `settings.macos-original.json` | Исходные настройки с Mac (как есть, для справки) |
| `keybindings.macos-original.json` | Исходные горячие клавиши с Mac |

## Быстрый старт

1. Скопируйте папку `vscode-transfer-win11` на десктоп (например, в `C:\Temp`).
2. Откройте в этой папке PowerShell (Shift + правый клик → «Открыть окно PowerShell здесь»).
3. Выполните:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-all.ps1
```

4. Перезапустите VS Code.

Если PowerShell блокирует запуск скриптов, разовая команда выше с `-ExecutionPolicy Bypass`
обойдёт это без изменения системных политик.

### Важно: команда `code` в PATH

Скрипт установки расширений использует консольную команду `code`. Если она не найдена:

1. Откройте VS Code.
2. `Ctrl+Shift+P` → `Shell Command: Install 'code' command in PATH`.
3. Перезапустите PowerShell и повторите запуск.

## Раздельный запуск

```powershell
# Только настройки и горячие клавиши
powershell -ExecutionPolicy Bypass -File .\install-settings.ps1

# Только расширения (последние совместимые версии)
powershell -ExecutionPolicy Bypass -File .\install-extensions.ps1

# Только расширения строго тех версий, что на Mac (может частично не установиться)
powershell -ExecutionPolicy Bypass -File .\install-extensions.ps1 -PinVersions
```

Установка 158 расширений занимает ориентировочно 10–25 минут в зависимости от сети.
Расширения, которые не удалось поставить, будут записаны в `extensions-failed.txt`.

## Ручной способ (без скриптов)

1. Нажмите `open-settings-folder.bat` — откроется `%APPDATA%\Code\User`.
2. Замените `settings.json` содержимым `settings.windows.json`.
3. Замените `keybindings.json` содержимым `keybindings.windows.json`.
4. Установите расширения командой в PowerShell:

```powershell
Get-Content .\extensions.txt | ForEach-Object {
    $id = ($_ -split '@')[0]
    if ($id.Trim()) { code --install-extension $id --force }
}
```

## Что адаптировано под Windows

- `editor.fontFamily`: `Monaco` → `Consolas, 'Courier New', monospace`
  (шрифта Monaco в Windows нет).
- Горячая клавиша `cmd+alt+e` → `ctrl+alt+e`
  (команда `sourcecraft-code-assist.popoutButtonClicked`).
- Убрана строка `sync.gist` — иначе расширение Settings Sync при старте попыталось бы
  подтянуть старый gist и перезаписать настройки.
- `terminal.integrated.defaultProfile.windows` уже был выставлен в `Command Prompt`,
  оставлен без изменений.

Всё остальное перенесено один в один: темы, форматирование, автосохранение,
настройки терминала, GitLens, Roo Code / SourceCraft, Live Server, Emmet и т.д.

## Примечания

- Часть расширений из списка ориентирована на macOS и на Windows просто не активируется
  (например, `swiftlang.swift-vscode`, `nmustakin.vscuda`). Они не мешают работе,
  их можно удалить вручную.
- В настройках есть `"files.associations": { "*.json": "shellscript" }` — это осознанная
  настройка с Mac, она перенесена как есть. Если JSON-файлы начнут подсвечиваться
  как shell-скрипты, удалите эту строку.
- `roo-cline.allowedCommands` и `sourcecraft-code-assist.allowedCommands` ссылаются на
  `npm`, `tsc`, `git` — для их работы на Windows должны быть установлены Node.js и Git.

## Откат

При запуске `install-settings.ps1` прежние файлы сохраняются в папку
`backup-ГГГГММДД-ЧЧММСС` рядом со скриптом. Чтобы вернуть всё как было, скопируйте
`settings.json` и `keybindings.json` из бэкапа обратно в `%APPDATA%\Code\User`.

## Альтернатива: встроенная синхронизация

Если на десктопе войти в VS Code тем же аккаунтом GitHub или Microsoft, что на Mac,
и включить Settings Sync (`Ctrl+Shift+P` → `Settings Sync: Turn On`), настройки,
клавиши и расширения подтянутся автоматически. Этот пакет нужен, если аккаунт другой,
синхронизация отключена или требуется разовый перенос без привязки к аккаунту.
