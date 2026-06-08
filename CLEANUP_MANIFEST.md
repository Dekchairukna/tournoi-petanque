# Cleanup manifest

Removed obvious unused duplicate/backup files and macOS metadata.

- Removed `__MACOSX` and `.DS_Store` artifacts.
- Removed root duplicate files ending with ` 2`.
- Removed old patch/change-note markdown files.
- Removed template backup files `*.bak*`.
- Kept all primary source files, templates, static assets, and data spreadsheets.

Functional changes:

- Swiss voice announcement now says `ประกาศผลการประกบคู่ / การแข่งขันครั้งที่ X`.
- Playoff next-round dropdown always shows A/B, Double knockout, Knockout, Swiss, and disabled Round Robin.

Additional cleanup:

- Removed root Thai/manual `.txt` note dumps that are not imported by Flask. Kept `requirements.txt`.
- Removed temporary snippet file `1.py` and empty file `main`.
