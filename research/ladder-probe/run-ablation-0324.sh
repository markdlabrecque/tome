#!/usr/bin/env bash
# The #35/#36 prompt ablation, all four conditions re-run on Ollama 0.32.4.
#
# Why all four rather than just the two new arms: the committed 14b replicates predate the
# 0.32.4 upgrade, and the fenced arm does not reproduce across it (Event -> Fact 1 -> 3 on
# Mark's single 0324 replicate). Comparing a new arm against a pre-upgrade baseline would be
# a cross-runtime comparison, so control and fenced are re-measured here too.
#
# Replicate-interleaved on purpose: if this dies partway, every condition has the same
# number of replicates rather than the early conditions having all of them.
#
# Serialized by construction — never two GPU jobs on this box (raw-contended.jsonl.bak).
set -u
cd "$(dirname "$0")"

run() {  # run <prompt> <out>
  local prompt="$1" out="$2"
  echo "=== $(date -Is)  $prompt -> $out"
  PROMPT="$prompt" OUT="$out" ARMS=qwen3:14b FORMAT=json python3 run.py
  echo "=== $(date -Is)  done $out ($(grep -c . "$out" 2>/dev/null || echo 0) records)"
}

# replicate 1 — fenced r1 is Mark's raw-fenced-0324.jsonl, already present
run prompt.txt                         raw-control-0324.jsonl
run prompt-fenced-nogate.txt           raw-nogate-0324.jsonl
run prompt-fenced-nogate-noconf.txt    raw-noconf-0324.jsonl

# replicate 2
run prompt-fenced.txt                  raw-fenced-0324-r2.jsonl
run prompt.txt                         raw-control-0324-r2.jsonl
run prompt-fenced-nogate.txt           raw-nogate-0324-r2.jsonl
run prompt-fenced-nogate-noconf.txt    raw-noconf-0324-r2.jsonl

# replicate 3
run prompt-fenced.txt                  raw-fenced-0324-r3.jsonl
run prompt.txt                         raw-control-0324-r3.jsonl
run prompt-fenced-nogate.txt           raw-nogate-0324-r3.jsonl
run prompt-fenced-nogate-noconf.txt    raw-noconf-0324-r3.jsonl

echo "=== $(date -Is)  ALL ARMS COMPLETE"
