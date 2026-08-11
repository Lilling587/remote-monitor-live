# Stage Monitor Live

Build a screen sharing relay app called "StagEye" for live sound engineers to remotely monitor a FOH computer screen.

## Architecture
- The app is a relay between a Python script running on a host computer and any number of browser viewers
- The Python script sends JPEG screen captures to Supabase Storage
- The app displays the latest frame in real time using Supabase Realtime notifications
- Viewers can optionally send mouse and keyboard control events back to the host

## Pages / Routes
1. `/` - Viewer page (the main page everyone opens)
2. `/host` - Host info page (shows setup instructions and connection status)

## Viewer page (`/`)
- Dark background (#0a0a0a)
- Full-viewport canvas/image that shows the latest screen capture
- Top bar (slim, ~40px): app name "StagEye" on the left, connection status dot (green = host connected, red = disconnected) on the right
- Status message below top bar when no host is connected: "Waiting for host connection..."
- When a frame is received, display it scaled to fit the viewport (maintain aspect ratio)
- Below the image: a slim toolbar with:
  - A toggle: "View only" / "Control" (switching to control mode enables mouse and keyboard relay)
  - Frame rate indicator (e.g. "~1 fps")
  - Last updated timestamp

## Control mode
- When "Control" is toggled on, mouse clicks and moves on the image send events to a Supabase Realtime channel called `control-events`
- Each event: `{ type: "mousemove"|"mouseclick"|"keydown", x: 0.0-1.0, y: 0.0-1.0, button: 0|1|2, key: "string" }`
- Coordinates are normalized (0.0 to 1.0 relative to the original screen dimensions)

## Supabase setup needed
- Storage bucket: `screen-frames` (public)
- Frame is stored as `latest.jpg` in the bucket, overwritten every update
- Realtime channel: `frame-updates` — host broadcasts `{ timestamp: number }` when a new frame is ready
- Realtime channel: `control-events` — viewers broadcast mouse/keyboard events to host

## Design
- Aesthetic: dark broadcast monitor. Think hardware rack unit or professional video scaler — functional, no decoration
- Color palette: #0a0a0a background, #1a1a1a panels, #00ff88 accent (green status/active), #ff4444 red for disconnected, #888 for secondary text
- Monospace font (JetBrains Mono or similar) for all UI labels and status text
- The screen capture fills the entire dark viewport — everything else is secondary
- Top bar and bottom toolbar should be semi-transparent overlays that disappear when no interaction for 3 seconds (like a video player)

## Host info page (`/host`)
- Shows the Supabase project URL and anon key (from env) so the Python script can be configured
- Shows a simple status: "Host connected / disconnected"
- Shows instructions for running the Python script

## Tech notes
- Use Supabase JS client for Storage and Realtime
- Poll for new frame by subscribing to `frame-updates` Realtime channel
- When a new frame notification arrives, fetch the image from Storage with a cache-busting timestamp query param
- The frame image URL: `{SUPABASE_URL}/storage/v1/object/public/screen-frames/latest.jpg?t={timestamp}`

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/1206b096-4490-421e-8952-b7b107367894).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
