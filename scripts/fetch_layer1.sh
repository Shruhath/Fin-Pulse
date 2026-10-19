#!/usr/bin/env bash
# Fetch the free "layer 1" benchmark datasets (GitHub + Hugging Face) into data-set/layer1,
# keeping DATA ONLY: code, model outputs, images and duplicate copies are dropped.
#
# Result:  data-set/layer1/<name>/        the data files
#          data-set/layer1/_docs/<name>/  licence + dataset card (needed for attribution)
#          data-set/layer1/MANIFEST.tsv   source, commit, date, licence, notes
#
#   ./scripts/fetch_layer1.sh              fetch everything (and trim any untrimmed folder)
#   ./scripts/fetch_layer1.sh --list       show what would be fetched
#   ONLY="sentfin finentity" ./scripts/fetch_layer1.sh     fetch a subset
#   REFRESH=1 ./scripts/fetch_layer1.sh    delete and re-fetch existing folders
#   FULL=1 ./scripts/fetch_layer1.sh       keep the complete repos (no trimming)
#   DEST=/some/dir ./scripts/fetch_layer1.sh   different output folder
#
# Safe to re-run. Needs: git, git-lfs, network. No account, token or payment is needed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DEST:-$ROOT/data-set/layer1}"
ONLY="${ONLY:-}"
REFRESH="${REFRESH:-0}"
FULL="${FULL:-0}"

# name | url | licence | role | note | data files to keep (globs) | docs to keep (globs)
DATASETS=$(cat <<'LIST'
sentfin|https://github.com/pyRis/SEntFiN|MIT|Indian headlines, entity-level sentiment|Decisions column is a Python-dict string, not JSON. Cite the repo; do not re-host.|SEntFiN.csv entity_list_comprehensive.csv|LICENSE README.md
finentity|https://huggingface.co/datasets/yixuantt/FinEntity|ODC-BY|entity spans + sentiment|No official test split; make your own.|FinEntity.json|README.md
financial_phrasebank|https://huggingface.co/datasets/takala/financial_phrasebank|CC BY-NC-SA 3.0|sentence sentiment warm-up|TRAIN AND CITE ONLY. Never bundle into the published release.|data/FinancialPhraseBank-v1.0.zip|README.md
fiqa-2018|https://huggingface.co/datasets/pauri32/fiqa-2018|none stated|aspect sentiment (Task 1)|Mirror: the official Drive links are dead.|train.csv validation.csv test.csv|README.md
tradetheevent|https://github.com/Zhihan1996/TradeTheEvent|none|corporate event taxonomy (EDT)|The data is NOT in the repo: Google Drive folder https://drive.google.com/drive/folders/1xKjd9hzA8UTn2DXVIYYnX5TngNAMom19 (303,893 articles, 2020-21). Docs kept for the event definitions.||README.md data/README.md
ectsum|https://github.com/rajdeep345/ECTSum|GPL-3.0 (repo)|long-document summaries|EVALUATION ONLY. Never bundle into the published release.|data/final|LICENSE.txt README.md
findver|https://github.com/yilunzhao/FinDVer|MIT (repo)|claim verification over financial documents|Model outputs and code removed.|data/test.json data/testmini.json financial_reports|LICENSE README.md
indiafinbench|https://huggingface.co/datasets/Rajveer-code/IndiaFinBench|CC BY 4.0 (data)|SEBI/RBI questions incl. contradiction items|Tests the claim verifier on Indian regulatory text.|data/*.parquet|README.md
sebi-circulars|https://huggingface.co/datasets/opnsrcntrbtrian/sebi-circulars|CC BY 4.0 (annotations)|SEBI circulars, chunked, for retrieval|Parquet only; the JSONL copies were verified identical and dropped.|chunks/chunks.parquet corpus/corpus.parquet citation-normalization/citation-normalization.parquet eval/eval.parquet golden_v7/golden_v7.parquet lineage/lineage.parquet supersession-pairs/supersession-pairs.parquet|README.md metadata.json manifest.json AIKOSH_SUBMISSION_PACK/LICENSING.txt
nse-india-security-master|https://huggingface.co/datasets/tickertruthorg/nse-india-security-master|CC BY 4.0|NSE symbols + ISIN seed list|No alias field; pair with the SEntFiN entity list.|data/nse_security_master.csv|README.md
twitter-financial-news-sentiment|https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment|MIT tag|optional social text|LABEL_0 = Bearish, LABEL_2 = Neutral. No test split.|sent_train.csv sent_valid.csv|README.md sent_dataset_meta.txt
indian_financial_news|https://huggingface.co/datasets/kdave/Indian_Financial_News|none|SILVER ONLY: Indian news with weak labels|GPT-labelled; balanced and sorted by label. Never use for evaluation.|training_data_26000.csv|README.md
LIST
)

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; fi
if [[ "${1:-}" == "--list" ]]; then
  printf '%-34s %-24s %s\n' NAME LICENCE ROLE
  while IFS='|' read -r name url lic role note keep docs; do printf '%-34s %-24s %s\n' "$name" "$lic" "$role"; done <<<"$DATASETS"
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

mkdir -p "$DEST/_docs"
ok=(); skipped=(); trimmed=(); failed=()

