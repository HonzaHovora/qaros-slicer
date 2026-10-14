# První spuštění přes GitHub Desktop

Tento postup používá již přihlášený GitHub Desktop a checkout `D:\QAROS_VTK`.
Slicer je nainstalovaný v `D:\3D Slicer 5.12.4`.

1. V GitHub Desktop otevři repozitář QAROS_VTK na větvi main.
2. Klikni **Fetch origin**, potom **Pull origin**, pokud se nabízí.
3. Spusť `D:\QAROS_VTK\START-PREVIEW.cmd`.
4. Skript ověří přiložený ZIP, rozbalí ho do `package\windows-start` a otevře náhled zelené kostky.

Balíček je skutečný soubor v `downloads/`, nikoli Git LFS pointer nebo odkaz.
Tento postup nepotřebuje přihlášení v prohlížeči, instalaci GitHub CLI ani kompilátor.
Podporovaná grafika a Visual C++ Runtime x64 jsou stále potřeba.
Při chybě pošli text z otevřeného okna; při hlášení o chybějícím ZIPu dokonči Pull origin.

## Plugin ve Sliceru

Po prvním spuštění náhledu přidej v **Edit → Application Settings → Modules →
Additional module paths** složku:

```text
D:/QAROS_VTK/package/windows-start/plugins/slicer
```

Restartuj Slicer a otevři **QAROS → QAROS Streaming**. Nainstaluj pouze tuto kopii
modulu; pokud už máš stejný modul přidaný z `D:/QAROS_VTK-bin/plugins/slicer`,
nahraď starou cestu novou.

- Sender executable: `D:/QAROS_VTK/package/windows-start/Release/qarvtk-sender.exe`
- Testovací model: `D:/QAROS_VTK/package/windows-start/sample/cube-200mm.vtp`
- QAROS SDK folder: skutečný adresář tvého kompletního SDK, obsahující include a bin.

Nejdřív zkontroluj shodu SDK podle `package/windows-start/ZACNI_ZDE.txt`; v jeho
PowerShell příkladu nastav `$kit = 'D:\QAROS_VTK\package\windows-start'`.
SDK, Hub a viewer nejsou součástí repozitáře. Přiložený sender používá moderní
Hub API; starší SDK 2540 s ním není kompatibilní.

Balíček odpovídá testovacímu vydání windows-start-2026-10-14. Nativní Windows
sestavení a core testy prošly, skutečný NVIDIA/Hub/headset přenos zůstává
k ověření. První verze přenáší jeden povrchový model.
