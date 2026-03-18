You are an expert HDFS system analyst specializing in block operation health.

Task:
Analyze the sequence of log messages for a single HDFS block operation and determine whether it represents normal or anomalous behavior.

Background Context:
In a healthy HDFS block operation, you typically see:
- Block allocation by the NameSystem
- Block reception at one or more DataNodes
- Successful write operations
- Storage confirmations from multiple DataNodes (usually 3 for replication)
- Clean termination of packet responders
- No error messages or exceptions

Important: Block deletion AFTER successful storage is normal HDFS behavior. Blocks are routinely deleted as part of:
- Temporary file cleanup (e.g., MapReduce intermediate data)
- User-initiated file deletions
- HDFS garbage collection

A session is only anomalous if:
1. There are explicit errors/exceptions, OR
2. The block lifecycle is incomplete (e.g., allocation without storage confirmation)

Instructions:
1. Read through the entire log sequence carefully.
2. Check if storage confirmations (`addStoredBlock`) are present.
3. If storage was confirmed, subsequent deletion is NORMAL.
4. Only flag as anomalous if there are errors OR missing storage confirmations.
5. Note the key observations that influenced your decision.

Output Format:
Return ONLY a JSON object with this structure:
{
    "label": 0 or 1,
    "signals": ["brief observation 1", "brief observation 2", "brief observation 3"]
}

Where:
- label: 0 = Normal, 1 = Anomalous
- signals: 2-3 concise phrases describing the most important observations

Important:
- Be concise and factual in your signals.
- Deletion after storage confirmation = NORMAL
- Missing storage confirmation = ANOMALOUS
- Explicit errors/exceptions = ANOMALOUS

Here are examples of parsed session logs and their classifications:

Example 1 (Normal - complete lifecycle):
    Parsed Session Logs:
        Receiving block blk_6667093857658912327 src: /10.251.73.188:57743 dest: /10.251.73.188:50010
        Receiving block blk_6667093857658912327 src: /10.251.73.188:54097 dest: /10.251.73.188:50010
        BLOCK* NameSystem.allocateBlock: /user/root/rand8/_temporary/_task_200811101024_0015_m_001611_0/part-01611. blk_6667093857658912327
        Receiving block blk_6667093857658912327 src: /10.251.106.37:53888 dest: /10.251.106.37:50010
        PacketResponder 1 for block blk_6667093857658912327 terminating
        Received block blk_6667093857658912327 of size 67108864 from /10.251.73.188
        BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.251.106.37:50010 is added to blk_6667093857658912327 size 67108864
        BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.251.73.188:50010 is added to blk_6667093857658912327 size 67108864
        BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.251.110.160:50010 is added to blk_6667093857658912327 size 67108864
        PacketResponder 2 for block blk_6667093857658912327 terminating
        Received block blk_6667093857658912327 of size 67108864 from /10.251.73.188
        PacketResponder 0 for block blk_6667093857658912327 terminating
        Received block blk_6667093857658912327 of size 67108864 from /10.251.106.37
    Output:
        {
            "label": 0,
            "signals": [
                "successful block reception",
                "block storage confirmations from 3 nodes",
                "normal packet responder termination"
            ]
        }

Example 2 (Normal - complete lifecycle WITH deletion):
    Parsed Session Logs:
        Receiving block blk_842810621657300290 src: /10.251.193.175:48910 dest: /10.251.193.175:50010
        Receiving block blk_842810621657300290 src: /10.251.193.175:47516 dest: /10.251.193.175:50010
        BLOCK* NameSystem.allocateBlock: /user/root/rand4/_temporary/_task_200811101024_0009_m_001521_0/part-01521. blk_842810621657300290
        Receiving block blk_842810621657300290 src: /10.251.31.242:39712 dest: /10.251.31.242:50010
        PacketResponder 1 for block blk_842810621657300290 terminating
        Received block blk_842810621657300290 of size 67108864 from /10.251.193.175
        PacketResponder 2 for block blk_842810621657300290 terminating
        Received block blk_842810621657300290 of size 67108864 from /10.251.193.175
        PacketResponder 0 for block blk_842810621657300290 terminating
        Received block blk_842810621657300290 of size 67108864 from /10.251.31.242
        BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.251.193.175:50010 is added to blk_842810621657300290 size 67108864
        BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.250.18.114:50010 is added to blk_842810621657300290 size 67108864
        BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.251.31.242:50010 is added to blk_842810621657300290 size 67108864
        BLOCK* NameSystem.delete: blk_842810621657300290 is added to invalidSet of 10.250.18.114:50010
        BLOCK* NameSystem.delete: blk_842810621657300290 is added to invalidSet of 10.251.193.175:50010
        BLOCK* NameSystem.delete: blk_842810621657300290 is added to invalidSet of 10.251.31.242:50010
        Deleting block blk_842810621657300290 file /mnt/hadoop/dfs/data/current/subdir49/blk_842810621657300290
    Output:
        {
            "label": 0,
            "signals": [
                "block storage confirmed on 3 nodes before deletion",
                "deletion after successful storage is normal cleanup",
                "no errors or exceptions present"
            ]
        }

Example 3 (Anomalous - incomplete, no storage confirmation):
    Parsed Session Logs:
        BLOCK* NameSystem.allocateBlock: /user/root/randtxt5/_temporary/_task_200811101024_0012_m_001014_0/part-01014. blk_4615226180823858743
        Receiving block blk_4615226180823858743 src: /10.251.30.179:36961 dest: /10.251.30.179:50010
    Output:
        {
            "label": 1,
            "signals": [
                "incomplete block operation",
                "missing block storage confirmation",
                "early termination of block lifecycle"
            ]
        }

Example 4 (Anomalous - explicit error):
    Parsed Session Logs:
        BLOCK* NameSystem.allocateBlock: /user/root/randtxt/_temporary/_task_200811092030_0003_m_000269_0/part-00269. blk_-152459496294138933
        Receiving block blk_-152459496294138933 src: /10.251.74.134:53158 dest: /10.251.74.134:50010
        Receiving block blk_-152459496294138933 src: /10.251.74.134:51159 dest: /10.251.74.134:50010
        writeBlock blk_-152459496294138933 received exception java.io.IOException: Could not read from stream
    Output:
        {
            "label": 1,
            "signals": [
                "io exception during writeBlock",
                "explicit failure message",
                "block write interruption"
            ]
        }
