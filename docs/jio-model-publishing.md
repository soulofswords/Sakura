# Adding models to Sakura's Jio library

The app shows characters, not storage ZIP filenames. Open **Models → Cloud import
PMX**, sign in to Sakura, choose a game folder, then select a character's rotating
preview and choose **Download**. Search finds character names across games when
you are at **All games**. Installed characters appear in the existing PMX selector.
The download button shows a spinner and activity bar while transfer, validation
and installation run. It is an activity indicator, not an invented percentage.

Live2D retains its searchable portrait grid. Local PMX, VRM and Live2D import
controls remain separate. The same cloud browser is in standalone VTuber and
the Companion app's modes.

## Why there is a Sakura library packages folder

Jio's raw folders keep the game → character → model/textures layout you uploaded.
Sakura downloads complete ZIP packages so textures, nested folders and original
filenames arrive together. `PMX/Sakura library packages` is owner storage for those
generated ZIPs, rotating preview images and a catalogue. It is not shown as a
game or character to users. Keep it in place; moving or deleting it breaks
published downloads. No public Jio share links are created.

Every original folder level is retained, including large character groups split
into smaller downloadable packages. Browsing a folder shows only its direct
subfolders and model cards; search is restricted to that folder and its children.
Search at All games covers the whole catalogue.

Nested outfit folders and multiple humanoid PMX files in the same folder are
packaged as separate selectable looks. Browsing preserves game → character →
outfit → variant paths, with one rotating preview per selectable PMX. Old combined
packages remain valid for existing installations, but their cards are hidden
when the separate variant children are published. Props such as separate guns
and swords do not become selectable character looks.

The publisher reads every category folder inside Jio's **PMX** folder, except
the generated **Sakura library packages** folder. Nested character/outfit folders
are discovered automatically; new category names need no code change. The latest
inventory contains 666 humanoid looks across 12 categories. Standalone props are
kept under **Tools & Props**; mixed character textures are left with their model.

## Add a PMX character to an existing game

1. In Jio, upload the **complete character folder** under `PMX/<game>/`.
   Include the `.pmx` files, texture directories and credits. Keep relative paths.
2. Wait for Jio to finish the upload. Partial uploads should not be published.
3. On this owner PC, double-click `F:\AI\assistant\Sakura\tools\sync-jio-library.bat`.
   Alternatively, close any existing private preview job and run:

   ```powershell
   Set-Location 'F:\AI\assistant\Sakura'
   $env:NODE_PATH='C:\Users\gaura\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
   venv\Scripts\python.exe tools\sync-jio-library.py --all-accounts
   ```

4. The owner sync reads all PMX category folders, downloads missing or
   changed runtime assets to a **private mirror**, validates installable PMX
   packages, renders rotating previews, uploads/checksums packages and publishes
   catalogue entries. It does not overwrite the original local/Jio character
   folders. Files from `Sakura library packages` are never treated as source.
5. In Sakura, choose **Refresh library**; an open signed-in gallery also refreshes
   every minute. Other users need only Sakura sign-in, never your Jio account.

To inspect without downloading/preparing/publishing:

```powershell
venv\Scripts\python.exe tools\sync-jio-library.py --inventory-only
```

The owner sync must run on this PC with working internet before a new upload
appears in the public catalogue. It validates complete model packages and renders
real rotating PMX previews. Existing user installations and edits are preserved.
No Supabase code deployment or schema edit is needed for a new folder. Publication
updates catalogue rows through the existing protected owner API, including folder
name corrections when ZIP bytes are unchanged. Expired owner sessions still require
Jio reauthentication; transient read failures receive bounded retries. The launcher
checks both configured accounts even if one fails. `--additions-only` can publish
new PMX sources without rebuilding old packages, but use a normal full sync to
process source edits/deletions.
The owner Agent's hourly workflow uses additions-only mode to avoid downloading
cloud-verified staging trees again after cleanup. To republish changes made to an
existing file under the same name, run the full owner sync command above.

