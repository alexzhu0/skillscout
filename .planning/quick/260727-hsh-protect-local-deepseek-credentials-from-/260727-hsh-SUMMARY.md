---
quick_id: 260727-hsh
status: complete
---

# Protect local DeepSeek credentials from Git — Summary

## Completed

- Added the root `.env` Git ignore boundary before copying the authorized local credential file.
- Created the local `.env` with owner-only `0600` permissions.
- Verified the file is ignored, untracked, and absent from scoped Git status.

## Verification

```text
git check-ignore -q -- .env
stat -f '%Lp' .env  # 600
git status --short -- .env  # empty
```

No credential content was read, printed, staged, or committed.
