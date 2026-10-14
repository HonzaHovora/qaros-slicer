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

Balíček odpovídá testovacímu vydání `windows-start-2026-10-14-session022c40b6r8`.
R7 už má na testovacím PC potvrzené správné transformace. R8 podrobněji měří
čekání: zatímco Visualizer ukazuje asi 44 FPS, sender skutečně předává přibližně
19,7 celých stereo snímků za sekundu. Tato dvě čísla měří různé části přenosu.
Samotné VTK vykreslení obou očí trvá v dodaném logu průměrně 4,6 ms.

Po aktualizaci spusť přenos stejné kostky. Nech Visualizer viditelný v popředí
asi minutu, několikrát otoč kamerou, potom stiskni **Stop streaming** a spusť
`COLLECT-LOGS.cmd`. Přilož vytvořený ZIP. Není třeba kopírovat jednotlivé řádky.

Sender každých pět sekund zapisuje `PERF` s oddělenými časy vykreslení,
uspávání, převzetí textur, údržby smyčky a dalších operací. Řádek `PACING`
doplňuje celkové čekání od první žádosti o snímek do jeho připravenosti a
skutečnou průměrnou/maximální délku krátkého uspání. Toto celkové čekání se
překrývá s některými položkami PERF, proto je nesčítej. Jde o časy na straně
senderu, nikoli přímé měření asynchronního enkodéru nebo práce mixeru.
Tato diagnostická verze ještě není ověřená optimalizace na 60 FPS. Výkon pro
dvoje brýle nebyl změřený.

## Když po zobrazení volume přenos spadne

Po pádu spusť `D:\QAROS_VTK\COLLECT-LOGS.cmd`. Slicer může zůstat otevřený.
Skript vytvoří ZIP v `D:\QAROS_VTK\diagnostics` a vybere ho v Průzkumníku.
Přilož tento ZIP do chatu. Obsahuje poslední tři logy senderu, informace o
nainstalované verzi a související záznamy pádů z Windows. Modely ani pozvánky
do balíčku nekopíruje. Nic automaticky neodesílá a nepotřebuje správce.

Napiš také, zda zmizí celé okno Visualizeru, nebo jen pracovní volume. Pokud
Slicer zůstane otevřený, připiš číslo z hlášení `Sender exited with code ...`
nad polem Sender log. To rozliší chybu senderu od pádu vieweru.