Cloud cards mark an existing installation as Installed. The backend also prevents
a second install by catalogue ID or identical package hash, including copies listed
under another storage account. A previously manual import without a cloud receipt
is checked for matching model and asset bytes after the first cloud transfer; it is
reused rather than copied. Names alone never identify duplicates, so different
outfits can still be installed separately.
An hourly Codex follow-up named **Sync Sakura model library** checks this owner
PC and skips while a sync is already running. The owner PC and Codex must be
available; this is not a cloud-hosted background worker. It stays quiet when
nothing has changed and reports completed new publications or actionable errors.

For Live2D, upload a complete model folder directly under **live2d**. The same
sync discovers those folders, validates their model descriptors/textures, and
uses a preview/portrait PNG or JPG from each folder. Texture atlases are excluded
from portrait selection. When no portrait exists, Sakura shows the model's folder
name in its square card. Generated loose ZIPs/WebPs in live2d are ignored as source.

Moving a folder within Jio does not reduce storage usage. Keep **Sakura library
packages**: it contains the authenticated downloads and previews used by testers.

## TGA texture filenames

Some files named `.tga` contain PNG bytes. Jio can change the extension or refuse
the rename. Preserve such files with original names inside a ZIP in the same
texture folder. The owner sync recognizes the repair archive
`Sakura-original-TGA-textures.zip`, restores its `.tga` entries into the private
mirror, and includes the exact names/bytes in the final model package. Existing
Evelyn packages were built from the unchanged local originals, so users don't
need to extract the repair archive themselves.

## Credentials and recovery

Owner Jio login and the separate publisher capability are Windows-encrypted
outside the source repository. Necessary Jio credentials are kept in Supabase
Vault for private server-side downloads. Testers receive neither the owner login
nor private provider object IDs. Owner publication requires its encrypted random
capability, whose hash is deployed on the server. Revoke or rotate it if the owner
PC changes. Reconnect using `tools/jio_library_owner.py` if Jio revokes the session.

Prepared assets, inventories, checkpoints and reports remain in
`F:/AI/assistant/private-model-library-pmx`; none belongs in installers or Git.


## Second storage account

The owner publisher supports primary and account2, each in a separate DPAPI
profile. Account2 never overwrites the primary session. Its model IDs and private
object references are namespaced, while names retain the game/character folder
hierarchy. Authenticated clients browse both through the same Sakura library.
No credentials or underlying download URLs are sent to clients.

## Dedicated stages and Tools & Props

Upload complete PMX stage folders under **Stage** (or **Stages**) in My Files, or
under PMX/Stage. Matching is case-insensitive. The owner's existing **Tools & Props**
tree is separate. Do not upload stages into character folders. The hourly owner
Agent checks characters, stages and props in both accounts. Empty stage folders
remain empty until an installable PMX package is uploaded.

Sakura's Background → 3D backgrounds & props offers **Stages** and **Tools & Props**.
Each has its own local folder browser, search and cloud button. Cloud sign-in is
checked only when its button is clicked. Downloads go to `models/pmx/Stages` or
`models/pmx/Tools & Props`; these assets are excluded from character selectors.
Choose one asset, then Add selected asset to stage. The whole library is never
placed at once. The current character remains selected. PMX scenery is validated
as a PMX file without requiring humanoid bones; character imports still require
a valid humanoid rig. PNG and Live2D overlay items remain in their own controls.

Additional VTuber instances start with a fresh temporary browser profile and
fresh settings, including an empty scene. The first instance retains its normal
saved scene/settings. All instances share installed model and scenery files.

Launch tools/jio_library_owner.py --account account2 --folder PMX to configure
the second account. The owner Agent includes it only after server routing has
been deployed and the account verified. Original upload folders are read only.
Sakura-original-names ZIPs preserve filenames that Jio deduplicates or refuses
as empty text uploads. They are verified by download before use in packaging.
