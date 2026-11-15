; ============================================================
;  EVE Motor Market - Windows-Installer (Auftrag F5)
;  Gebaut mit Inno Setup 6 (kostenlos, https://jrsoftware.org/isdl.php).
;  Aufruf uebernimmt build.bat - dort werden Name und Version aus
;  eve_trader/__init__.py hereingereicht, damit es EINE Wahrheit bleibt.
; ============================================================

; NAME UND VERSION KOMMEN VON AUSSEN. build.bat liest sie aus
; eve_trader/__init__.py und gibt sie per /D mit. Die Werte hier sind nur
; ein Notnagel, falls jemand die .iss direkt in der Inno-Setup-Oberflaeche
; oeffnet - dann steht wenigstens etwas Sinnvolles drin, statt dass der
; Bau abbricht.
#ifndef MyAppName
  #define MyAppName "EVE Motor Market"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppExeName MyAppName + ".exe"

[Setup]
; AppId FEST VERDRAHTET und NIE aendern: Windows erkennt daran, dass eine
; neue Fassung dieselbe Anwendung ist. Aendert man sie, steht das Programm
; nach dem naechsten Update ZWEIMAL in der Softwareliste, und die alte
; Fassung laesst sich nur noch von Hand entfernen.
AppId={{7C4B1F2E-9A63-4D18-8E57-2F0B6C3A9D41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Peanut Motor
AppPublisherURL=https://github.com/PeanutMotor/eve-motor-market
AppSupportURL=https://github.com/PeanutMotor/eve-motor-market/issues
AppUpdatesURL=https://github.com/PeanutMotor/eve-motor-market/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Symbol des Installers selbst - dieselbe Datei, die build.bat vor dem Bau
; aus dem Logo im Code erzeugt. Sonst traegt ausgerechnet das erste, was ein
; neuer Nutzer sieht, das nichtssagende Standardsymbol.
SetupIconFile=eve_trader\ui\assets\logo.ico
; DAS LOGO IM ASSISTENTEN (emm943, Nutzer 15.11.2026: "hier ist das Logo
; bitte bau es ein"): gross auf Willkommens- und Abschluss-Seite, klein
; oben rechts auf den uebrigen. Die Bilder erzeugt
; werkzeuge\mache_installer_bilder.py aus demselben Logo wie das Symbol.
; NUR WENN SIE DA SIND: fehlen sie (jemand baut aus einem alten Stand),
; nimmt Inno Setup seine Standardbilder, statt den Bau abzubrechen.
#if FileExists("installer_gross.bmp")
WizardImageFile=installer_gross.bmp
#endif
#if FileExists("installer_klein.bmp")
WizardSmallImageFile=installer_klein.bmp
#endif
OutputDir=dist
OutputBaseFilename=EVE-Motor-Market-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Sprache nicht aus Windows ableiten - Englisch vorwaehlen (emm945,
; siehe [Languages]).
LanguageDetectionMethod=none
; OHNE ADMINRECHTE: installiert nach %LOCALAPPDATA%\Programs. Ein
; Handelswerkzeug braucht keine Systemrechte, und die UAC-Abfrage ist fuer
; viele Nutzer genau die Huerde, an der sie abbrechen.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
; ENGLISCH IST DIE VORGABE (emm945, Nutzer 15.11.2026: "das hier am
; anfang soll standard auf english sein"). Die ERSTE Sprache der Liste
; ist die Vorgabe, sobald die Erkennung der Windows-Sprache aus ist
; (LanguageDetectionMethod=none in [Setup]) - sonst waehlt Inno Setup auf
; einem deutschen Windows Deutsch vor. Deutsch bleibt waehlbar.
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; NUR DIE EXE. Hier NICHTS aus dem Projektordner hinzufuegen - dort liegen
; settings.json (mit client_id und Charakter-IDs), ledger.db (Handelsdaten)
; und .smoke_home. Die Pruefung aa222 in test_bestand_herkunft.py schlaegt
; an, wenn hier etwas anderes auftaucht.
; onedir (emm866): gepackt wird der GANZE Build-Ordner aus dist\ -
; die EXE landet wie bisher direkt in {app}, daneben _internal\.
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

; ============================================================
;  BEWUSST KEIN [UninstallDelete].
;  Die Nutzerdaten (settings.json, ledger.db, industry.db) liegen unter
;  %APPDATA%\EVE Motor Market - also in ROAMING, nicht in LocalAppData.
;  Dorthin installiert sich nur das PROGRAMM. Wer den Datenordner sucht und
;  im falschen Zweig nachsieht, haelt seine Daten fuer verschwunden.
;  Dazu der alte Ordner EveTradeLedger, solange jemand noch nicht
;  umgestiegen ist. BEIDE werden vom Installer NIE angefasst - weder beim
;  Installieren noch beim Entfernen. Inno Setup loescht von sich
;  aus nur, was es selbst angelegt hat; ein [UninstallDelete] auf diesen
;  Ordner wuerde beim Entfernen das gesamte Handelsjournal mitnehmen. Wer
;  hier etwas ergaenzen will: aa226 verbietet es, und zwar mit Absicht.
; ============================================================
