# StagEye

Fjärrövervakning av FOH-datorns skärm över LAN och internet. Byggt för
Vara Konserthus, för att starta, övervaka och stänga Smaart (SPL-mätning)
på distans från valfri telefon eller webbläsare, utan installation.

## Arkitektur

Python-skript på FOH-datorn tar skärmbilder och gör två saker med varje bild:

1. Håller den i minnet och serverar den från en lokal webbserver (LAN-läge)
2. Laddar upp den till Supabase Storage (WAN-läge)

LAN-läget kräver ingen internetuppkoppling alls. Misslyckas uppladdningen
fortsätter LAN-läget opåverkat.

Ingen Realtime används. Webbläsaren hämtar helt enkelt den senaste bilden
med jämna mellanrum.

## Rum

Appen stödjer flera scener. Rummet sätts per dator i `stageye_host.py`.

| Rum           | LAN                     | WAN                                                |
| ------------- | ----------------------- | -------------------------------------------------- |
| `stora-salen` | `http://<FOH-IP>:8080/` | https://stageye.spdproduktion.se/?room=stora-salen |
| `blackbox`    | `http://<FOH-IP>:8080/` | https://stageye.spdproduktion.se/?room=blackbox    |

`src/lib/stageye.ts` innehåller `ROOM_NAMES`, `roomFrameUrl()` och
`roomFrameObject()`. Viewern läser `?room=` via TanStack Routers
`validateSearch`.

## Lagring

Supabase Storage, publik bucket `screen-frames`, en fil per rum:
`{room}/latest.jpg`. Skrivs över vid varje uppladdning.

## Python-värd

`stageye_host.py` körs på FOH-datorn.

- Lokal fångst: 0.4 s intervall, JPEG-kvalitet 65
- Molnuppladdning: 2 s intervall, JPEG-kvalitet 40, ren HTTPS PUT
- Loggar till `stageye_host.log` bredvid skriptet
- Mus- och tangentbordsstyrning via `pyautogui` (valfritt, `CONTROL_ENABLED`)

Autostart via `stageye_start.bat`, som körs dolt med `pythonw` från Windows
Startup-mappen. Batchfilen låser Python-versionen till 3.12, eftersom 3.14
saknar wheels för `mss`.

Porten 8080 måste vara öppen för inkommande trafik i Windows-brandväggen:

    netsh advfirewall firewall add rule name="StagEye LAN" dir=in action=allow protocol=TCP localport=8080

## Bandbredd

Cirka 4,4 GB/månad vid ~20 gig, 3 h per gig — inom Supabase gratisnivå
(5 GB/mån). LAN-läget belastar inte kvoten alls. Vid behov: höj
`CLOUD_INTERVAL` eller flytta lagringen till Cloudflare R2.

## Arbetssätt

Alla kodändringar görs via GitHubs webbgränssnitt, inte via Lovable-chatten,
för att spara Lovable-krediter. Lovable synkar automatiskt från GitHub.

Kom ihåg: FOH-datorn har en egen kopia av `stageye_host.py`. Ändringar i
repot måste laddas ner dit manuellt.
