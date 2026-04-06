```
==============================================================================
  PBS LAYER OUTPUT ANALYZER v3 — Post-Fix Verification
  Bid Period: Test Bid 2 (ORD, January 2026)
  Analysis: 2026-03-29 22:35
==============================================================================

  Bid: dbdba365-6257-4b5f-9a65-8a4d8c54e93e
  Sequences in pool: 1705
  Bid properties: 2
    string_days_off_starting: 2026-01-16 (L1)
    prefer_pairing_type: ipd (L1,2)
  Seniority: 5000 / 10000 (None%)
  Credit range: 70h - 90h
  Commute from: N/A

Running optimizer (7 layers, CP-SAT)...
  Saved 49 entries to fresh_entries_v3.json
  Layers populated: [1, 2, 3, 4, 5, 6, 7]
    L1: 9 sequences
    L2: 4 sequences
    L3: 6 sequences
    L4: 6 sequences
    L5: 6 sequences
    L6: 9 sequences
    L7: 9 sequences

==============================================================================
  PART 1: LEGALITY AUDIT
==============================================================================

  Layer |  Dates |   Rest |       Credit | Days Off |  7-Day Blk | Multi-OPS
  ------+--------+--------+--------------+----------+------------+----------
  L  1 |   PASS |   PASS |    90.0 PASS |  12 PASS |  27.5 PASS |      PASS
  L  2 |   PASS |   PASS |    89.3 PASS |  16 PASS |  21.8 PASS |      PASS
  L  3 |   PASS |   PASS |    90.0 PASS |  12 PASS |  29.9 PASS |      PASS
  L  4 |   PASS |   PASS |    90.0 PASS |  12 PASS |  29.0 PASS |      PASS
  L  5 |   PASS |   PASS |    90.0 FAIL |  12 PASS |  28.9 PASS |      PASS
  L  6 |   PASS |   PASS |    90.0 PASS |  12 PASS |  28.2 PASS |      PASS
  L  7 |   PASS |   PASS |    90.0 PASS |  12 PASS |  25.4 PASS |      PASS

  LEGALITY FAILURES DETECTED:
    L5: Credit 90.0h > max 88h

  Layer 1 sequences:
    SEQ 23968: d 1- 2 (2d) | TPAY 10.0h | Block 6.1h | turn
    SEQ 24062: d 3- 4 (2d) | TPAY 10.0h | Block 9.4h | turn
    SEQ 24128: d 5- 6 (2d) | TPAY 10.0h | Block 8.8h | turn
    SEQ 24294: d 8- 9 (2d) | TPAY 10.0h | Block 6.7h | turn
    SEQ 24380: d10-11 (2d) | TPAY 10.0h | Block 9.6h | turn
    SEQ 24457: d12-13 (2d) | TPAY 10.0h | Block 8.5h | turn
    SEQ 24576: d15-16 (2d) | TPAY 10.0h | Block 9.4h | turn
    SEQ 23774: d17-18 (2d) | TPAY 10.0h | Block 8.7h | turn
    SEQ 24713: d19-20 (2d) | TPAY 10.0h | Block 8.4h | turn
    7-day block warnings (>25h):
      d4-10: 25.0h
      d5-11: 25.1h
      d9-15: 26.2h
      d10-16: 27.5h
      d11-17: 27.1h
      d12-18: 26.6h
      d13-19: 26.5h
      d14-20: 26.5h
      d15-21: 26.5h

  Layer 2 sequences:
    SEQ   663: d 9-12 (4d) | TPAY 29.6h | Block 21.8h | NRT,LAS
    SEQ   678: d 2- 5 (4d) | TPAY 29.2h | Block 21.5h | NRT,LAS
    SEQ 24928: d25-27 (3d) | TPAY 15.5h | Block 14.9h | MIA
    SEQ 24643: d17-19 (3d) | TPAY 15.0h | Block 12.0h | PHX

  Layer 3 sequences:
    SEQ 24096: d 4- 6 (3d) | TPAY 15.0h | Block 14.2h | DEN
    SEQ 24257: d 7- 9 (3d) | TPAY 15.0h | Block 14.9h | PDX
    SEQ 24420: d11-13 (3d) | TPAY 15.0h | Block 13.6h | PHX,MCO
    SEQ  5494: d14-16 (3d) | TPAY 15.0h | Block 14.7h | MIA
    SEQ 24673: d18-20 (3d) | TPAY 15.0h | Block 14.9h | PDX
    SEQ 24800: d21-23 (3d) | TPAY 15.0h | Block 15.0h | PDX
    7-day block warnings (>25h):
      d3-9: 29.1h
      d4-10: 29.1h
      d5-11: 28.9h
      d6-12: 28.7h
      d7-13: 28.5h
      d8-14: 28.4h
      d9-15: 28.4h
      d10-16: 28.3h
      d11-17: 28.3h
      d12-18: 28.7h
      d13-19: 29.1h
      d14-20: 29.5h
      d15-21: 29.6h
      d16-22: 29.7h
      d17-23: 29.9h
      d18-24: 29.9h

  Layer 4 sequences:
    SEQ 24164: d 5- 7 (3d) | TPAY 15.0h | Block 14.2h | SAN
    SEQ 23812: d 8-10 (3d) | TPAY 15.0h | Block 14.4h | SFO
    SEQ 24463: d12-14 (3d) | TPAY 15.0h | Block 14.4h | PDX
    SEQ 24559: d15-17 (3d) | TPAY 15.0h | Block 13.2h | MIA
    SEQ 24707: d19-21 (3d) | TPAY 15.0h | Block 14.1h | MIA
    SEQ  5305: d23-25 (3d) | TPAY 15.0h | Block 14.8h | MIA
    7-day block warnings (>25h):
      d4-10: 28.5h
      d5-11: 28.5h
      d6-12: 28.6h
      d7-13: 28.7h
      d8-14: 28.8h
      d9-15: 28.4h
      d10-16: 28.0h
      d11-17: 27.6h
      d12-18: 27.6h
      d13-19: 27.5h
      d14-20: 27.4h
      d15-21: 27.3h
      d19-25: 29.0h

  Layer 5 sequences:
    SEQ 23981: d 1- 3 (3d) | TPAY 15.0h | Block 14.4h | PHX
    SEQ 24146: d 5- 7 (3d) | TPAY 15.0h | Block 14.4h | SFO
    SEQ 24303: d 8-10 (3d) | TPAY 15.0h | Block 13.8h | LAS
    SEQ 24443: d12-14 (3d) | TPAY 15.0h | Block 13.2h | MIA
    SEQ 24584: d15-17 (3d) | TPAY 15.0h | Block 13.4h | LAS
    SEQ  5540: d19-21 (3d) | TPAY 15.0h | Block 14.9h | MIA
    7-day block warnings (>25h):
      d1-7: 28.9h
      d2-8: 28.7h
      d3-9: 28.5h
      d4-10: 28.2h
      d5-11: 28.2h
      d6-12: 27.8h
      d7-13: 27.4h
      d8-14: 27.0h
      d9-15: 26.9h
      d10-16: 26.8h
      d11-17: 26.6h
      d12-18: 26.6h
      d13-19: 27.2h
      d14-20: 27.8h
      d15-21: 28.4h

  Layer 6 sequences:
    SEQ 23854: d 1- 2 (2d) | TPAY 10.0h | Block 8.6h | turn
    SEQ 24079: d 3- 4 (2d) | TPAY 10.0h | Block 8.6h | turn
    SEQ 24151: d 5- 6 (2d) | TPAY 10.0h | Block 9.2h | turn
    SEQ 24312: d 8- 9 (2d) | TPAY 10.0h | Block 8.4h | turn
    SEQ  5320: d10-11 (2d) | TPAY 10.0h | Block 9.9h | turn
    SEQ 24591: d15-16 (2d) | TPAY 10.0h | Block 9.8h | turn
    SEQ 24698: d18-19 (2d) | TPAY 10.0h | Block 9.7h | turn
    SEQ 24871: d23-24 (2d) | TPAY 10.0h | Block 9.5h | turn
    SEQ 24457: d12-13 (2d) | TPAY 10.0h | Block 8.5h | turn
    7-day block warnings (>25h):
      d1-7: 26.4h
      d2-8: 26.3h
      d3-9: 26.2h
      d4-10: 26.8h
      d5-11: 27.5h
      d6-12: 27.1h
      d7-13: 26.8h
      d8-14: 26.8h
      d9-15: 27.5h
      d10-16: 28.2h

  Layer 7 sequences:
    SEQ 24066: d 3- 4 (2d) | TPAY 10.0h | Block 9.5h | turn
    SEQ 24191: d 5- 6 (2d) | TPAY 10.0h | Block 9.8h | turn
    SEQ 24360: d 9-10 (2d) | TPAY 10.0h | Block 7.7h | turn
    SEQ 24415: d11-12 (2d) | TPAY 10.0h | Block 6.5h | turn
    SEQ 23837: d15-16 (2d) | TPAY 10.0h | Block 6.5h | turn
    SEQ 24659: d17-18 (2d) | TPAY 10.0h | Block 9.4h | turn
    SEQ 23968: d 1- 2 (2d) | TPAY 10.0h | Block 6.1h | turn
    SEQ 24713: d19-20 (2d) | TPAY 10.0h | Block 8.4h | turn
    SEQ 24871: d23-24 (2d) | TPAY 10.0h | Block 9.5h | turn
    7-day block warnings (>25h):
      d1-7: 25.4h

  STOPPING: Legality failures detected. Fix before proceeding.
==============================================================================
  PART 2: SCHEDULE SHAPE
==============================================================================

  Layer 1: Dream Schedule — Compact + Quality
  Credit: 90.0h | Span: 20d (d1-d20) | Off: 10d | Blocks: 3
  Block Rating: FAIR | Off Rating: FAIR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7    8▓▓  9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14   15▓▓ 16▓▓ 17▓▓ 18▓▓
     19▓▓ 20▓▓ 21   22   23   24   25  
     26   27   28   29   30  

    SEQ-23968  d 1- 2  (2d, layovers: turn)  credit: 10.0h
    SEQ-24062  d 3- 4  (2d, layovers: turn)  credit: 10.0h
    SEQ-24128  d 5- 6  (2d, layovers: turn)  credit: 10.0h
    SEQ-24294  d 8- 9  (2d, layovers: turn)  credit: 10.0h
    SEQ-24380  d10-11  (2d, layovers: turn)  credit: 10.0h
    SEQ-24457  d12-13  (2d, layovers: turn)  credit: 10.0h
    SEQ-24576  d15-16  (2d, layovers: turn)  credit: 10.0h
    SEQ-23774  d17-18  (2d, layovers: turn)  credit: 10.0h
    SEQ-24713  d19-20  (2d, layovers: turn)  credit: 10.0h

  Layer 2: Alternative Schedule — Back Half
  Credit: 89.3h | Span: 26d (d2-d27) | Off: 5d | Blocks: 4
  Block Rating: POOR | Off Rating: POOR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1    2▓▓  3▓▓  4▓▓
      5▓▓  6    7    8    9▓▓ 10▓▓ 11▓▓
     12▓▓ 13   14   15   16   17▓▓ 18▓▓
     19▓▓ 20   21   22   23   24   25▓▓
     26▓▓ 27▓▓ 28   29   30  

    SEQ-  663  d 9-12  (4d, layovers: NRT 24h, LAS 19h)  credit: 29.6h
    SEQ-  678  d 2- 5  (4d, layovers: NRT 23h, LAS 20h)  credit: 29.2h
    SEQ-24928  d25-27  (3d, layovers: MIA 21h)  credit: 15.5h
    SEQ-24643  d17-19  (3d, layovers: PHX 20h)  credit: 15.0h

  Layer 3: Maximum Pay
  Credit: 90.0h | Span: 20d (d4-d23) | Off: 7d | Blocks: 3
  Block Rating: FAIR | Off Rating: POOR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1    2    3    4▓▓
      5▓▓  6▓▓  7▓▓  8▓▓  9▓▓ 10   11▓▓
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17   18▓▓
     19▓▓ 20▓▓ 21▓▓ 22▓▓ 23▓▓ 24   25  
     26   27   28   29   30  

    SEQ-24096  d 4- 6  (3d, layovers: DEN 17h)  credit: 15.0h
    SEQ-24257  d 7- 9  (3d, layovers: PDX 17h)  credit: 15.0h
    SEQ-24420  d11-13  (3d, layovers: PHX 18h, MCO 14h)  credit: 15.0h
    SEQ- 5494  d14-16  (3d, layovers: MIA 12h)  credit: 15.0h
    SEQ-24673  d18-20  (3d, layovers: PDX 15h)  credit: 15.0h
    SEQ-24800  d21-23  (3d, layovers: PDX 15h)  credit: 15.0h

  Layer 4: All 4-Day Trips — Fewer Commutes
  Credit: 90.0h | Span: 21d (d5-d25) | Off: 5d | Blocks: 4
  Block Rating: POOR | Off Rating: POOR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1    2    3    4  
      5▓▓  6▓▓  7▓▓  8▓▓  9▓▓ 10▓▓ 11  
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17▓▓ 18  
     19▓▓ 20▓▓ 21▓▓ 22   23▓▓ 24▓▓ 25▓▓
     26   27   28   29   30  

    SEQ-24164  d 5- 7  (3d, layovers: SAN 13h)  credit: 15.0h
    SEQ-23812  d 8-10  (3d, layovers: SFO 15h)  credit: 15.0h
    SEQ-24463  d12-14  (3d, layovers: PDX 15h)  credit: 15.0h
    SEQ-24559  d15-17  (3d, layovers: MIA 18h)  credit: 15.0h
    SEQ-24707  d19-21  (3d, layovers: MIA 20h)  credit: 15.0h
    SEQ- 5305  d23-25  (3d, layovers: MIA 12h)  credit: 15.0h

  Layer 5: Best Layovers — Quality Destinations
  Credit: 90.0h | Span: 21d (d1-d21) | Off: 9d | Blocks: 4
  Block Rating: POOR | Off Rating: FAIR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4  
      5▓▓  6▓▓  7▓▓  8▓▓  9▓▓ 10▓▓ 11  
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17▓▓ 18  
     19▓▓ 20▓▓ 21▓▓ 22   23   24   25  
     26   27   28   29   30  

    SEQ-23981  d 1- 3  (3d, layovers: PHX 14h)  credit: 15.0h
    SEQ-24146  d 5- 7  (3d, layovers: SFO 15h)  credit: 15.0h
    SEQ-24303  d 8-10  (3d, layovers: LAS 15h)  credit: 15.0h
    SEQ-24443  d12-14  (3d, layovers: MIA 18h)  credit: 15.0h
    SEQ-24584  d15-17  (3d, layovers: LAS 12h)  credit: 15.0h
    SEQ- 5540  d19-21  (3d, layovers: MIA 13h)  credit: 15.0h

  Layer 6: Flexible Alternative
  Credit: 90.0h | Span: 24d (d1-d24) | Off: 6d | Blocks: 5
  Block Rating: POOR | Off Rating: POOR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7    8▓▓  9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14   15▓▓ 16▓▓ 17   18▓▓
     19▓▓ 20   21   22   23▓▓ 24▓▓ 25  
     26   27   28   29   30  

    SEQ-23854  d 1- 2  (2d, layovers: turn)  credit: 10.0h
    SEQ-24079  d 3- 4  (2d, layovers: turn)  credit: 10.0h
    SEQ-24151  d 5- 6  (2d, layovers: turn)  credit: 10.0h
    SEQ-24312  d 8- 9  (2d, layovers: turn)  credit: 10.0h
    SEQ- 5320  d10-11  (2d, layovers: turn)  credit: 10.0h
    SEQ-24591  d15-16  (2d, layovers: turn)  credit: 10.0h
    SEQ-24698  d18-19  (2d, layovers: turn)  credit: 10.0h
    SEQ-24871  d23-24  (2d, layovers: turn)  credit: 10.0h
    SEQ-24457  d12-13  (2d, layovers: turn)  credit: 10.0h

  Layer 7: Safety Net — Maximum Flexibility
  Credit: 90.0h | Span: 24d (d1-d24) | Off: 6d | Blocks: 4
  Block Rating: POOR | Off Rating: POOR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7    8    9▓▓ 10▓▓ 11▓▓
     12▓▓ 13   14   15▓▓ 16▓▓ 17▓▓ 18▓▓
     19▓▓ 20▓▓ 21   22   23▓▓ 24▓▓ 25  
     26   27   28   29   30  

    SEQ-24066  d 3- 4  (2d, layovers: turn)  credit: 10.0h
    SEQ-24191  d 5- 6  (2d, layovers: turn)  credit: 10.0h
    SEQ-24360  d 9-10  (2d, layovers: turn)  credit: 10.0h
    SEQ-24415  d11-12  (2d, layovers: turn)  credit: 10.0h
    SEQ-23837  d15-16  (2d, layovers: turn)  credit: 10.0h
    SEQ-24659  d17-18  (2d, layovers: turn)  credit: 10.0h
    SEQ-23968  d 1- 2  (2d, layovers: turn)  credit: 10.0h
    SEQ-24713  d19-20  (2d, layovers: turn)  credit: 10.0h
    SEQ-24871  d23-24  (2d, layovers: turn)  credit: 10.0h
==============================================================================
  PART 3: COMMUTABILITY
==============================================================================

  COMMUTABILITY — Layer 1
    Block 1 (d1-6, 6d):
      First report: 13:31 -> GREAT
      Last release: 06:26 -> GREAT
      Buffer before: 0d | Buffer after: 24d
      Block score: 85/100
    Block 2 (d8-13, 6d):
      First report: 09:24 -> GOOD
      Last release: 15:55 -> GREAT
      Buffer before: 7d | Buffer after: 17d
      Block score: 93/100
    Block 3 (d15-20, 6d):
      First report: 12:15 -> GREAT
      Last release: 09:03 -> GREAT
      Buffer before: 14d | Buffer after: 10d
      Block score: 100/100
    Total commute events: 6
    Commutability score: 92/100

  COMMUTABILITY — Layer 2
    Block 1 (d2-5, 4d):
      First report: 14:26 -> GREAT
      Last release: 13:58 -> GREAT
      Buffer before: 1d | Buffer after: 25d
      Block score: 92/100
    Block 2 (d9-12, 4d):
      First report: 13:50 -> GREAT
      Last release: 13:58 -> GREAT
      Buffer before: 8d | Buffer after: 18d
      Block score: 100/100
    Block 3 (d17-19, 3d):
      First report: 11:19 -> GOOD
      Last release: 11:15 -> GREAT
      Buffer before: 16d | Buffer after: 11d
      Block score: 93/100
    Block 4 (d25-27, 3d):
      First report: 06:05 -> MARGINAL
      Last release: 12:25 -> GREAT
      Buffer before: 24d | Buffer after: 3d
      Block score: 82/100
    Total commute events: 8
    Commutability score: 91/100

  COMMUTABILITY — Layer 3
    Block 1 (d4-9, 6d):
      First report: 08:50 -> MARGINAL
      Last release: 12:30 -> GREAT
      Buffer before: 3d | Buffer after: 21d
      Block score: 82/100
    Block 2 (d11-16, 6d):
      First report: 12:25 -> GREAT
      Last release: 12:26 -> GREAT
      Buffer before: 10d | Buffer after: 14d
      Block score: 100/100
    Block 3 (d18-23, 6d):
      First report: 09:19 -> GOOD
      Last release: 12:30 -> GREAT
      Buffer before: 17d | Buffer after: 7d
      Block score: 93/100
    Total commute events: 6
    Commutability score: 91/100

  COMMUTABILITY — Layer 4
    Block 1 (d5-10, 6d):
      First report: 14:26 -> GREAT
      Last release: 12:40 -> GREAT
      Buffer before: 4d | Buffer after: 20d
      Block score: 100/100
    Block 2 (d12-17, 6d):
      First report: 14:00 -> GREAT
      Last release: 09:20 -> GREAT
      Buffer before: 11d | Buffer after: 13d
      Block score: 100/100
    Block 3 (d19-21, 3d):
      First report: 06:05 -> MARGINAL
      Last release: 09:20 -> GREAT
      Buffer before: 18d | Buffer after: 9d
      Block score: 82/100
    Block 4 (d23-25, 3d):
      First report: 11:07 -> GOOD
      Last release: 12:26 -> GREAT
      Buffer before: 22d | Buffer after: 5d
      Block score: 93/100
    Total commute events: 8
    Commutability score: 93/100

  COMMUTABILITY — Layer 5
    Block 1 (d1-3, 3d):
      First report: 17:22 -> GREAT
      Last release: 16:20 -> GOOD
      Buffer before: 0d | Buffer after: 27d
      Block score: 78/100
    Block 2 (d5-10, 6d):
      First report: 09:11 -> GOOD
      Last release: 16:58 -> GOOD
      Buffer before: 4d | Buffer after: 20d
      Block score: 86/100
    Block 3 (d12-17, 6d):
      First report: 07:10 -> MARGINAL
      Last release: 13:58 -> GREAT
      Buffer before: 11d | Buffer after: 13d
      Block score: 82/100
    Block 4 (d19-21, 3d):
      First report: 11:58 -> GOOD
      Last release: 11:21 -> GREAT
      Buffer before: 18d | Buffer after: 9d
      Block score: 93/100
    Total commute events: 8
    Commutability score: 84/100

  COMMUTABILITY — Layer 6
    Block 1 (d1-6, 6d):
      First report: 20:10 -> GREAT
      Last release: 12:40 -> GREAT
      Buffer before: 0d | Buffer after: 24d
      Block score: 85/100
    Block 2 (d8-13, 6d):
      First report: 16:59 -> GREAT
      Last release: 15:55 -> GREAT
      Buffer before: 7d | Buffer after: 17d
      Block score: 100/100
    Block 3 (d15-16, 2d):
      First report: 20:00 -> GREAT
      Last release: 00:38 -> GREAT
      Buffer before: 14d | Buffer after: 14d
      Block score: 100/100
    Block 4 (d18-19, 2d):
      First report: 18:30 -> GREAT
      Last release: 00:45 -> GREAT
      Buffer before: 17d | Buffer after: 11d
      Block score: 100/100
    Block 5 (d23-24, 2d):
      First report: 10:56 -> GOOD
      Last release: 13:58 -> GREAT
      Buffer before: 22d | Buffer after: 6d
      Block score: 93/100
    Total commute events: 10
    Commutability score: 95/100

  COMMUTABILITY — Layer 7
    Block 1 (d1-6, 6d):
      First report: 13:31 -> GREAT
      Last release: 00:38 -> GREAT
      Buffer before: 0d | Buffer after: 24d
      Block score: 85/100
    Block 2 (d9-12, 4d):
      First report: 18:35 -> GREAT
      Last release: 09:16 -> GREAT
      Buffer before: 8d | Buffer after: 18d
      Block score: 100/100
    Block 3 (d15-20, 6d):
      First report: 18:37 -> GREAT
      Last release: 09:03 -> GREAT
      Buffer before: 14d | Buffer after: 10d
      Block score: 100/100
    Block 4 (d23-24, 2d):
      First report: 10:56 -> GOOD
      Last release: 13:58 -> GREAT
      Buffer before: 22d | Buffer after: 6d
      Block score: 93/100
    Total commute events: 8
    Commutability score: 94/100
==============================================================================
  PART 4: TRIP QUALITY
==============================================================================

  TRIP QUALITY — Layer 1
    Trips: 9 sequences (9x2-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
    No layovers (all turns)
    Avg legs/duty-day: 1.3 | Heavy days (4+ legs): 0
    Deadhead: 0/24 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 65/100

  TRIP QUALITY — Layer 2
    Trips: 4 sequences (2x3-day, 2x4-day)
    Credit efficiency: 6.38 hrs/day (pool avg: 5.60) -> ABOVE AVG
      NRT (100/100): 24.2h
      LAS (75/100): 18.8h
      NRT (100/100): 23.2h
      LAS (75/100): 20.1h
      MIA (82/100): 20.8h
      PHX (72/100): 19.9h
    Avg layover: 21.2h | Min: 19h (LAS) | Max: 24h (NRT)
    Avg city tier: 84/100
    Avg legs/duty-day: 1.1 | Heavy days (4+ legs): 0
    Deadhead: 4/16 legs (25%) [WARNING >15%]
    Red-eye/ODAN: none
    Quality Score: 75/100

  TRIP QUALITY — Layer 3
    Trips: 6 sequences (6x3-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
      DEN (83/100): 16.8h
      PDX (82/100): 17.0h
      PHX (72/100): 17.6h
      MCO (70/100): 13.8h [SHORT]
      MIA (82/100): 12.1h [SHORT]
      PDX (82/100): 15.4h
      PDX (82/100): 15.4h
    Avg layover: 15.4h | Min: 12h (MIA) | Max: 18h (PHX)
    Avg city tier: 79/100
    Avg legs/duty-day: 1.5 | Heavy days (4+ legs): 0
    Deadhead: 0/27 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 71/100

  TRIP QUALITY — Layer 4
    Trips: 6 sequences (6x3-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
      SAN (88/100): 13.1h [SHORT]
      SFO (88/100): 15.0h
      PDX (82/100): 15.4h
      MIA (82/100): 18.4h
      MIA (82/100): 20.3h
      MIA (82/100): 12.3h [SHORT]
    Avg layover: 15.7h | Min: 12h (MIA) | Max: 20h (MIA)
    Avg city tier: 84/100
    Avg legs/duty-day: 1.3 | Heavy days (4+ legs): 0
    Deadhead: 0/24 legs (0%)
    Red-eye/ODAN: none
    WARNING: 6 trips shorter than min_pairing_days=4
    Quality Score: 74/100

  TRIP QUALITY — Layer 5
    Trips: 6 sequences (6x3-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
      PHX (72/100): 13.7h [SHORT]
      SFO (88/100): 15.0h
      LAS (75/100): 15.4h
      MIA (82/100): 18.4h
      LAS (75/100): 12.4h [SHORT]
      MIA (82/100): 13.2h [SHORT]
    Avg layover: 14.7h | Min: 12h (LAS) | Max: 18h (MIA)
    Avg city tier: 79/100
    Avg legs/duty-day: 1.4 | Heavy days (4+ legs): 0
    Deadhead: 0/26 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 72/100

  TRIP QUALITY — Layer 6
    Trips: 9 sequences (9x2-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
    No layovers (all turns)
    Avg legs/duty-day: 1.6 | Heavy days (4+ legs): 0
    Deadhead: 0/28 legs (0%)
    Red-eye: 2 | ODAN: 0
    WARNING: 9 trips shorter than min_pairing_days=3
    Quality Score: 55/100

  TRIP QUALITY — Layer 7
    Trips: 9 sequences (9x2-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
    No layovers (all turns)
    Avg legs/duty-day: 1.3 | Heavy days (4+ legs): 0
    Deadhead: 0/24 legs (0%)
    Red-eye: 1 | ODAN: 0
    Quality Score: 61/100
==============================================================================
  PART 5: CROSS-LAYER COMPARISON
==============================================================================

  Jaccard Similarity Matrix:
         L1   L2   L3   L4   L5   L6   L7
  L1    -  0.00  0.00  0.00  0.00  0.06  0.12 
  L2 0.00     -  0.00  0.00  0.00  0.00  0.00 
  L3 0.00  0.00     -  0.00  0.00  0.00  0.00 
  L4 0.00  0.00  0.00     -  0.00  0.00  0.00 
  L5 0.00  0.00  0.00  0.00     -  0.00  0.00 
  L6 0.06  0.00  0.00  0.00  0.00     -  0.06 
  L7 0.12  0.00  0.00  0.00  0.00  0.06     - 

  All layer pairs have Jaccard <= 0.5 (good diversity)

  Credit Spread:
    L1: 90.0h
    L2: 89.3h
    L3: 90.0h
    L4: 90.0h
    L5: 90.0h
    L6: 90.0h
    L7: 90.0h
    Range: 0.7h (NARROW: <8h spread)

  Strategy Fulfillment:
    L1 [MATCH] Compact front-loaded, 2+ day trips
         OK: all trips >= 2-day | WARN: 3 blocks (expected <=2) | OK: front-loaded
    L2 [MATCH] Compact back-loaded, 2+ day trips
         OK: all trips >= 2-day | WARN: 4 blocks (expected <=2) | WARN: window mismatch (front=8, back=6)
    L3 [MATCH] Max credit, 3+ day trips
         OK: all trips >= 3-day | WARN: 3 blocks (expected <=2) | OK: highest/near-highest credit
    L4 [MISMATCH] All 4-day trips, fewer commutes
         FAIL: 6 trips < 4-day | WARN: 4 blocks (expected <=2) | INFO: mix {3: 6} (target: all 4-day)
    L5 [MATCH] Best layover cities, 3+ day trips
         OK: all trips >= 3-day | WARN: 4 blocks (expected <=2) | INFO: city tier 79 (L1:50, L3:79)
    L6 [MISMATCH] Flexible fallback, 2+ day trips
         FAIL: 9 trips < 3-day
    L7 [MATCH] Safety net, 2+ day trips
         OK: all trips >= 2-day

  Safety Net Adequacy (L7):
    Total sequences with dates: 1364
    L7 selected: 9 sequences
    L6 selected: 9 sequences
    L7 produces legal line: YES
==============================================================================
  PART 6: FINAL SCORECARD
==============================================================================

  Layer |                  Strategy |  Credit | Span |  Off | Blk | Gap |  Comm |  Qual | Legal | Strat
  ------+---------------------------+---------+------+------+-----+-----+-------+-------+-------+------
  L  1 | Dream Schedule — Compact  |  90.0h |  20d |  10d |   3 |   2 |  92/100 |  65/100 |     Y |     Y
  L  2 | Alternative Schedule — Ba |  89.3h |  26d |   5d |   4 |  12 |  91/100 |  75/100 |     Y |     Y
  L  3 |               Maximum Pay |  90.0h |  20d |   7d |   3 |   2 |  91/100 |  71/100 |     Y |     Y
  L  4 | All 4-Day Trips — Fewer C |  90.0h |  21d |   5d |   4 |   3 |  93/100 |  74/100 |     Y |     N
  L  5 | Best Layovers — Quality D |  90.0h |  21d |   9d |   4 |   3 |  84/100 |  72/100 |     N |     Y
  L  6 |      Flexible Alternative |  90.0h |  24d |   6d |   5 |   6 |  95/100 |  55/100 |     Y |     N
  L  7 | Safety Net — Maximum Flex |  90.0h |  24d |   6d |   4 |   6 |  94/100 |  61/100 |     Y |     Y

------------------------------------------------------------------------------

  1. ARE ALL LAYERS LEGAL?
     NO. The following layers have legality failures:
       L5: Credit 90.0h > max 88h

  2. WOULD A DOMESTIC FA WANTING COMPACT 3-4 DAY TRIPS SUBMIT THIS BID?

     L1: 90.0h | 9x2d | scattered (3 blocks), wide 20d span | cities: turns only
         Quality: 65/100 | Commutability: 92/100
     L2: 89.3h | 2x3d, 2x4d | scattered (4 blocks), wide 26d span | cities: LAS, MIA, NRT, PHX
         Quality: 75/100 | Commutability: 91/100
     L3: 90.0h | 6x3d | scattered (3 blocks), wide 20d span | cities: DEN, MCO, MIA, PDX, PHX
         Quality: 71/100 | Commutability: 91/100

     CONCERNS:
       - Narrow credit spread: 0.7h

     VERDICT: NO

  3. DOES THE 7-LAYER SET PROVIDE ADEQUATE FALLBACK COVERAGE?

     Layer progression:
       L1 (Dream Schedule — Compact + Quality): 90.0h, 20d span, 3 block(s)
       L2 (Alternative Schedule — Back Half): 89.3h, 26d span, 4 block(s)
       L3 (Maximum Pay): 90.0h, 20d span, 3 block(s)
       L4 (All 4-Day Trips — Fewer Commutes): 90.0h, 21d span, 4 block(s)
       L5 (Best Layovers — Quality Destinations): 90.0h, 21d span, 4 block(s)
       L6 (Flexible Alternative): 90.0h, 24d span, 5 block(s)
       L7 (Safety Net — Maximum Flexibility): 90.0h, 24d span, 4 block(s)

     WARNING: Layers [6] have 5+ work blocks (scattered, dreadful)
     L7 (safety net) legal: YES
     L7 prevents Layer None: YES

```
