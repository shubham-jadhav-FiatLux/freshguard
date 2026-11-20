#!/usr/bin/env bash
# Assembles slide stills + recorded clips into one 1280x720 H.264 MP4 at 25 fps (the capture rate,
# so no frames are duplicated), then adds the generated soundtrack. Usage: assemble.sh <out.mp4>
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"; OUT="$1"
PY="${PY:-python3}"   # needs numpy (soundtrack.py, calibrate.py)
W="$S/work"; rm -rf "$W"; mkdir -p "$W"
enc=(-an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 25)
i=0; T=0; echo "[" > "$W/timeline.json"; sep=""
calc() { python3 -c "print(round($1,3))"; }
still() {  # still <png> <seconds>
  i=$((i+1)); local d="$2"; local fo; fo=$(calc "max(0,$d-0.35)")
  ffmpeg -loglevel error -y -loop 1 -t "$d" -i "$1" \
    -vf "scale=1280:720,fps=25,fade=t=in:st=0:d=0.35,fade=t=out:st=$fo:d=0.35" "${enc[@]}" "$W/$(printf %02d $i).mp4"
  T=$(calc "$T+$d")
}
clip() {   # clip <name> <trim-start-seconds>
  i=$((i+1)); local f="$S/clips/$1.webm" dur len fo
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  len=$(calc "$dur-$2-0.2"); fo=$(calc "max(0,$len-0.35)")
  ffmpeg -loglevel error -y -ss "$2" -t "$len" -i "$f" \
    -vf "scale=1280:720,fps=25,fade=t=in:st=0:d=0.35,fade=t=out:st=$fo:d=0.35" "${enc[@]}" "$W/$(printf %02d $i).mp4"
  printf '%s{"clip": "%s", "start": %s, "trim": %s, "len": %s}\n' "$sep" "$1" "$T" "$2" "$len" >> "$W/timeline.json"; sep=","
  T=$(calc "$T+$len")
}
still "$S/slides/s-01.png" 4.5
still "$S/slides/s-02.png" 7
still "$S/slides/s-03.png" 6
clip  ui_ask 1.0
clip  ui_paste 1.0
clip  term1 1.0
clip  term2 1.0
still "$S/slides/s-05.png" 8
clip  dash "$(cat "$S/dash_trim.txt")"
still "$S/slides/s-10.png" 8
still "$S/slides/s-13.png" 5
echo "]" >> "$W/timeline.json"
ls "$W"/[0-9]*.mp4 | sed "s/.*/file '&'/" > "$W/list.txt"
ffmpeg -loglevel error -y -f concat -safe 0 -i "$W/list.txt" -c copy "$W/video.mp4"
TOTAL=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$W/video.mp4")
"$PY" "$S/calibrate.py"
"$PY" "$S/soundtrack.py" "$W/timeline.json" "$TOTAL" "$W/soundtrack.wav"
ffmpeg -loglevel error -y -i "$W/video.mp4" -i "$W/soundtrack.wav" -c:v copy -ar 48000 -c:a aac -b:a 160k -shortest -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
