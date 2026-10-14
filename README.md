# QAROS × VTK

Pluginy pro **ParaView a 3D Slicer** se společným VTK/OpenGL backendem pro QAROS.
Instalují se do běžných hostitelských aplikací; backend renderuje v samostatném
procesu. QAROS už OpenGL podporuje; Vulkan není součástí této implementace.

**První test přes GitHub Desktop:** po Fetch/Pull spusť `START-PREVIEW.cmd`
v kořeni checkoutu. Hotový Windows ZIP se stáhne spolu s repozitářem; skript ho
ověří, rozbalí a otevře zelenou kostku. [Postup pro D:\QAROS_VTK](docs/WINDOWS_DESKTOP.md).

Aktuální balíček pro GitHub Desktop používá session API a přesně odpovídá
hlavičce `022c40b6…` ze stávajícího SDK v `D:\install`. Použij **Legacy viewer →
visualizer**; Hub pairing code nech prázdný. Podrobnosti jsou v uvedeném postupu.
R7 už má na testovacím PC potvrzené správné transformace. Visualizer ukazuje
přibližně 44 FPS, ale log senderu měří asi 19,7 nových stereo snímků za sekundu.
Vykreslení obou očí trvá průměrně 4,6 ms; většina zbývajícího času zatím není
přesně přiřazená. Diagnostická verze r8 rozlišuje čekání na snímek, skutečné
uspání smyčky a převzetí textur (`PERF` a `PACING`). Dosažení cíle 60 FPS ještě
není potvrzené. Před rozbalením zavři Slicer i Visualizer;
cesty k pluginu a senderu zůstávají stejné. Logy lze zabalit pomocí `COLLECT-LOGS.cmd`.
Samostatné stažení je také v [GitHub Release](https://github.com/HonzaHovora/QAROS_VTK/releases/tag/windows-start-2026-10-14-session022c40b6r8).
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
- Slicer plugin: výběr modelu/segmentu, Start/Stop, pairing, aktualizace a log.
- ParaView Python plugin přes Plugin Manager: filtr QAROS Streaming, Start/Stop
  a publikování změn pipeline. První Hub pairing se provede ve Sliceru nebo terminálu.
- Samostatné složky pluginů, ZIP balíček a základ CMake extension pro Slicer.
- Znovunačtení exportu za běhu (`--watch`), kontrola shody SDK, skripty pro build a CI.

Pluginy předávají geometrii přes atomicky zapsaný `.vtp`; video snímky zůstávají
na GPU backendu. Tím jsou jeho knihovny oddělené od VTK/Qt hostitele. První verze
podporuje jeden povrch; kompletní scény, volume rendering, barevné mapy a interakce
z headsetu zpět do aplikace zbývá implementovat.

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


