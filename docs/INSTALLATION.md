# Instalace a první spuštění QAROS VTK

**Pro první pokus použij [hotový Windows ZIP](https://github.com/HonzaHovora/QAROS_VTK/releases/tag/windows-start-2026-10-14)
a [krátký postup](WINDOWS_QUICKSTART.txt).** Windows sestavení i core testy už prošly.
Níže je plný postup ze zdrojů, potřebný například pro jiné SDK.

Tento návod je pro první pokus na Windows po návratu. Projekt se od začátku instaluje jako **plugin do Sliceru a ParaView**. Oba pluginy spouštějí stejný C++ backend v samostatném procesu. Není potřeba přestavovat Slicer ani ParaView.

První verze přenáší **jeden povrchový model nebo jeden segment**, jeho změny a prostorovou polohu. Backend renderuje stereo barvu a hloubku pro QAROS. Celá hostitelská scéna, CT/MR volume rendering, materiály, barevné mapy a výběr objektů z headsetu ještě nejsou implementované. Běžící proces sám o sobě neznamená připojený headset.

## 1. Co si připravit

- Windows x64, podporovanou NVIDIA GPU a její aktuální ovladač pro použitou verzi QAROS.
- QAROS Hub/viewer a **kompletní SDK**: `include/qar_streaming.h` a původní `bin/`. Samotná hlavička nestačí. SDK musí odpovídat backendu.
- [3D Slicer](https://download.slicer.org/) nebo [ParaView](https://www.paraview.org/download/). Referenční hostitelské testy používají Slicer 5.12.4 a oficiální balík ParaView 5.12.1 na Linuxu; Windows hosty ověříme na tvém PC.
- Pro sestavení backendu: Git, Python 3.9+, CMake 3.20+ a Visual Studio 2022 s **Desktop development with C++**, MSVC v143 a Windows SDK.

Instalace Python pluginů nevyžaduje `pip install vtk` do Sliceru ani ParaView. Každý host používá vlastní VTK. SDK ani jeho DLL se do hostitelské aplikace nekopírují.

## 2. Stáhnout projekt a připravit pluginy

V běžném PowerShellu (cesty uprav podle svého disku):

```powershell
New-Item -ItemType Directory -Force C:\dev | Out-Null
cd C:\dev
git clone https://github.com/HonzaHovora/QAROS_VTK.git
cd QAROS_VTK
py -3 scripts/package_plugins.py
```

Pokud už checkout máš, nejdřív v něm proveď `git pull --ff-only` a pak příkaz s Pythonem. Soukromý repozitář vyžaduje přihlášení ke GitHubu s oprávněním k projektu.

Vzniknou:

- `package/QAROS-VTK-plugins/slicer/` — kompletní Slicer modul;
- `package/QAROS-VTK-plugins/paraview/` — kompletní ParaView plugin;
- `package/QAROS-VTK-plugins.zip` — přenositelný archiv obou složek.

Archiv je pro ruční rozbalení. **Není to balíček pro Slicer Extensions Manager.** Pro standardní sestavení extension je už připravený `integrations/slicer/CMakeLists.txt`; ten vyžaduje vývojový build Sliceru. Na první instalaci není potřeba.

Hotový ZIP je také mezi artefakty úspěšného workflow **Build and test**, pod názvem `QAROS-VTK-python-plugins` (uchování 30 dní). Příkaz výše ho kdykoli vytvoří z aktuálního checkoutu.

## 3. Sestavit backend na Windows

Jednorázově připrav vcpkg. Pokud už máš jeho samostatný checkout, použij jeho cestu:

```powershell
git clone https://github.com/microsoft/vcpkg.git C:\dev\vcpkg
C:\dev\vcpkg\bootstrap-vcpkg.bat -disableMetrics
```

V kořeni `QAROS_VTK` nastav skutečnou složku SDK. Níže je příklad `D:\install`; musí přímo obsahovat `include` a `bin`, případně zvol jeho podadresář.

```powershell
$qarSdk = 'D:\install'
Test-Path "$qarSdk/include/qar_streaming.h"
Test-Path "$qarSdk/bin/qar-streaming-c.dll"
cmake -S . -B build-windows-release -G "Visual Studio 17 2022" -A x64 "-DCMAKE_TOOLCHAIN_FILE=C:/dev/vcpkg/scripts/buildsystems/vcpkg.cmake" "-DVCPKG_OVERLAY_TRIPLETS=$PWD/cmake/triplets" -DVCPKG_TARGET_TRIPLET=x64-windows-release -DQARVTK_BUILD_SENDER=ON "-DQAROS_SDK_ROOT=$qarSdk"
```

Oba `Test-Path` musí vrátit `True`. Po úspěšném configure:

```powershell
cmake --build build-windows-release --config Release --parallel 4
ctest --test-dir build-windows-release -C Release --output-on-failure
.\build-windows-release\Release\qarvtk-preview.exe --frames 300
.\build-windows-release\Release\qarvtk-sender.exe --sdk-info
```

Po každém příkazu zkontroluj, že skončil bez chyby. První kompilace VTK může trvat přes hodinu a potřebuje dost místa na disku; další buildy využijí cache. Triplet sestavuje pouze Release. Původní Windows CI vypršelo při kompilaci Debug VTK; aktuální stav plného buildu je v [GitHub Actions](https://github.com/HonzaHovora/QAROS_VTK/actions/workflows/windows-native.yml).

Preview má zobrazit zelenou kostku. Nevyžaduje Hub ani SDK runtime. GPU test vyžaduje funkční OpenGL 3.3, proto ho spouštěj v místní grafické relaci. `--sdk-info` vypíše fingerprint hlavičky, typ API a `plugin_protocol: 1`.

Při přesunu backendu zkopíruj **celou složku `Release` s DLL**, ne samotné EXE. SDK ponech zvlášť a kompletní. Binárky z CI sestavené jen s veřejnou hlavičkou nemusí odpovídat tvému SDK; plugin nesoulad odmítne.

## 4. Slicer — doporučený první pokus

1. Spusť Slicer. V **Edit → Application Settings → Modules → Additional module paths** přidej `C:/dev/QAROS_VTK/package/QAROS-VTK-plugins/slicer` a restartuj Slicer.
2. Vyber modul **QAROS → QAROS Streaming**.
3. Načti model nebo segmentaci a vyber ji. U segmentace vyber jeden segment. Pro první pokus použij malý model poblíž počátku souřadnic.
4. **Sender executable** nastav na `C:/dev/QAROS_VTK/build-windows-release/Release/qarvtk-sender.exe`. **QAROS SDK folder** nastav na svou složku SDK.
5. U nového Hub SDK zadej **Hub pairing code** při prvním spojení. Identita se uloží mimo repozitář do `%LOCALAPPDATA%/QAROS_VTK/onboarding-id.txt`. Kód se po pokusu vymaže z políčka a plugin ho neukládá do nastavení. Volitelně vyplň Hub host.
6. U staršího SDK 2540 se používá session invite: případně vyber **Legacy invite**, zvol **Legacy viewer** (`visualizer` nebo `quest`). Pole Hub identity/kód se u něj nepoužívají.
7. Klikni **Start streaming**. U nového API otevři aplikaci/volume v Hub vieweru. Sleduj **Sender log**; chyba GPU, SDK nebo připojení je vidět zde.
8. Po změně modelu stiskni **Update surface**. Volitelně zapni aktualizaci každou sekundu; u velkých segmentací může export zdržovat UI.
9. **Stop streaming** požádá backend o ukončení. Během blokujícího SDK připojení to může trvat až přibližně 65 sekund. Při zavření Sliceru se neukončený proces po krátkém čekání ukončí vynuceně.

Transformace rodičů MRML se aplikují automaticky; jednotky jsou RAS milimetry a převod do QAROS metrů provádí backend. Nastavení scénu automaticky nevystředí. Model mimo počátek může být mimo záběr/app volume.

Bez SDK můžeš ověřit načtení pluginu a **Export surface to file**. Export má fungovat i bez senderu. Vzniklý VTP lze otevřít lokálně:

```powershell
.\build-windows-release\Release\qarvtk-preview.exe --scene C:\data\model.vtp --ras --meters-per-unit 0.001
```

## 5. ParaView — skutečný plugin přes Plugin Manager

1. Spusť ParaView s lokálním **built-in** připojením. Tato verze pluginu nepodporuje `pvserver` ani MPI.
2. **Tools → Manage Plugins → Local Plugins → Load New**: vyber `package/QAROS-VTK-plugins/paraview/QarosVTKPlugin.py`. Nech vedle něj ostatní `.py` soubory. Volitelně zapni **Auto Load**.
3. Vytvoř např. **Sources → Sphere**, klikni **Apply** a vyber zdroj. Přidej filtr **QAROS Streaming** přes vyhledávání filtrů.
4. Nastav **Sender Executable**, **SDK Folder** a **Metres Per Unit**. Pro data v metrech je to `1`, pro milimetry `0.001`. Klikni **Apply**.
5. Pro nové Hub API nejdřív jednou proveď pairing přes Slicer nebo terminál (níže). **Identity File** ponech prázdné pro společnou výchozí identitu. Pro starší SDK nastav případný **Legacy Invite File** a **Legacy Target**.
6. Klikni **Start streaming**. **Show sender log** vypíše stav a log do výstupu ParaView. **Stop streaming** ukončí proces. Před změnou SDK/cest/měřítka nejprve zastav streaming.
7. Změna vstupu filtru a jeho přepočet publikuje nový povrch pro běžící sender. Nepřenáší se změny provedené jen v části **Display**. Pro posun/otočení/měřítko vlož před QAROS filtr standardní **Transform** filtr.

Pairing pro ParaView z PowerShellu, pokud nepoužiješ Slicer:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA/QAROS_VTK" | Out-Null
py -3 scripts/run_sender.py --exe build-windows-release/Release/qarvtk-sender.exe --sdk D:/install --identity "$env:LOCALAPPDATA/QAROS_VTK/onboarding-id.txt"
```

Kód zadej až na výzvu programu. Potom program ukonči Ctrl+C a identitu použij v pluginu. ParaView nemá pole pro pairing kód, aby se kód neukládal do `.pvsm` stavu. Po expiraci/zrušení identity zopakuj párování. Pro první test používej jeden sender současně.

## 6. Linux

Pro ParaView použij oficiální binární balík z webu projektu. Ubuntu 24.04 balíček ParaView 5.11.2 se systémovým Pythonem 3.12 má chybu loaderu Python pluginů (`inspect.getargspec`); samotný exportní helper v něm funguje, plugin se ale nenačte. Neupravuj kvůli tomu systémový Python.

Slicer i ParaView mají Linuxové verze. Python pluginy se instalují stejnými kroky. Backend:

```bash
sudo apt-get update
sudo apt-get install -y cmake ninja-build g++ libvtk9-dev libglfw3-dev libgl1-mesa-dev
python3 scripts/package_plugins.py
bash scripts/build-linux.sh /cesta/k/linuxovemu/QAROS-SDK
```

Pro streaming je potřeba Linuxové SDK s `bin/libqar-streaming-c.so`, podporovaná GPU a X11/GLX. Windows DLL na Linuxu nefungují. Bez Linuxového SDK lze sestavit preview pomocí `bash scripts/build-linux.sh` a ověřit hostitelské pluginy/export. Výchozí Hub identita je `$XDG_STATE_HOME/QAROS_VTK/onboarding-id.txt`, případně `~/.local/state/QAROS_VTK/onboarding-id.txt`.

## 7. Jak poznat úspěch a co poslat při chybě

První test je úspěšný, až když uvidíš správně velký model ve vieweru, reaguje na pohyb hlavy, **Update surface** změní geometrii a **Stop streaming** ukončí sender bez pádu hostitele. Zvlášť ověř hloubku/okluzi a polohu na skutečném zařízení.

Při chybě pošli: verzi Sliceru/ParaView, commit repozitáře, výstup `--sdk-info`, poslední chybu z logu a typ GPU/ovladače. Log je v dočasné složce `qarvtk-*`, kterou ukazuje stav pluginu. Neukládej do Gitu pairing kódy, onboarding identitu, pozvánky ani pacientská data. Soukromý pracovní VTP plugin odstraní při úklidu; po pádu aplikace může zůstat v dočasné složce.

| Projev | Co zkontrolovat |
| --- | --- |
| Plugin není v nabídce | Správná složka s celým balíčkem, restart Sliceru / načtení `.py` v Plugin Manageru ParaView. |
| SDK does not match | Překonfigurovat a sestavit sender proti hlavičce z téhož SDK jako runtime. |
| Sender is too old | Znovu sestavit backend z aktuálního checkoutu; plugin potřebuje protokol 1. |
| Missing runtime / DLL | Kompletní SDK a kompletní složka Release s DLL; ne míchat verze. |
| OpenGL/GPU identity chyba | Ovladač, podporovaná GPU, stejný adaptér pro OpenGL a QAROS; Linux X11. |
| No viewer request / timeout | Spuštěný Hub/viewer, správné párování/invite, otevřená app volume, síť. |
| Model není vidět | Jednotky, poloha vůči počátku, platný polygonální povrch, velikost vůči app volume. |

Aktuální stav ověření a známé mezery: [VALIDATION.md](https://github.com/HonzaHovora/QAROS_VTK/blob/main/docs/VALIDATION.md). Pluginy nejsou zatím publikované v oficiálních katalozích. Toto je instalovatelný vývojový prototyp, nikoli hotová medicínská aplikace.

