# Aimee's Recipes 🍲

A pastel recipe book that installs on a phone from GitHub Pages and works offline.
Recipes are stored on each phone; move them between phones with **Backup** and **Restore**.

## Install on a phone
- **iPhone (Safari):** open the Pages link → Share → *Add to Home Screen*.
- **Android (Chrome):** open the Pages link → ⋮ menu → *Install app* / *Add to Home screen*.

## Pushing an update
1. Change the files.
2. Bump the version in **both** `app.js` (`APP_VERSION`) and `sw.js` (`VERSION`).
3. Commit and push. Installed phones pick it up next time the app is opened online
   (or tap *Restore → Check for updates*). Recipes are never touched by updates.
