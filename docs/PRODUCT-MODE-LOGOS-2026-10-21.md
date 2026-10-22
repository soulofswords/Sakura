# Product and mode logos — 2026-10-21

Companion startup chooser, Local LLM, and Cloud API modes: supplied pink flower design, static/assets/desktop-companion.png and launcher/companion.ico.
Companion VTuber camera/phone tracking mode: supplied character profile with sakura design, static/assets/companion-vtuber.png and launcher/companion-vtuber.ico. Returning to AI restores the flower. The dedicated Sakura VTuber product never uses either Companion identity.
Standalone Sakura VTuber: supplied neon headset Sakura VTUBER design, static/assets/vtuber-app.png and launcher/vtuber.ico.

Native window/taskbar/tray and web titlebar/favicon/splash are connected to the same product/mode mapping. Local launchers recompiled with product-specific embedded icons; startup chooser uses the flower icon. Windows installer and macOS bootstrap build recipes select the correct product icons for future rebuilds. No installers/APK rebuilt and no GitHub publication. Both owner's local apps refreshed. Existing running processes must restart; Windows may retain pinned shortcut icon cache independently.

Validation: 5 Python identity/product-template tests; JS tests of all mode/product paths, titlebar/favicon/splash and native bridge calls; Python syntax and JS syntax checks; multi-resolution ICO checks and both local refresh/import/launcher checks passed. Native Qt/taskbar change was implemented through UI-thread signals; not yet visually checked after restarting this branding update.

Asset processing used built-in image_gen to extract each supplied raster logo into a transparent outside tile and standard Pillow resizing/ICO encoding. Outputs are derived extractions rather than guaranteed pixel-identical crops. Prior Companion PNG/ICO saved in backups/branding-before-2026-10-21.

Prompts:
1. Extract ONLY the LEFT app icon from the supplied sheet: the rounded pale white-pink square with the faceted pink sakura blossom. Deliver one square icon, centered, tightly fitted to canvas, full exact original left icon design preserved, no redesign, no words or labels, no sheet/background outside the icon. Preserve the rounded square pale background INSIDE the icon and make only the outside corner regions transparent. The right character portrait and all typography must be absent. This is an asset extraction for the existing logo.
2. Extract ONLY the RIGHT app icon from the supplied sheet: the rounded dark purple square containing the white and pink anime girl profile silhouette, large pink sakura blossom and subtle circular arc. Deliver one square icon, centered and tightly fitted to canvas, full exact original right icon design preserved, no redesign, no words or labels, no sheet/background outside the icon. Preserve the dark rounded square background INSIDE the icon and make only the outside corners transparent. Left flower icon and all typography must be absent. Asset extraction of the existing supplied logo.
3. Extract the existing rounded-square Sakura VTuber neon app icon, preserving its complete original artwork exactly including Sakura VTUBER lettering, headphones, face, flowers, and purple rounded tile. One square icon tightly fitted to canvas, make only the OUTSIDE of the rounded tile transparent, removing surrounding dark poster margins. No redesign, no added elements, no cropping away content within tile. Deliver an app icon asset.


## Executable/taskbar follow-up

Recompiled and replaced both F:/AI/assistant root launchers with their product icons while no Sakura window was open. Verified each EXE's RT_GROUP_ICON and all seven RT_ICON binary payloads match the chosen ICO exactly (Companion flower; dedicated VTuber neon). Notified the shell of association/icon changes. Added pywebviewready branding resync so native taskbar/window branding gets applied even if initial settings load precedes bridge readiness. Both local editions refreshed. Visually verified flower in the reopened chooser and profile logo in Companion's VTuber titlebar. Pinned Windows shortcut cache can be independently retained by Windows; no icon-cache database deletion or Explorer restart performed. No installer rebuild.
