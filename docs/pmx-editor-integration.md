# PMX Editor integration

On Windows, select a PMX model and click **PMX Editor** in either Sakura edition. The editor opens the exact source PMX file. Save changes in the editor and reload the model in Sakura to display them.

The local refresh and Windows installer preserve `tools/pmx-editor`, including the native executable, libraries, plugins and original documentation. Character and motion files from the editor folder are excluded from Windows packages. macOS does not package this Windows-only editor.

If the editor is missing, clicking the button opens a file picker for an existing `PmxEditor.exe` installation. The selected path is saved in user settings and reused. Keep its accompanying libraries in the same installation folder.

The source repository contains the integration code, not the third-party editor binaries. To build a Windows installer from source, provide a complete PMX Editor installation at `tools/pmx-editor` first. Build checks verify that the editor executable and library folder are installed in both editions.

This launches the native editor for comparison; it does not embed PmxView or make Sakura's renderer identical to PMX Editor.
