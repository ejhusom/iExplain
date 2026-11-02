---
name: hdfs-stream-analysis
description: Classify multiple HDFS block operations from an interleaved log stream. Use when the task provides a stream.log with lines from several blocks mixed together and asks for a normal/anomalous label per block ID.
metadata:
  owner: iexplain
  version: "1"
---

## Task

`stream.log` interleaves log lines from several HDFS block operations. Work one block
at a time: collect every line whose block ID matches, reconstruct that block's
lifecycle, and classify it.

## Anomaly criteria

A block is **normal (0)** when its lifecycle completes:

- block allocation by the NameSystem
- block reception on one or more DataNodes
- storage confirmations (`addStoredBlock`) — usually 3 for replication
- clean termination of packet responders

Deletion **after** storage confirmation is normal cleanup (temporary files,
user deletions, garbage collection).

A block is **anomalous (1)** only when:

1. there is an explicit error or exception (for example `writeBlock ... received
   exception`, socket timeout, failed replication), or
2. the lifecycle is incomplete (allocation/reception without any
   `addStoredBlock` storage confirmation).

## Examples

Normal — full lifecycle with storage confirmations on three nodes, then deletion:
allocateBlock, Receiving block, addStoredBlock x3, PacketResponder terminating,
NameSystem.delete. Label 0.

Anomalous — allocation and reception but no `addStoredBlock` confirmation: the block
lifecycle never completes. Label 1.

Anomalous — `writeBlock blk_... received exception java.io.IOException`: an explicit
failure. Label 1.

## Output

Return ONLY this JSON object, with exactly one entry per candidate block ID:

```
{"blocks": [{"block_id": "blk_-123", "label": 0}, {"block_id": "blk_456", "label": 1}]}
```

label: 0 = normal, 1 = anomalous. Do not add prose, headings, or extra fields.
