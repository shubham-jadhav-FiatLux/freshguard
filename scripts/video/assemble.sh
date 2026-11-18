#!/usr/bin/env bash
# Assembles slide stills + recorded clips into one 1280x720 H.264 MP4 with a silent audio track.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"; OUT="$1"
W="$S/work"; rm -rf "$W"; mkdir -p "$W"
enc=(-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -c:a aac -b:a 96k -ar 48000 -ac 2 -shortest)
i=0
still() {  # still <png> <seconds>
  i=$((i+1)); local d="$2"; local fo; fo=$(python3 -c "print(max(0,$d-0.35))")
  ffmpeg -loglevel error -y -loop 1 -t "$d" -i "$1" -f lavfi -t "$d" -i anullsrc=r=48000:cl=stereo \
    -vf "scale=1280:720,fps=30,fade=t=in:st=0:d=0.35,fade=t=out:st=$fo:d=0.35" "${enc[@]}" "$W/$(printf %02d $i).mp4"
}
clip() {   # clip <webm> <trim-start-seconds>
  i=$((i+1)); local dur; dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1")
  local len; len=$(python3 -c "print(round($dur-$2-0.2,2))"); local fo; fo=$(python3 -c "print(max(0,$len-0.35))")
  ffmpeg -loglevel error -y -ss "$2" -t "$len" -i "$1" -f lavfi -t "$len" -i anullsrc=r=48000:cl=stereo \
    -vf "scale=1280:720,fps=30,fade=t=in:st=0:d=0.35,fade=t=out:st=$fo:d=0.35" "${enc[@]}" "$W/$(printf %02d $i).mp4"
}
still "$S/slides/s1-01.png" 4.5
still "$S/slides/s2-02.png" 7
still "$S/slides/s3-03.png" 6
clip  "$S/clips/ui_ask.webm" 1.0
clip  "$S/clips/ui_paste.webm" 1.0
clip  "$S/clips/term1.webm" 1.0
clip  "$S/clips/term2.webm" 1.0
still "$S/slides/s5-05.png" 8
clip  "$S/clips/dash.webm" $(cat "$S/dash_trim.txt")
still "$S/slides/s10-10.png" 8
still "$S/slides/s13-13.png" 5
ls "$W"/*.mp4 | sed "s/.*/file '&'/" > "$W/list.txt"
ffmpeg -loglevel error -y -f concat -safe 0 -i "$W/list.txt" -c copy -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
