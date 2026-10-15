# První spuštění přes GitHub Desktop

Tento postup používá již přihlášený GitHub Desktop a checkout `D:\QAROS_VTK`.
Slicer je nainstalovaný v `D:\3D Slicer 5.12.4`.

Při aktualizaci nejdřív zastav stream a zavři Slicer, Visualizer i náhled kostky.

1. V GitHub Desktop otevři repozitář QAROS_VTK na větvi main.
2. Klikni **Fetch origin**, potom **Pull origin**, pokud se nabízí.
3. Spusť `D:\QAROS_VTK\START-PREVIEW.cmd`.
4. Skript ověří přiložený ZIP, rozbalí ho do `package\windows-start` a otevře náhled zelené kostky.

Balíček je skutečný soubor v `downloads/`, nikoli Git LFS pointer nebo odkaz.
Tento postup nepotřebuje přihlášení v prohlížeči, instalaci GitHub CLI ani kompilátor.
Podporovaná grafika a Visual C++ Runtime x64 jsou stále potřeba.
Při chybě pošli text z otevřeného okna; při hlášení o chybějícím ZIPu dokonči Pull origin.

## Přímý renderer Sliceru: r14

Po aktualizaci otevři **QAROS → QAROS Live Renderer**. Modul používá první
3D pohled Sliceru. Host bridge DLL je
`D:/QAROS_VTK/package/windows-start/Release/qarvtk-host.dll`, SDK `D:/install`
a Viewer `visualizer`. Přenos spustíš tlačítkem **Start live streaming**.
Preset, viditelnost a ROI se mění živě, bez Update scene.
[Celý postup a rozsah testovací verze](WINDOWS_LIVE_QUICKSTART.txt).

Předchozí QAROS Streaming musí být zastavený. První verze podporuje jeden
VTK GPU Composite objem a neprůhledné povrchy; ROI ořez je podporovaný.
R12 u standardního vykreslování spojuje barvu a hloubku do jednoho průchodu pro
každé oko, uchovává desktopové textury a potlačuje automatický redraw při změně
kamery. Neověřené vlastní renderovací průchody mají původní doplňkovou cestu.
R13 předává natočení, umístění i velikost SDK pomocí app_pose/app_scale.
Nech zapnuté **Use Slicer viewing direction at Start**. Depth má poloviční
šířku i výšku oproti barvě. **Render resolution** 100/75/50 % mění velikost
skutečného renderu; 50 % používá čtvrtinu pixelů. Rozměry se zobrazují v modulu.
R11 oprava opakovaného snímku a měření zůstávají zachované.
R14 doplňuje sekundová měření snímků, aktivního okna a volitelná data NVIDIA GPU.
Pro další měření nastav 50 %, střídej aktivní okno po 20–30 sekundách bez změny
pohledu a scény, po 2–3 minutách zastav stream a spusť COLLECT-LOGS.cmd.
ZIP zahrne host-bridge.log, host-python.log a host-system.log.
Orientace je potvrzená; příčinu postupného poklesu FPS tato diagnostika teprve hledá.

## Instalace modulu a dosavadní exportní cesta

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
- QAROS SDK folder: `D:/install` (stávající kompletní SDK s include a bin).
- Legacy viewer: `visualizer`.
- Legacy invite, Hub pairing code a Hub host: prázdné.

Podrobný postup pro první použití Sliceru je v
[WINDOWS_SESSION_QUICKSTART.txt](WINDOWS_SESSION_QUICKSTART.txt) a v rozbaleném
`package/windows-start/ZACNI_ZDE.txt`. Přiložený sender používá **session API**
a odpovídá přesné hlavičce z existujícího SDK:
`022c40b670f87a066664c37daeb06da525db37fffdf5810e72cff8a5b81e677d`.
Plugin tuto shodu ověřuje automaticky. Toto SDK neposkytuje nové Hub párování;
pole Hub identity se nepoužívá. SDK runtime a viewer nejsou součástí balíčku.

Balíček odpovídá testovacímu vydání `windows-start-2026-10-15-session022c40b6r13`.
Nový modul QAROS Live Renderer používá postup uvedený výše. Následující popis
se týká zachovaného modulu QAROS Streaming s exportem r9.
R9 přidává osvětlení, barvy, viditelné modely/segmenty a jeden CT/MR objem ze Sliceru.
V modulu zvol **Selected object** nebo **Visible 3D scene (first view)** a nech
zapnuté **Center and fit**. Pro CT/MR nejdřív nastav preset ve **Volume Rendering**;
po změnách použij **Update scene**. Podrobnosti a omezení jsou v krátkém postupu výše.

R7/r8 mají na testovacím PC potvrzený přenos a transformace. Nové scény a objemy
je ještě potřeba ověřit v cílovém Visualizeru. Diagnostika `PERF`/`PACING` z r8
zůstává zachovaná; toto vydání nepředstavuje ověřené zvýšení FPS.

## Když po zobrazení volume přenos spadne

Po pádu spusť `D:\QAROS_VTK\COLLECT-LOGS.cmd`. Slicer může zůstat otevřený.
Skript vytvoří ZIP v `D:\QAROS_VTK\diagnostics` a vybere ho v Průzkumníku.
Přilož tento ZIP do chatu. Obsahuje poslední tři logy senderu, informace o
nainstalované verzi a související záznamy pádů z Windows. Modely ani pozvánky
do balíčku nekopíruje. Nic automaticky neodesílá a nepotřebuje správce.

Napiš také, zda zmizí celé okno Visualizeru, nebo jen pracovní volume. Pokud
Slicer zůstane otevřený, připiš číslo z hlášení `Sender exited with code ...`
nad polem Sender log. To rozliší chybu senderu od pádu vieweru.


