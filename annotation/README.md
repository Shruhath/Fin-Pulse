# Annotation

Gold labels for the 120 frozen passages are made in Label Studio. The pipeline selects and freezes
the passages, exports them as tasks, and imports the finished annotations.

```bash
docker compose -f ../infra/docker-compose.yml --profile annotation up -d label-studio   # http://127.0.0.1:8085
cd ../server
uv run finpulse gold select                    # freeze passages (40 AO, 15 WTM, 15 settlement, 50 NCLT by default)
uv run finpulse gold config                    # writes annotation/label_config.xml
uv run finpulse gold tasks                     # writes annotation/tasks.json
#   create a Label Studio project, paste label_config.xml as its labelling config, import tasks.json
uv run finpulse gold import export.json --annotators 1=asha,2=ben,3=chitra
uv run finpulse gold agreement                 # kappa on the calibration passages, against the gates
uv run finpulse gold eval --llm                # scores every stage against gold, records the results
```

Rules the code enforces:

- A passage's text is frozen with its SHA-256 and OCR provenance. Spans are checked against it on import; a
  span that does not match is skipped and counted, never repaired.
- Gold and silver labels live in separate rows (`annotations.label_source`) and separate export files.
- A calibration passage with several annotators is scored only after someone labels it as `adjudicated`.
- Annotators do not see model output while labelling.
