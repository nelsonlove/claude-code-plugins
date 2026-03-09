---
name: playlist-curation
description: Use when the user asks to create a playlist, curate music, find songs for a mood/activity, or work with their Apple Music library. Also use when the user mentions "clawtunes", "naptime playlist", or asks about their music collection.
---

# Playlist Curation with Clawtunes

## Overview

Help the user create intelligently curated playlists from their Apple Music library using the `clawtunes` CLI and your music knowledge.

## Core Workflow

1. **Extract** — Pull track metadata from the user's library (playlists, loved tracks, etc.) via `clawtunes` or `osascript`
2. **Curate** — Use your deep knowledge of artists and catalogs to filter tracks by mood, energy, genre, or purpose
3. **Build** — Add tracks to a new or existing playlist via `clawtunes`

## Tools Available

### clawtunes CLI

```bash
# Search songs (use -A to filter by artist — critical for disambiguation)
clawtunes search "track name" -A "artist name" -s --no-albums

# Add to playlist (use -1 for automation, -A for precision)
clawtunes -1 playlist add "Playlist Name" "track name" -A "artist"

# Remove from playlist
clawtunes -1 playlist remove "Playlist Name" "track name" -A "artist"

# Create playlist
clawtunes playlist create "Playlist Name"

# List playlists
clawtunes playlists

# Playback control
clawtunes play playlist "Playlist Name"
clawtunes shuffle on
clawtunes pause / resume / next / prev
clawtunes volume 30
clawtunes status
```

### osascript (for bulk operations and advanced queries)

Use osascript when you need to:
- Export large track lists (clawtunes is slow for bulk reads)
- Search with complex criteria (multiple field matching)
- Handle tracks with special characters that clawtunes can't find
- Get track properties not exposed by clawtunes (duration, genre, play count)

```applescript
-- Export tracks from a playlist
tell application "Music"
    set theTracks to tracks of playlist "Playlist Name"
    repeat with t in theTracks
        -- name, artist, album, duration, genre all available
    end repeat
end tell
```

## Curation Strategy

### For mood/activity playlists:
1. Start with the user's **Loved** tracks or existing playlists as the pool
2. Get the full artist+genre breakdown first
3. Tier artists by how well they fit the mood:
   - **Tier 1**: Almost everything fits (include by default)
   - **Tier 2**: Good fit, needs track-level filtering
   - **Tier 3**: Mostly doesn't fit, cherry-pick specific tracks
4. Use parallel agents to curate each tier simultaneously
5. Build the playlist, then audit for wrong matches (especially cover bands and generic track names)

### Critical: Always use -A for disambiguation
Generic track names like "Sunday", "Alice", "Made", "Chariot" WILL match wrong songs without the artist filter. Always use `-A "Artist Name"` with `clawtunes -1 playlist add`.

### Genre as quality check
After building a playlist, check genre distribution. Outlier genres (e.g., Techno in a naptime playlist) usually indicate wrong-artist matches from `-1` auto-select.

## Limitations

- Apple Music does not expose BPM, energy, loudness, or audio analysis data
- Genre metadata is often missing or inconsistent
- `clawtunes` searches are name-substring matches, not fuzzy — exact spelling matters
- Smart quotes and special characters in track names can cause search failures — fall back to osascript
