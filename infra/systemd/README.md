# systemd units

The RBI feed keeps only its latest items, so the collector runs daily to build the archive.

```bash
mkdir -p ~/.config/systemd/user
cp finpulse-rbi.service finpulse-rbi.timer ~/.config/systemd/user/
# edit WorkingDirectory in the service to the real path of server/
systemctl --user daemon-reload
systemctl --user enable --now finpulse-rbi.timer
systemctl --user list-timers finpulse-rbi.timer
```