# Keep only the data files (and the licence/card) of a full copy; replace the folder with the result.
trim_dir() {
  local dir="$1" name="$2" keep="$3" docs="$4" note="$5"
  local stage="$dir.stage" dd="$DEST/_docs/$name"
  rm -rf "${stage:?}" "${dd:?}"; mkdir -p "$stage" "$dd"
  ( cd "$dir" && shopt -s nullglob && for p in $keep; do cp -a --parents "$p" "$stage/"; done )
  ( cd "$dir" && shopt -s nullglob && for p in $docs; do cp -a --parents "$p" "$dd/"; done
    [[ -f .manifest-line ]] && cp .manifest-line "$dd/.manifest-line" )
  if [[ -z "$keep" ]]; then
    printf 'No data files in this repository.\n%s\n' "$note" > "$stage/NO_DATA_IN_REPO.txt"
  elif [[ -z "$(ls -A "$stage")" ]]; then
    echo "WARN   $name: nothing matched the keep list; leaving the full copy" >&2
    rm -rf "${stage:?}" "${dd:?}"; return 1
  fi
  rm -rf "${dir:?}"; mv "$stage" "$dir"
}

fetch_one() {
  local name="$1" url="$2" lic="$3" role="$4" note="$5" keep="$6" docs="$7"
  local dir="$DEST/$name" tmp="$DEST/.tmp-$name"
  if [[ -n "$ONLY" && " $ONLY " != *" $name "* ]]; then return 0; fi
  if [[ -d "$dir" && "$REFRESH" == "1" ]]; then rm -rf "${dir:?}" "${DEST:?}/_docs/$name"; fi

  if [[ -d "$dir" ]]; then
    if [[ "$FULL" != "1" && ! -d "$DEST/_docs/$name" ]]; then
      echo "trim   $name (existing full copy)"
      [[ -f "$dir/.manifest-line" ]] || printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$url" unknown "$(date -u +%F)" "$lic" "$role" "$note" > "$dir/.manifest-line"
      if trim_dir "$dir" "$name" "$keep" "$docs" "$note"; then trimmed+=("$name"); else failed+=("$name"); fi
    else
      echo "skip   $name (already there; REFRESH=1 to re-fetch)"; skipped+=("$name")
    fi
    return 0
  fi

  echo "fetch  $name  <-  $url"
  rm -rf "${tmp:?}"
  if ! timeout 3600 git "${GIT_LFS_CFG[@]}" clone --quiet --depth 1 "$url" "$tmp"; then
    echo "FAILED $name" >&2; rm -rf "${tmp:?}"; failed+=("$name"); return 0
  fi
  local sha; sha="$(git -C "$tmp" rev-parse HEAD 2>/dev/null || echo unknown)"
  if grep -rIl --exclude-dir=.git '^version https://git-lfs.github.com/spec/v1' "$tmp" 2>/dev/null | head -1 | grep -q .; then
    echo "WARN   $name has unresolved LFS pointer files (re-run, or check your network)" >&2
  fi
  rm -rf "${tmp:?}/.git"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$url" "$sha" "$(date -u +%F)" "$lic" "$role" "$note" > "$tmp/.manifest-line"
  if [[ "$FULL" != "1" ]]; then
    trim_dir "$tmp" "$name" "$keep" "$docs" "$note" || { failed+=("$name"); return 0; }
  fi
  mv "$tmp" "$dir"
  ok+=("$name")
}

while IFS='|' read -r name url lic role note keep docs; do
  [[ -n "$name" ]] && fetch_one "$name" "$url" "$lic" "$role" "$note" "$keep" "$docs"
done <<<"$DATASETS"

# manifest rebuilt from what is on disk
{
  printf 'name\turl\tcommit\tfetched\tlicence\trole\tnote\n'
  cat "$DEST"/_docs/*/.manifest-line "$DEST"/*/.manifest-line 2>/dev/null
} > "$DEST/MANIFEST.tsv"

cat > "$DEST/README.txt" <<'TXT'
Layer 1: public benchmark datasets (free downloads), DATA ONLY.

  <name>/          the data files
  _docs/<name>/    each dataset's licence and dataset card (keep for attribution and citation)
  MANIFEST.tsv     source URL, commit, fetch date, licence, notes

Rules
- Never commit this folder (data-set/ is git-ignored).
- financial_phrasebank (CC BY-NC-SA) and ectsum (GPL-3.0): train/evaluate and cite only. Never bundle them into the published FinPulse release.
- indian_financial_news has weak, GPT-generated labels: silver data only, never for evaluation.
- sentfin: cite the GitHub repo; do not re-host the CSV.
- tradetheevent has no data here: see tradetheevent/NO_DATA_IN_REPO.txt for the Google Drive folder.

Not fetched by git (get these by hand if needed)
- IN-Abs (legal summaries): https://zenodo.org/record/7151679  (CC BY 4.0, about 98 MB)
- SEBI enforcement-order metadata: https://data.mendeley.com/datasets/ppdk9pzfdp/2  (CC BY 4.0)
- SENTiVENT (events): https://osf.io/enu2k/
TXT

echo
echo "=== summary ==="
echo "fetched: ${#ok[@]}   trimmed: ${#trimmed[@]}   skipped: ${#skipped[@]}   failed: ${#failed[@]}"
[[ ${#failed[@]} -gt 0 ]] && echo "failed:  ${failed[*]}"
du -sh "$DEST"/*/ 2>/dev/null | sed "s#$DEST/##"
echo "total:   $(du -sh "$DEST" | cut -f1)"
echo "output:  $DEST"
[[ ${#failed[@]} -eq 0 ]]
