# Conectare automata la VPN si citire UMG 509

1. **Pregatire configuratie**
   - In fisierul `config/settings.yaml` sau varianta indicata prin `--config`, completeaza campurile `router.openvpn_profile` (cale catre profilul `.ovpn`) si `router.openvpn_executable` (calea completa catre `openvpn.exe`).
   - Asigura-te ca profilul `.ovpn` refera corect certificatele/credentialele (parametrul `auth-user-pass` poate indica un fisier cu user/parola).

2. **Pornire VPN din CLI**
   - Comanda citeste automat tunelul daca folosesti optiunea implicita `--auto-vpn`:  
     `python -m prognoza.interfaces.cli read-umg power_active_total`
   - Pentru un timeout diferit:  
     `python -m prognoza.interfaces.cli read-umg power_active_total --vpn-timeout 60`
   - Daca vrei sa folosesti un alt fisier de configurare:  
     `python -m prognoza.interfaces.cli --config config/settings.example.yaml read-umg power_active_total`

3. **Executie scheduler cu VPN automat**
   - Ruleaza `python scripts/run_scheduler.py`. Scriptul porneste OpenVPN, asteapta mesajul "Initialization Sequence Completed" si mentine tunelul activ pana la oprire (Ctrl+C).

4. **Oprire tunel**
   - Atat CLI-ul (in modul auto) cat si `run_scheduler.py` opresc procesul OpenVPN la final. Pentru sesiuni manuale poti inchide scriptul sau folosi OpenVPN GUI pentru deconectare.

5. **Diagnosticare**
   - Fisierele de log se scriu in directorul `logs/` sub forma `openvpn_<profil>_<timestamp>.log`.
   - Mesajele `AUTH_FAILED` sau iesirea imediata a procesului indica probleme de credentiale sau de permisiuni. Pe Windows, ruleaza terminalul cu privilegii de Administrator.
