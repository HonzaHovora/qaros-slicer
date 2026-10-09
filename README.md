# QAROS × VTK

První funkční základ pro přenos povrchové 3D scény z VTK do QAROS. Cílem jsou
ParaView a 3D Slicer. Společná renderovací cesta používá OpenGL, které již QAROS
podporuje; Vulkan není součástí této implementace.

**Stav: prototyp před ověřením s reálným QAROS Hubem a headsetem.** GPU cesta se
ověřuje na Linuxu s Mesa. Úspěšný test není potvrzení funkčnosti NVIDIA enkodéru,
transportu ani výsledného obrazu v headsetu. Aktuální sestavení a jejich výsledky:
[GitHub Actions](https://github.com/HonzaHovora/QAROS_VTK/actions).

## Co už je v repozitáři

- C++17 jádro: stereo, asymetrické projekce, souřadnice a kontrola layoutu.
- VTK/OpenGL renderer a samostatný náhled bez QAROS SDK.
- GPU kopírování barvy a hloubky do textur QAROS bez čtení obrazu na CPU.
- Odesílač pro Windows/WGL a Linux/GLX: nový Hub onboarding i starší SDK 2540.
- Export aktivního povrchu z ParaView a modul pro export modelu/segmentu ze Sliceru.
- Znovunačtení exportu za běhu (`--watch`), kontrola shody SDK, skripty pro build a CI.

Hostitelské mosty v této fázi exportují povrch do `.vtp`; VTK renderer běží jako
samostatný proces. To odděluje jeho VTK/Qt knihovny od verzí přibalených k ParaView
nebo Sliceru. Nejde zatím o přímý renderovací plugin ani přenos kompletní scény,
volume renderingu, barevných map nebo interakcí z headsetu zpět do aplikace.

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

Postup v [docs/WINDOWS.md](docs/WINDOWS.md). Potřeba: Visual Studio 2022 s C++,
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

Podrobné kroky a příklady: [docs/HOST_INTEGRATIONS.md](docs/HOST_INTEGRATIONS.md).
Slicer exportuje world RAS v milimetrech, proto jeho data spouštějte takto:

```powershell
python scripts/run_sender.py --exe build-windows/Release/qarvtk-sender.exe --sdk C:/QAROS --scene C:/data/surface.vtp --ras --meters-per-unit 0.001 --watch --preview
```

Další podklady:

- [Architektura, formáty a omezení](docs/ARCHITECTURE.md)
- [Ověření a další práce](docs/VALIDATION.md)
- [Rozdíly verzí SDK](docs/SDK_COMPATIBILITY.md)

SDK, runtime DLL, pozvánky a párovací identity nejsou součástí repozitáře.
