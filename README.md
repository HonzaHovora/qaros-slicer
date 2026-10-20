# QAROS × VTK

Pluginy pro **ParaView a 3D Slicer** a OpenGL přenos do QAROS.

**Aktualizace r7: oprava Stop a Visualizer + HoloLens pro QAROS 0.9.0-dev.2927+f291e404.** Zavři Slicer,
dej Fetch/Pull checkoutu s touto aktualizací a spusť `UPDATE-LIVE-PLUGIN.cmd`.
Instalaci najde v registru Windows, obvykle
`C:\Program Files\Quaternar\QAROS`, ověří SDK a zálohuje předchozí plugin.
Ve Sliceru otevři **QAROS Live Renderer**, ponech **Stream to → Visualizer + headset**
a první připojení povol v okně QAROS Hubu. V QAROSu spusť jeden přijímač
Visualizeru a připoj HoloLens; brýle lze připojit i za běhu streamu.
Každý objem má samostatný sender pro každý cíl. Brýle dostávají obraz podle
vlastní polohy hlavy, společné řezové panely jsou viditelné na obou cílech.
Volby **Headset only** a **Visualizer only** umožňují přenášet jen do jednoho zařízení.
R7 zatím nebyla ověřena na fyzickém headsetu; [postup testu brýlí](docs/HEADSET_STREAMING.md).
**Panely jsou zapnuté a běžný start už nečeká na diagnostický dotaz po každém okně.**
Volbu **Test panel startup step by step** nech pro běžné použití vypnutou.
V dev.2927 může po Stop/Start přestat fungovat obraz a obnovený receiver může
vyvolat problém s panely. Ověřený postup obnovy je receiver odebrat a vytvořit nový.
**R7 opravuje chybu našeho ukončování:** plugin volal `qar_runtime_destroy`,
které ukončuje runtime. Nyní uvolňuje pouze vlastní handle přes
`qar_runtime_handle_destroy`; sdílený QAROS má zůstat běžet. Opraven je Live
bridge i zdroj standalone senderu. Nový Python odmítne starou DLL bez této
opravy. Zda tím mizí i pády panelů a potíže Stop/Start, musí potvrdit živý test.
Starší dev.2540 má jiné API; samotné přepsání cesty v původním pluginu nestačí.
[Postup a ověření](docs/QAROS_DEV2927_UPDATE.md).

**Experiment: vlastní QAROS kostka pro každý objem.** Výchozí volba
**Separate QAROS workspace for each volume** vytvoří samostatné pracovní objemy
vedle sebe, každý s vlastním streamem, měřítkem a živým ROI. Sdílejí jednu relaci
a v r6 je může současně sledovat jeden Visualizer a jeden headset.
Vypnutím volby se přenáší celá scéna společně.
Nový aktualizátor výše obsahuje tuto podporu i DLL ABI 5 pro nové SDK.
Původní verze používala SDK v `D:/install`. Popis a omezení jsou v
[postupu pro více objemů](docs/MULTIPLE_VOLUMES.md).

**R17: živé náhledy řezů jako samostatné QAROS panely.**
Volba **Show slice views as panels (preview only)** přenáší hotové GPU obrazy
viditelných řezů, včetně videa a časových sekvencí. Výchozí limit je 15 FPS
na panel, volitelně 5/10/15/30. Při pomalém příjemci vítězí nejnovější snímek.
Panely se objeví pod 3D objemem; ovládání zatím zůstává ve Sliceru.
Přenos panelů má vlastní SDK vlákno a zachycené chyby náhledů neukončí stereo
stream. Před pádem přijímacího procesu QAROS to nechrání; omezení dev.2927 je výše.
Na cílové NVIDIA kartě je potřeba ověřit obraz a náklady dalších enkodérů.

R16 pracovní prostor podle rozsahu scény zůstává zachovaný.
Při Start se nastaví kvádr podle viditelných objektů, jejich natočení a měřítka.
Zapnuté **Center and fit** vystředí scénu a nastaví nejdelší hranu na 65 cm;
vypnuté zachová skutečnou velikost a polohu. Rozměry zobrazí řádek **Workspace**.
R15 maximalizace a návrat do původního rozložení jsou potvrzené na cílovém PC.
Sekundová diagnostika výkonu zůstává; příčina celého poklesu FPS není určená.
[Dosavadní zjištění a další měření](docs/FPS_DIAGNOSTICS.md).

