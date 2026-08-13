# StagEye — Remote Screen Monitor

Live remote view of the FOH computer screen over the internet.
Built for Vara Konserthus.

---

## Viewer URLs

| Stage | URL |
|---|---|
| Stora Salen | https://stageye.spdproduktion.se/?room=stora-salen |
| Blackbox | https://stageye.spdproduktion.se/?room=blackbox |
| Host setup | https://stageye.spdproduktion.se/host |

Open any viewer URL in any browser — no install needed.

---

## FOH Computer Setup

### Install once
1. Download Python from [python.org/downloads](https://python.org/downloads) — tick **Add Python to PATH**
2. Open a terminal and run:
3. Copy `stageye_host.py` and `stageye_start.bat` to the FOH computer

### Configure the script
Open `stageye_host.py` and set the room at the top:
```python
ROOM = "stora-salen"   # or "blackbox"
```

### Run it
Double-click `stageye_start.bat` — no terminal window appears.

### Autostart on boot
1. Press `Win + R` → type `shell:startup` → press Enter
2. Put a shortcut to `stageye_start.bat` in that folder
3. The script now starts automatically every time Windows boots

---

## How it works
---

## Rooms

Each stage has its own isolated stream. The room is set in the Python script
and in the viewer URL. Adding a new stage: pick a slug (no spaces), add it to
`ROOM_NAMES` in `src/lib/stageye.ts`, copy the script to the new FOH computer
and set the ROOM variable.

---

## Project

- App: [stageye.lovable.app](https://stageye.lovable.app)
- Custom domain: [stageye.spdproduktion.se](https://stageye.spdproduktion.se)
- Lovable project: [lovable.dev/projects/1206b096-4490-421e-8952-b7b107367894](https://lovable.dev/projects/1206b096-4490-421e-8952-b7b107367894)
- Supabase project: `fxomeytrkhrzkpjkpfjt`
- 
