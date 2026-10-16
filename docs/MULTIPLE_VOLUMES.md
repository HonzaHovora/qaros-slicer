# Více objemů v jednom živém 3D pohledu

Experimentální rozšíření Python pluginu nad Windows balíčkem r17 (host ABI 4).
Přenáší všechny viditelné běžné GPU Composite objemy z prvního 3D pohledu
Sliceru do jednoho společného QAROS pracovního prostoru. Zachovává jejich
barvy, transformace, viditelnost a ROI ořez nastavené ve Sliceru.

## Vyzkoušení na Windows

1. Zastav streaming a zavři Slicer.
2. V GitHub Desktop dej Fetch origin a přepni Current branch na
   `codex/slicer-multiple-volumes`.
3. V kořeni checkoutu spusť `UPDATE-LIVE-PLUGIN.cmd`. Použije již rozbalený
   r17; nativní DLL a SDK se nemění. Pokud r17 dosud není rozbalený, spusť
   nejdříve `START-PREVIEW.cmd`, zavři kostku a teprve potom aktualizační skript.
4. Otevři Slicer. V modulu QAROS Live Renderer musí být nový text
   **Multiple VTK GPU Composite volumes**.
5. V prvním 3D pohledu zobraz oba objemy. Pro každý použij **VTK GPU Ray Casting**
   a **Composite with shading**. Zpočátku je umísti vedle sebe.
6. Klikni Start live streaming. Oba objemy se mají objevit společně.
   Vyzkoušej skrytí jednoho, změnu presetu, transformaci a ROI ořez.

Při načtení druhého objemu nebo změně celkového rozsahu scény dej Stop a Start,
aby pracovní prostor znovu zahrnul celou scénu. Viditelnost již načtených objemů
a jejich vzhled se za běhu aktualizují automaticky.

`START-PREVIEW.cmd` vždy rozbaluje původní r17 a tím tuto úpravu odstraní.
Pro návrat k experimentu potom znovu spusť `UPDATE-LIVE-PLUGIN.cmd`.

## Co se přenáší a jaké jsou náklady

Barva obou očí pochází z nezměněného rendereru Sliceru. Pro více objemů se pro
každé oko přidá samostatný průchod pro hloubku všech objemů a neprůhledných
povrchů. Standardně používá požadované poloviční rozlišení hloubky: při barvě
1920 × 1080 je hloubka 960 × 540. V logu je `host_render_calls=4` a
`volume_depth_passes=2` na stereo snímek. Při jediném viditelném objemu zůstává
rychlá cesta `2` / `0`, pokud ji umožňuje původní hostitelská pipeline.

Dodatečný průchod může snížit FPS; skutečný dopad se musí změřit na cílové
NVIDIA kartě. Pro první srovnání lze vypnout náhledy řezů a poté je opět zapnout.
Záznam diagnostiky nově zahrnuje `volume_count` a nastavení každého objemu.

Každý pixel má stále jednu hloubku, určenou nejbližším přispívajícím vzorkem
nebo neprůhledným povrchem. Nejde o přenos všech průhledných vrstev objemu.
Barva zachovává i případná omezení původního Slicer rendereru při překrývání
objemů. Tato změna neopravuje pořadí jejich nativního barevného skládání.

Samostatné QAROS objekty pro každý objem/pohled nejsou součástí této změny.
Speciální renderer **VTK Multi-Volume** pro společnou fúzi je stále odmítnutý.
Víceobjemová cesta vyžaduje VTK 9.6 (testovaná verze Sliceru 5.12.4), Composite,
neprůhledné povrchy a standardní pipeline bez SSAO, stínů, vlastního renderovacího
průchodu nebo konfliktního shaderu hloubky. Kontrola se provádí i za běhu.

## Ověření

Lokálně prošel tento test na skutečném rendereru VTK 9.6.2 přes EGL/Mesa,
bez grafického okna (`python tests/slicer_multivolume_smoke.py --vtk-egl`).
Prošly také testy umístění a transportního stavu. GitHub Actions pro tento
prototyp skončily před prvním krokem, bez spuštěného runneru. Plný test v
Sliceru 5.12.4 proto zatím nemá nový úspěšný výsledek; místní prostředí
neumožňuje spustit jeho grafické okno. EGL ověřuje GPU výpočet, ne MRML/Qt.

`tests/slicer_multivolume_smoke.py` porovnává výslednou barvu s nativním Slicerem
a hloubku s minimem nezávislých VTK RenderToImage průchodů jednotlivých objemů.
Zahrnuje oba stereo pohledy, opačné pořadí objemů, transformace, projekční překryv,
neprůhledný povrch, živý ROI ořez, poloviční hloubku, prázdné paprsky,
skrytí nepodporovaného objemu a obnovu desktopu i po chybě příjemce.

Samotný úspěch renderovacích testů nepotvrzuje NVIDIA enkodér ani přenos do
Visualizeru na Windows. Ten musí ověřit první cílový pokus.