R13 umístění přes app_pose/app_scale a poloviční hloubka zůstávají zachované. Modul přebírá GPU
výstup živého 3D pohledu, včetně hostitelských shaderů a ROI ořezu objemu.
Scénu neexportuje. Windows knihovna nepřidává do Sliceru další VTK ani Qt.
Natočení podle pohledu Sliceru, vystředění i měřítko nyní nastavuje SDK.
Kamera přebírá SDK pózy přímo, bez dalšího převodu os či velikosti scény.
Při barvě 1920 × 1080 má depth 960 × 540 pro každé oko. Volba Render resolution
100/75/50 % mění skutečnou velikost hostitelského renderu; modul i log zobrazují
rozměry renderu, přenášené barvy, hloubky a desktopového pohledu.
Zachovává dva rendery na stereo snímek z r12 a původní desktopové GPU textury.
Orientace v r13 je na cílovém PC potvrzená. Při 50 % renderu FPS postupně
kleslo z přibližně 19 na 13; růst času uvnitř Render() ještě nemá určenou příčinu.
[Postup pro první test](docs/WINDOWS_LIVE_QUICKSTART.txt).

Dosavadní **QAROS Streaming** používá samostatný renderer r9 a export VTP/VTM;
ParaView zatím zůstává u povrchového exportu. Další prioritou je ověřit přímý
Slicer přenos s náhledy řezů, pak napojit renderer ParaView a původní Qt ovládání.
[Architektura a podmínky ověření](docs/ARCHITECTURE.md).

**První test přes GitHub Desktop:** po Fetch/Pull spusť `START-PREVIEW.cmd`
v kořeni checkoutu. Hotový Windows ZIP se stáhne spolu s repozitářem; skript ho
ověří, rozbalí a otevře zelenou kostku. [Postup pro D:\QAROS_VTK](docs/WINDOWS_DESKTOP.md).

