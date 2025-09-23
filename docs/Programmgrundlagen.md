# Programmiertechnische Grundlagen & Funktionsweise

**Ziel & Überblick.**
*p2p-copy* ist eine Python-Bibliothek mit begleitender CLI zum zuverlässigen Kopieren von Dateien über einen vermittelnden Relay-Server per WebSocket. Sie ist asynchron (asyncio-basiert) und modular aufgebaut.

**Paketaufbau.**

* `p2p_copy/` – Kernbibliothek mit Funktionalitäten für Nutzer
* `p2p_copy_cli/` – Kommandozeilenoberfläche zum Senden, Empfangen und Weiterleiten 
* `p2p_copy_server/` – Relay-Server zum Weiterleiten von Dateien

**Modernes WebSocket-Backend.**
Client und Server verwenden die aktuelle `websockets`-AsyncIO-API (`websockets.asyncio.client.connect` / `websockets.asyncio.server.serve`). Diese wurde kürzlich erst überarbeitet.

**Ablauf eines Transfers.**

1. **Verbindung:** Sender und Empfänger verbinden sich zum Relay und senden jeweils ein `hello` (Textnachricht) mit der SHA-256-Prüfsumme des gemeinsamen Codes und ihrer Rolle (`sender`/`receiver`). Der Relay-Server paart exakt ein Sender/Empfänger-Paar pro Code.
2. **Manifest:** Der Sender sendet ein `manifest` (Textnachricht) mit Metadaten der Datei.
3. **Übertragungsfluss:** Die Datei wird in binären Teilnachrichten übertragen; der Abschluss kommt als `eof` (Textnachricht).
4. **Weiterleitung:** Der Relay-Server leitet Nachrichten bidirektional 1:1 weiter; schließt eine Seite, wird die Gegenverbindung kontrolliert beendet.
   *Hinweis:* Kompression, E2E-Verschlüsselung, Integrietätsprüfung und Fehlerbehadlung sind bereits angelegt und werden in nächsten Phasen implementiert.

**CLI-Bedienung.**

* `p2p-copy send SERVER CODE FILE` – startet einen Kopiervorgang.
* `p2p-copy receive SERVER CODE ` – erwartet und speichert die empfangene Datei.
* `p2p-copy run-relay-server HOST PORT ` – startet den Relay-Server; **TLS ist standardmäßig aktiv**, für lokale Tests kann `--no-tls` genutzt werden (z. B. `ws://localhost:8765`).

**Asynchrones Design & Fehlerbehandlung.**  

Alle Netzwerkinteraktionen sind `async` implementiert; lange andauernde Operationen blockieren den Event-Loop nicht. Probleme (falsche Reihenfolge der Nachrichten, doppelte Rollen, Verbindungsabbrüche) werden mit klaren Rückgabecodes und spezifischen Fehlern signalisiert und in der CLI in Prozess-Exitcodes abgebildet.

**Packaging & Abhängigkeiten.**  
Das Projekt nutzt in `pyproject.toml` beschriebene Pakete. Für die moderne API wird `websockets` in einer hinreichend neuen Version vorausgesetzt.

**Erweiterbarkeit.**  
Die Trennung von **API**, **CLI** und **Relay** sowie die klaren Schnittstellen erlauben inkrementelle Erweiterungen: mehrere Datein, Integritätsprüfungen (SHA-256/Ketten-Prüfsummen), optionale E2E-Verschlüsselung (AES-GCM), Verbindungswiederaufnahme und TLS-Betrieb
