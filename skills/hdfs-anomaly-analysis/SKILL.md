---
name: hdfs-anomaly-analysis
description: HDFS session anomaly classification and explanation. Use when the task is to label an HDFS session as normal or anomalous and explain the decision from the observed session flow.
metadata:
  owner: iexplain
  version: "1"
---

## Focus

- parse the session flow
- detect explicit failure markers
- detect broken normal flow

## Strong anomaly evidence

- exceptions
- socket timeout
- failed block write or replication
- abrupt termination after an error

## Normal flow pattern

- receive block
- acknowledgements or packet handling
- clean termination