Aktuální balíček pro GitHub Desktop používá session API a přesně odpovídá
hlavičce `022c40b6…` ze stávajícího SDK v `D:\install`. Použij **Legacy viewer →
visualizer**; Hub pairing code nech prázdný. Podrobnosti jsou v uvedeném postupu.
R7 už má na testovacím PC potvrzené správné transformace. Diagnostická r8
naměřila asi 20,3 nových stereo snímků za sekundu: vykreslení obou očí trvá
4,0 ms, čekání na připravenost dalšího snímku od QAROS 42,6 ms. Převzetí textur
je rychlé (0,01 ms). Další diagnostika musí rozlišit příčinu čekání uvnitř
QAROS/mixeru/přijímače; podrobnosti jsou v [VALIDATION.md](docs/VALIDATION.md).
Údaj přibližně 44 FPS ve Visualizeru měří jinou část přenosu. Dosažení cíle
60 FPS ještě není potvrzené. Před rozbalením zavři Slicer i Visualizer;
cesty k pluginu a senderu zůstávají stejné. Logy lze zabalit pomocí `COLLECT-LOGS.cmd`.
Samostatné stažení je také v [GitHub Release](https://github.com/HonzaHovora/QAROS_VTK/releases/tag/windows-start-2026-10-15-session022c40b6r17).
Původní [moderní Hub varianta](https://github.com/HonzaHovora/QAROS_VTK/releases/tag/windows-start-2026-10-14)
zůstává dostupná pro jiné SDK. Každý sender vyžaduje odpovídající kompletní runtime.

**Začni zde: [instalace na Windows, instalace pluginů a první pokus](docs/INSTALLATION.md).**

**Stav: prototyp před ověřením s reálným QAROS Hubem a headsetem.** GPU cesta se
ověřuje na Linuxu s Mesa. Úspěšný test není potvrzení funkčnosti NVIDIA enkodéru,
transportu ani výsledného obrazu v headsetu. Aktuální sestavení a jejich výsledky:
[GitHub Actions](https://github.com/HonzaHovora/QAROS_VTK/actions).

## Co už je v repozitáři

- C++17 jádro: stereo, asymetrické projekce, souřadnice a kontrola layoutu.
- VTK/OpenGL renderer a samostatný náhled bez QAROS SDK.
- GPU kopírování barvy a hloubky do textur QAROS bez čtení obrazu na CPU.
- Odesílač pro Windows/WGL a Linux/GLX: nový Hub onboarding i starší SDK 2540.
- QAROS Live Renderer pro Slicer: přímý hostitelský stereo render a Windows
  knihovna bez VTK/Qt, živé změny scény a ROI, jeden GPU Composite objem.
- Slicer plugin: model/segment/CT/MR nebo viditelná 3D scéna, barvy, osvětlení,
  volume transfer funkce, automatické vystředění, Start/Stop, aktualizace a log.
- ParaView Python plugin přes Plugin Manager: filtr QAROS Streaming, Start/Stop
  a publikování změn pipeline. První Hub pairing se provede ve Sliceru nebo terminálu.
- Samostatné složky pluginů, ZIP balíček a základ CMake extension pro Slicer.
- Znovunačtení exportu za běhu (`--watch`), kontrola shody SDK, skripty pro build a CI.

Původní modul QAROS Streaming předává scénu přes atomicky publikovaný `.vtm` a neměnné VTP/VTI soubory;
ParaView používá `.vtp`. Video i hloubka zůstávají na GPU backendu. VTK/Qt
hostitele se nemíchá s knihovnami senderu. R9 podporuje jeden skalární objem
(Composite, bez ROI ořezu) a neprůhledné modely/segmenty. CT/MR převezme nastavení
ze Slicer Volume Rendering. Popisky, řezy a interakce z headsetu zbývají.
[Krátký postup pro modely a CT/MR](docs/WINDOWS_SESSION_QUICKSTART.txt).

## Rychlé spuštění na Linuxu

Ubuntu 24.04, X11, CMake, C++ kompilátor:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build libvtk9-dev libglfw3-dev libgl1-mesa-dev xvfb
git clone https://github.com/HonzaHovora/QAROS_VTK.git
cd QAROS_VTK
bash scripts/build-linux.sh
./build-linux/qarvtk-preview
```

Na stroji bez obrazovky lze ověřit GPU operace přes software OpenGL:

```bash
xvfb-run -a env LIBGL_ALWAYS_SOFTWARE=1 bash scripts/build-linux.sh
xvfb-run -a env LIBGL_ALWAYS_SOFTWARE=1 ./build-linux/qarvtk-preview --hidden --frames 5
```

Zelená krychle má hranu 0,4 m a střed v počátku. Náhled má kameru 2 m před ní.
VTK, ParaView i Slicer mají linuxové verze. Náš dostupný runtime QAROS
`0.9.0-dev.2540+1ed038e4` je balík pro Windows: jeho DLL na Linuxu nespustíme.
Linuxové připojení k Hubu vyžaduje odpovídající nativní QAROS SDK/runtime.

## Přenos na Windows

Postup v [docs/INSTALLATION.md](docs/INSTALLATION.md). Potřeba: Visual Studio 2022 s C++,
CMake, Git, Python a vcpkg; pro QAROS také kompletní odpovídající SDK a podporovaná
NVIDIA karta. Ve složce repozitáře:

```powershell
./scripts/build-windows.ps1 -VcpkgRoot C:/dev/vcpkg -SdkRoot C:/QAROS
./build-windows/Release/qarvtk-preview.exe
python scripts/run_sender.py --exe build-windows/Release/qarvtk-sender.exe --sdk C:/QAROS --preview --frames 300
```

`C:/QAROS` zde znamená složku obsahující **include/** a **bin/**. První build VTK
přes vcpkg trvá déle. Header se bere z lokálního SDK; nekopírujte nový veřejný
header do staršího balíku s DLL.

## ParaView a Slicer

Pluginy připravíš bez kompilace hostitelů:

```powershell
py -3 scripts/package_plugins.py
```

Složku `package/QAROS-VTK-plugins/slicer` přidej do Additional module paths.
Soubor `package/QAROS-VTK-plugins/paraview/QarosVTKPlugin.py` načti přes Plugin
Manager ParaView. Podrobnosti jsou v instalačním návodu; pomocné exportní API
zůstává popsané v [docs/HOST_INTEGRATIONS.md](docs/HOST_INTEGRATIONS.md).
Pro ruční export ze Sliceru platí world RAS milimetry:

```powershell
python scripts/run_sender.py --exe build-windows/Release/qarvtk-sender.exe --sdk C:/QAROS --scene C:/data/surface.vtp --ras --meters-per-unit 0.001 --watch --preview
```

Další podklady:

- [Architektura, formáty a omezení](docs/ARCHITECTURE.md)
- [Ověření a další práce](docs/VALIDATION.md)
- [Rozdíly verzí SDK](docs/SDK_COMPATIBILITY.md)

SDK runtime DLL, pozvánky a párovací identity nejsou součástí repozitáře.
Pro reprodukovatelné sestavení session senderu je uložená přesná dodaná hlavička
v `ci/sdk-headers/`; do instalovaného SDK ji nekopíruj.



