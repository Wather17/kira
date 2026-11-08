# Local test artifacts

This directory is intentionally excluded from Git because the Kindle test
fixtures and generated EPUBs are large binary files.

The local Kindle experiment is kept under:

```text
tests/artifacts/kindle/attack-on-titan/chapter-01/
```

It contains the source chapter, the generated EPUB variants, and the local
results report. The automated Python tests remain in the tracked `tests/`
directory; this folder is only for reproducible local/device experiments.
