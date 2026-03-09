# Clawtunes Plugin TODO

## Done
- [x] Scaffold plugin structure
- [x] Playlist curation skill
- [x] /now-playing command
- [x] Fork clawtunes, add --artist/-A filter (PR: https://github.com/forketyfork/clawtunes/pull/14)

## Up Next
- [ ] Spotify audio features integration — cross-reference Apple Music tracks against Spotify's Web API to get energy, valence, danceability, acousticness, instrumentalness, tempo, loudness per track. Use for automated mood-based filtering instead of relying solely on Claude's music knowledge. Spotify API is free (no premium required), ~180 req/30s rate limit. Would enable commands like "give me everything with energy < 0.3"
- [ ] Bulk playlist operations — `clawtunes playlist add-from-file` to avoid per-track subprocess overhead (upstream feature request or local script)
- [ ] Smart playlist audit command — after building a playlist, scan for genre outliers and wrong-artist matches
- [ ] AirPlay integration — skill for managing playback across devices (already supported by clawtunes CLI)
- [ ] More commands: /play, /playlists, /love, /skip
