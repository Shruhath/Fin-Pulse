#!/usr/bin/env bash
# Fetch the free "layer 1" benchmark datasets (GitHub + Hugging Face) into data-set/layer1.
#
#   ./scripts/fetch_layer1.sh              fetch everything
#   ./scripts/fetch_layer1.sh --list       show what would be fetched
#   ONLY="sentfin finentity" ./scripts/fetch_layer1.sh     fetch a subset
#   REFRESH=1 ./scripts/fetch_layer1.sh    delete and re-clone existing folders
#   KEEP_GIT=1 ./scripts/fetch_layer1.sh   keep each repo's .git (default: removed, to save disk)
#   DEST=/some/dir ./scripts/fetch_layer1.sh   different output folder
#
# Safe to re-run: folders that already exist are skipped. Needs: git, git-lfs, network.
# No account, token or payment is needed for any of these.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DEST:-$ROOT/data-set/layer1}"
ONLY="${ONLY:-}"
REFRESH="${REFRESH:-0}"
KEEP_GIT="${KEEP_GIT:-0}"

# name | url | licence | role | note
DATASETS=$(cat <<'LIST'
sentfin|https://github.com/pyRis/SEntFiN|MIT|Indian headlines, entity-level sentiment|SEntFiN.csv + entity_list_comprehensive.csv. Decisions column is a Python-dict string, not JSON. Cite the repo; do not re-host.
finentity|https://huggingface.co/datasets/yixuantt/FinEntity|ODC-BY|entity spans + sentiment|No official test split; make your own.
financial_phrasebank|https://huggingface.co/datasets/takala/financial_phrasebank|CC BY-NC-SA 3.0|sentence sentiment warm-up|TRAIN AND CITE ONLY. Never bundle into the published release. Raw zip inside.
fiqa-2018|https://huggingface.co/datasets/pauri32/fiqa-2018|none stated|aspect sentiment (Task 1)|Mirror: the official Drive links are dead. Row count differs between mirrors.
tradetheevent|https://github.com/Zhihan1996/TradeTheEvent|none|corporate event taxonomy (EDT)|The data itself is on a Google Drive linked in the README, not in the repo.
ectsum|https://github.com/rajdeep345/ECTSum|GPL-3.0 (repo)|long-document summaries|EVALUATION ONLY. Never bundle into the published release. Data is in data/final.
findver|https://github.com/yilunzhao/FinDVer|MIT (repo)|claim verification over financial documents|Check the README for where the data lives.
indiafinbench|https://huggingface.co/datasets/Rajveer-code/IndiaFinBench|CC BY 4.0 (data)|SEBI/RBI questions incl. contradiction items|Tests the claim verifier on Indian regulatory text.
sebi-circulars|https://huggingface.co/datasets/opnsrcntrbtrian/sebi-circulars|CC BY 4.0 (annotations)|SEBI circulars, chunked, for retrieval|Can be large.
nse-india-security-master|https://huggingface.co/datasets/tickertruthorg/nse-india-security-master|CC BY 4.0|NSE symbols + ISIN seed list|No alias field; pair with the SEntFiN entity list.
twitter-financial-news-sentiment|https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment|MIT tag|optional social text|LABEL_0 = Bearish, LABEL_2 = Neutral. No test split.
indian_financial_news|https://huggingface.co/datasets/kdave/Indian_Financial_News|none|SILVER ONLY: Indian news with weak labels|Labels came from a GPT spreadsheet add-on; classes are perfectly balanced and the file is sorted by label. Never use for evaluation.
LIST
)

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; fi
if [[ "${1:-}" == "--list" ]]; then
  printf '%-34s %-22s %s\n' NAME LICENCE ROLE
  while IFS='|' read -r name url lic role note; do printf '%-34s %-22s %s\n' "$name" "$lic" "$role"; done <<<"$DATASETS"
  echo; echo "output: $DEST"; exit 0
fi

command -v git >/dev/null 2>&1 || { echo "git is not installed." >&2; exit 1; }
GIT_LFS_CFG=()
if git lfs version >/dev/null 2>&1; then
  # Enable LFS for these clones only, without touching your global git config.
  GIT_LFS_CFG=(-c filter.lfs.required=true
               -c "filter.lfs.smudge=git-lfs smudge -- %f"
               -c "filter.lfs.process=git-lfs filter-process"
               -c "filter.lfs.clean=git-lfs clean -- %f")
elif [[ "${SKIP_LFS_CHECK:-0}" == "1" ]]; then
  echo "WARN: git-lfs missing; Hugging Face datasets will contain empty pointer files." >&2
else
  echo "git-lfs is not installed. Hugging Face stores data files with it; without it you get empty pointer files." >&2
  echo "  Arch/CachyOS:  sudo pacman -S git-lfs" >&2
  echo "  Debian/Ubuntu: sudo apt install git-lfs" >&2
  echo "Install it and re-run. (GitHub-only test: SKIP_LFS_CHECK=1 ONLY=\"sentfin\" ./scripts/fetch_layer1.sh)" >&2
  exit 1
fi
export GIT_TERMINAL_PROMPT=0   # fail instead of asking for credentials

mkdir -p "$DEST"
ok=(); skipped=(); failed=()

fetch_one() {
  local name="$1" url="$2" lic="$3" role="$4" note="$5"
  local dir="$DEST/$name" tmp="$DEST/.tmp-$name"
  if [[ -n "$ONLY" && " $ONLY " != *" $name "* ]]; then return 0; fi
  if [[ -d "$dir" && "$REFRESH" == "1" ]]; then rm -rf "${dir:?}"; fi
  if [[ -d "$dir" ]]; then echo "skip   $name (already there; REFRESH=1 to re-clone)"; skipped+=("$name"); return 0; fi

  echo "fetch  $name  <-  $url"
  rm -rf "${tmp:?}"
  if ! timeout 3600 git "${GIT_LFS_CFG[@]}" clone --quiet --depth 1 "$url" "$tmp"; then
    echo "FAILED $name" >&2; rm -rf "${tmp:?}"; failed+=("$name"); return 0
  fi
  local sha; sha="$(git -C "$tmp" rev-parse HEAD 2>/dev/null || echo unknown)"
  if grep -rIl --exclude-dir=.git '^version https://git-lfs.github.com/spec/v1' "$tmp" 2>/dev/null | head -1 | grep -q .; then
    echo "WARN   $name has unresolved LFS pointer files (re-run, or check your network)" >&2
  fi
  [[ "$KEEP_GIT" == "1" ]] || rm -rf "${tmp:?}/.git"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$url" "$sha" "$(date -u +%F)" "$lic" "$role" "$note" > "$tmp/.manifest-line"
  mv "$tmp" "$dir"
  ok+=("$name")
}

while IFS='|' read -r name url lic role note; do
  [[ -n "$name" ]] && fetch_one "$name" "$url" "$lic" "$role" "$note"
done <<<"$DATASETS"

# manifest + reminders, rebuilt from what is actually on disk
{
  printf 'name\turl\tcommit\tfetched\tlicence\trole\tnote\n'
  cat "$DEST"/*/.manifest-line 2>/dev/null
} > "$DEST/MANIFEST.tsv"

cat > "$DEST/README.txt" <<'TXT'
Layer 1: public benchmark datasets (free downloads). See MANIFEST.tsv for source, commit, licence and notes.

Rules
- Never commit this folder (data-set/ is git-ignored).
- financial_phrasebank (CC BY-NC-SA) and ectsum (GPL-3.0): train/evaluate and cite only. Never bundle them into the published FinPulse release.
- indian_financial_news has weak, GPT-generated labels: silver data only, never for evaluation.
- sentfin: cite the GitHub repo; do not re-host the CSV.

Not fetched by git (get these by hand if needed)
- EDT data: Google Drive folder linked from tradetheevent/README.md
- IN-Abs (legal summaries): https://zenodo.org/record/7151679  (CC BY 4.0, about 98 MB)
- SEBI enforcement-order metadata: https://data.mendeley.com/datasets/ppdk9pzfdp/2  (CC BY 4.0)
- SENTiVENT (events): https://osf.io/enu2k/
TXT

echo
echo "=== summary ==="
echo "fetched: ${#ok[@]}   skipped: ${#skipped[@]}   failed: ${#failed[@]}"
[[ ${#failed[@]} -gt 0 ]] && echo "failed:  ${failed[*]}"
du -sh "$DEST"/*/ 2>/dev/null | sed "s#$DEST/##"
echo "output:  $DEST"
echo "manifest: $DEST/MANIFEST.tsv   (read $DEST/README.txt for licence rules)"
[[ ${#failed[@]} -eq 0 ]]
