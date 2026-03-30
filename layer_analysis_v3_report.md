```
==============================================================================
  PBS LAYER OUTPUT ANALYZER v3 — Post-Fix Verification
  Bid Period: Test Bid 2 (ORD, January 2026)
  Analysis: 2026-03-29 19:30
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
  Saved 40 entries to fresh_entries_v3.json
  Layers populated: [1, 2, 3, 4, 5, 6, 7]
    L1: 3 sequences
    L2: 4 sequences
    L3: 6 sequences
    L4: 4 sequences
    L5: 5 sequences
    L6: 9 sequences
    L7: 9 sequences

==============================================================================
  PART 1: LEGALITY AUDIT
==============================================================================

  Layer |  Dates |   Rest |       Credit | Days Off |  7-Day Blk | Multi-OPS
  ------+--------+--------+--------------+----------+------------+----------
  L  1 |   PASS |   PASS |    75.5 PASS |  20 PASS |  38.3 FAIL |      PASS
  L  2 |   PASS |   PASS |    79.3 PASS |  20 PASS |  38.6 FAIL |      PASS
  L  3 |   PASS |   PASS |    90.0 PASS |  12 PASS |  34.1 FAIL |      PASS
  L  4 |   PASS |   PASS |    89.7 PASS |  14 PASS |  34.8 FAIL |      PASS
  L  5 |   PASS |   PASS |    80.0 PASS |  15 PASS |  34.0 FAIL |      PASS
  L  6 |   PASS |   PASS |    90.0 PASS |  12 PASS |  33.2 FAIL |      PASS
  L  7 |   PASS |   PASS |    90.0 PASS |  12 PASS |  31.0 FAIL |      PASS

  LEGALITY FAILURES DETECTED:
    L1: 7-day block 38.3h > 30h at d5-11
    L2: 7-day block 38.6h > 30h at d11-17
    L3: 7-day block 34.1h > 30h at d4-10
    L4: 7-day block 34.8h > 30h at d12-18
    L5: 7-day block 34.0h > 30h at d11-17
    L6: 7-day block 33.2h > 30h at d11-17
    L7: 7-day block 31.0h > 30h at d11-17

  Layer 1 sequences:
    SEQ   672: d 5- 6 (2d) | TPAY 16.6h | Block 16.6h | turn
    SEQ   663: d 8-11 (4d) | TPAY 29.6h | Block 21.8h | NRT,LAS
    SEQ   664: d 1- 4 (4d) | TPAY 29.4h | Block 21.5h | NRT,LAS
    7-day block warnings (>25h):
      d1-7: 38.1h
      d2-8: 38.1h
      d3-9: 38.2h
      d4-10: 38.3h
      d5-11: 38.3h
      d6-12: 30.0h

  Layer 2 sequences:
    SEQ   675: d13-14 (2d) | TPAY 16.5h | Block 16.5h | turn
    SEQ   671: d16-17 (2d) | TPAY 16.7h | Block 16.7h | turn
    SEQ   674: d 5- 6 (2d) | TPAY 16.6h | Block 16.6h | turn
    SEQ   663: d 8-11 (4d) | TPAY 29.6h | Block 21.8h | NRT,LAS
    7-day block warnings (>25h):
      d3-9: 27.5h
      d4-10: 32.9h
      d5-11: 38.3h
      d6-12: 30.0h
      d7-13: 30.0h
      d8-14: 38.2h
      d9-15: 32.8h
      d10-16: 35.7h
      d11-17: 38.6h
      d12-18: 33.2h
      d13-19: 33.2h

  Layer 3 sequences:
    SEQ 23983: d 1- 3 (3d) | TPAY 15.0h | Block 12.4h | SLC
    SEQ 24124: d 4- 6 (3d) | TPAY 15.0h | Block 14.4h | LAX
    SEQ 24257: d 7- 9 (3d) | TPAY 15.0h | Block 14.9h | PDX
    SEQ 23812: d10-12 (3d) | TPAY 15.0h | Block 14.4h | SFO
    SEQ 24497: d13-15 (3d) | TPAY 15.0h | Block 14.4h | LAX
    SEQ 24643: d17-19 (3d) | TPAY 15.0h | Block 12.0h | PHX
    7-day block warnings (>25h):
      d1-7: 31.8h
      d2-8: 32.6h
      d3-9: 33.5h
      d4-10: 34.1h
      d5-11: 34.1h
      d6-12: 34.1h
      d7-13: 34.1h
      d8-14: 33.9h
      d9-15: 33.8h
      d10-16: 28.8h
      d11-17: 28.0h
      d12-18: 27.2h
      d13-19: 26.4h

  Layer 4 sequences:
    SEQ   678: d 2- 5 (4d) | TPAY 29.2h | Block 21.5h | NRT,LAS
    SEQ 24298: d 8-11 (4d) | TPAY 20.0h | Block 19.0h | RDU,MIA
    SEQ 24472: d12-15 (4d) | TPAY 20.5h | Block 20.4h | SLC,PDX
    SEQ  5325: d16-19 (4d) | TPAY 20.0h | Block 19.2h | CLT,SJO
    7-day block warnings (>25h):
      d2-8: 26.3h
      d3-9: 25.6h
      d4-10: 25.0h
      d7-13: 29.2h
      d8-14: 34.3h
      d9-15: 34.6h
      d10-16: 34.7h
      d11-17: 34.7h
      d12-18: 34.8h
      d13-19: 34.5h
      d14-20: 29.4h

  Layer 5 sequences:
    SEQ 24165: d 5- 7 (3d) | TPAY 19.9h | Block 15.1h | SFO
    SEQ 24358: d 9-11 (3d) | TPAY 15.0h | Block 14.3h | LAX
    SEQ 24461: d12-14 (3d) | TPAY 15.0h | Block 14.8h | DEN
    SEQ 24579: d15-17 (3d) | TPAY 15.0h | Block 14.4h | BOS
    SEQ 24701: d18-20 (3d) | TPAY 15.1h | Block 13.9h | MIA
    7-day block warnings (>25h):
      d5-11: 29.4h
      d6-12: 29.3h
      d7-13: 29.2h
      d8-14: 29.1h
      d9-15: 33.9h
      d10-16: 33.9h
      d11-17: 34.0h
      d12-18: 33.9h
      d13-19: 33.5h
      d14-20: 33.2h
      d15-21: 28.3h

  Layer 6 sequences:
    SEQ 23839: d15-16 (2d) | TPAY 10.0h | Block 9.4h | turn
    SEQ 23991: d 1- 2 (2d) | TPAY 10.0h | Block 7.6h | turn
    SEQ 23854: d 3- 4 (2d) | TPAY 10.0h | Block 8.6h | turn
    SEQ 24131: d 5- 6 (2d) | TPAY 10.0h | Block 6.5h | turn
    SEQ 24276: d 7- 8 (2d) | TPAY 10.0h | Block 8.8h | turn
    SEQ 23837: d 9-10 (2d) | TPAY 10.0h | Block 6.5h | turn
    SEQ 24433: d11-12 (2d) | TPAY 10.0h | Block 9.4h | turn
    SEQ 24513: d13-14 (2d) | TPAY 10.0h | Block 9.8h | turn
    SEQ 24658: d17-18 (2d) | TPAY 10.0h | Block 8.9h | turn
    7-day block warnings (>25h):
      d1-7: 27.1h
      d2-8: 27.7h
      d3-9: 27.1h
      d4-10: 26.1h
      d5-11: 26.5h
      d6-12: 28.0h
      d7-13: 29.7h
      d8-14: 30.2h
      d9-15: 30.5h
      d10-16: 32.0h
      d11-17: 33.2h
      d12-18: 32.9h
      d13-19: 28.2h

  Layer 7 sequences:
    SEQ 23968: d 1- 2 (2d) | TPAY 10.0h | Block 6.1h | turn
    SEQ 24063: d 3- 4 (2d) | TPAY 10.0h | Block 9.6h | turn
    SEQ 24182: d 5- 6 (2d) | TPAY 10.0h | Block 6.3h | turn
    SEQ 24312: d 8- 9 (2d) | TPAY 10.0h | Block 8.4h | turn
    SEQ 24398: d10-11 (2d) | TPAY 10.0h | Block 9.4h | turn
    SEQ 24471: d12-13 (2d) | TPAY 10.0h | Block 8.4h | turn
    SEQ 23828: d14-15 (2d) | TPAY 10.0h | Block 8.4h | turn
    SEQ 23849: d18-19 (2d) | TPAY 10.0h | Block 7.9h | turn
    SEQ 23839: d16-17 (2d) | TPAY 10.0h | Block 9.4h | turn
    7-day block warnings (>25h):
      d6-12: 25.2h
      d7-13: 26.2h
      d8-14: 30.4h
      d9-15: 30.4h
      d10-16: 30.9h
      d11-17: 31.0h
      d12-18: 30.2h
      d13-19: 30.0h
      d14-20: 25.8h

  STOPPING: Legality failures detected. Fix before proceeding.
==============================================================================
  PART 2: SCHEDULE SHAPE
==============================================================================

  Layer 1: Dream Schedule — Compact + Quality
  Credit: 75.5h | Span: 11d (d1-d11) | Off: 19d | Blocks: 2
  Block Rating: GOOD | Off Rating: EXCELLENT

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7    8▓▓  9▓▓ 10▓▓ 11▓▓
     12   13   14   15   16   17   18  
     19   20   21   22   23   24   25  
     26   27   28   29   30  

    SEQ-  672  d 5- 6  (2d, layovers: turn)  credit: 16.6h
    SEQ-  663  d 8-11  (4d, layovers: NRT 24h, LAS 19h)  credit: 29.6h
    SEQ-  664  d 1- 4  (4d, layovers: NRT 23h, LAS 18h)  credit: 29.4h

  Layer 2: Flip Window — Back Half
  Credit: 79.3h | Span: 13d (d5-d17) | Off: 13d | Blocks: 4
  Block Rating: POOR | Off Rating: GOOD

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1    2    3    4  
      5▓▓  6▓▓  7    8▓▓  9▓▓ 10▓▓ 11▓▓
     12   13▓▓ 14▓▓ 15   16▓▓ 17▓▓ 18  
     19   20   21   22   23   24   25  
     26   27   28   29   30  

    SEQ-  675  d13-14  (2d, layovers: turn)  credit: 16.5h
    SEQ-  671  d16-17  (2d, layovers: turn)  credit: 16.7h
    SEQ-  674  d 5- 6  (2d, layovers: turn)  credit: 16.6h
    SEQ-  663  d 8-11  (4d, layovers: NRT 24h, LAS 19h)  credit: 29.6h

  Layer 3: Maximum Pay
  Credit: 90.0h | Span: 19d (d1-d19) | Off: 11d | Blocks: 2
  Block Rating: GOOD | Off Rating: GOOD

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7▓▓  8▓▓  9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16   17▓▓ 18▓▓
     19▓▓ 20   21   22   23   24   25  
     26   27   28   29   30  

    SEQ-23983  d 1- 3  (3d, layovers: SLC 17h)  credit: 15.0h
    SEQ-24124  d 4- 6  (3d, layovers: LAX 14h)  credit: 15.0h
    SEQ-24257  d 7- 9  (3d, layovers: PDX 17h)  credit: 15.0h
    SEQ-23812  d10-12  (3d, layovers: SFO 15h)  credit: 15.0h
    SEQ-24497  d13-15  (3d, layovers: LAX 13h)  credit: 15.0h
    SEQ-24643  d17-19  (3d, layovers: PHX 20h)  credit: 15.0h

  Layer 4: All 4-Day Trips — Fewer Commutes
  Credit: 89.7h | Span: 18d (d2-d19) | Off: 11d | Blocks: 2
  Block Rating: GOOD | Off Rating: GOOD

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1    2▓▓  3▓▓  4▓▓
      5▓▓  6    7    8▓▓  9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17▓▓ 18▓▓
     19▓▓ 20   21   22   23   24   25  
     26   27   28   29   30  

    SEQ-  678  d 2- 5  (4d, layovers: NRT 23h, LAS 20h)  credit: 29.2h
    SEQ-24298  d 8-11  (4d, layovers: RDU 13h, MIA 19h)  credit: 20.0h
    SEQ-24472  d12-15  (4d, layovers: SLC 11h, PDX 15h)  credit: 20.5h
    SEQ- 5325  d16-19  (4d, layovers: CLT 13h, SJO 17h)  credit: 20.0h

  Layer 5: Best Layovers — Quality Destinations
  Credit: 80.0h | Span: 16d (d5-d20) | Off: 10d | Blocks: 2
  Block Rating: GOOD | Off Rating: FAIR

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1    2    3    4  
      5▓▓  6▓▓  7▓▓  8    9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17▓▓ 18▓▓
     19▓▓ 20▓▓ 21   22   23   24   25  
     26   27   28   29   30  

    SEQ-24165  d 5- 7  (3d, layovers: SFO 16h)  credit: 19.9h
    SEQ-24358  d 9-11  (3d, layovers: LAX 17h)  credit: 15.0h
    SEQ-24461  d12-14  (3d, layovers: DEN 19h)  credit: 15.0h
    SEQ-24579  d15-17  (3d, layovers: BOS 14h)  credit: 15.0h
    SEQ-24701  d18-20  (3d, layovers: MIA 22h)  credit: 15.1h

  Layer 6: Flexible Alternative
  Credit: 90.0h | Span: 18d (d1-d18) | Off: 12d | Blocks: 1
  Block Rating: EXCELLENT | Off Rating: GOOD

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7▓▓  8▓▓  9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17▓▓ 18▓▓
     19   20   21   22   23   24   25  
     26   27   28   29   30  

    SEQ-23839  d15-16  (2d, layovers: turn)  credit: 10.0h
    SEQ-23991  d 1- 2  (2d, layovers: turn)  credit: 10.0h
    SEQ-23854  d 3- 4  (2d, layovers: turn)  credit: 10.0h
    SEQ-24131  d 5- 6  (2d, layovers: turn)  credit: 10.0h
    SEQ-24276  d 7- 8  (2d, layovers: turn)  credit: 10.0h
    SEQ-23837  d 9-10  (2d, layovers: turn)  credit: 10.0h
    SEQ-24433  d11-12  (2d, layovers: turn)  credit: 10.0h
    SEQ-24513  d13-14  (2d, layovers: turn)  credit: 10.0h
    SEQ-24658  d17-18  (2d, layovers: turn)  credit: 10.0h

  Layer 7: Safety Net — Maximum Flexibility
  Credit: 90.0h | Span: 19d (d1-d19) | Off: 11d | Blocks: 2
  Block Rating: GOOD | Off Rating: GOOD

    Mon  Tue  Wed  Thu  Fri  Sat  Sun
                     1▓▓  2▓▓  3▓▓  4▓▓
      5▓▓  6▓▓  7    8▓▓  9▓▓ 10▓▓ 11▓▓
     12▓▓ 13▓▓ 14▓▓ 15▓▓ 16▓▓ 17▓▓ 18▓▓
     19▓▓ 20   21   22   23   24   25  
     26   27   28   29   30  

    SEQ-23968  d 1- 2  (2d, layovers: turn)  credit: 10.0h
    SEQ-24063  d 3- 4  (2d, layovers: turn)  credit: 10.0h
    SEQ-24182  d 5- 6  (2d, layovers: turn)  credit: 10.0h
    SEQ-24312  d 8- 9  (2d, layovers: turn)  credit: 10.0h
    SEQ-24398  d10-11  (2d, layovers: turn)  credit: 10.0h
    SEQ-24471  d12-13  (2d, layovers: turn)  credit: 10.0h
    SEQ-23828  d14-15  (2d, layovers: turn)  credit: 10.0h
    SEQ-23849  d18-19  (2d, layovers: turn)  credit: 10.0h
    SEQ-23839  d16-17  (2d, layovers: turn)  credit: 10.0h
==============================================================================
  PART 3: COMMUTABILITY
==============================================================================

  COMMUTABILITY — Layer 1
    Block 1 (d1-6, 6d):
      First report: 14:26 -> GREAT
      Last release: 15:55 -> GREAT
      Buffer before: 0d | Buffer after: 24d
      Block score: 85/100
    Block 2 (d8-11, 4d):
      First report: 13:50 -> GREAT
      Last release: 13:58 -> GREAT
      Buffer before: 7d | Buffer after: 19d
      Block score: 100/100
    Total commute events: 4
    Commutability score: 92/100

  COMMUTABILITY — Layer 2
    Block 1 (d5-6, 2d):
      First report: 19:25 -> GREAT
      Last release: 17:30 -> GOOD
      Buffer before: 4d | Buffer after: 24d
      Block score: 93/100
    Block 2 (d8-11, 4d):
      First report: 13:50 -> GREAT
      Last release: 13:58 -> GREAT
      Buffer before: 7d | Buffer after: 19d
      Block score: 100/100
    Block 3 (d13-14, 2d):
      First report: 19:30 -> GREAT
      Last release: 17:30 -> GOOD
      Buffer before: 12d | Buffer after: 16d
      Block score: 93/100
    Block 4 (d16-17, 2d):
      First report: 17:10 -> GREAT
      Last release: 15:55 -> GREAT
      Buffer before: 15d | Buffer after: 13d
      Block score: 100/100
    Total commute events: 8
    Commutability score: 96/100

  COMMUTABILITY — Layer 3
    Block 1 (d1-15, 15d):
      First report: 18:14 -> GREAT
      Last release: 12:47 -> GREAT
      Buffer before: 0d | Buffer after: 15d
      Block score: 85/100
    Block 2 (d17-19, 3d):
      First report: 11:19 -> GOOD
      Last release: 11:15 -> GREAT
      Buffer before: 16d | Buffer after: 11d
      Block score: 93/100
    Total commute events: 4
    Commutability score: 89/100

  COMMUTABILITY — Layer 4
    Block 1 (d2-5, 4d):
      First report: 14:26 -> GREAT
      Last release: 13:58 -> GREAT
      Buffer before: 1d | Buffer after: 25d
      Block score: 92/100
    Block 2 (d8-19, 12d):
      First report: 11:15 -> GOOD
      Last release: 13:08 -> GREAT
      Buffer before: 7d | Buffer after: 11d
      Block score: 93/100
    Total commute events: 4
    Commutability score: 92/100

  COMMUTABILITY — Layer 5
    Block 1 (d5-7, 3d):
      First report: 15:05 -> GREAT
      Last release: 12:40 -> GREAT
      Buffer before: 4d | Buffer after: 23d
      Block score: 100/100
    Block 2 (d9-20, 12d):
      First report: 17:00 -> GREAT
      Last release: 23:23 -> BAD
      Buffer before: 8d | Buffer after: 10d
      Block score: 72/100
    Total commute events: 4
    Commutability score: 86/100

  COMMUTABILITY — Layer 6
    Block 1 (d1-18, 18d):
      First report: 19:52 -> GREAT
      Last release: 20:30 -> MARGINAL
      Buffer before: 0d | Buffer after: 12d
      Block score: 67/100
    Total commute events: 2
    Commutability score: 67/100

  COMMUTABILITY — Layer 7
    Block 1 (d1-6, 6d):
      First report: 13:31 -> GREAT
      Last release: 19:58 -> MARGINAL
      Buffer before: 0d | Buffer after: 24d
      Block score: 67/100
    Block 2 (d8-19, 12d):
      First report: 16:59 -> GREAT
      Last release: 20:30 -> MARGINAL
      Buffer before: 7d | Buffer after: 11d
      Block score: 82/100
    Total commute events: 4
    Commutability score: 74/100
==============================================================================
  PART 4: TRIP QUALITY
==============================================================================

  TRIP QUALITY — Layer 1
    Trips: 3 sequences (1x2-day, 2x4-day)
    Credit efficiency: 7.55 hrs/day (pool avg: 5.60) -> ABOVE AVG
      NRT (100/100): 24.2h
      LAS (75/100): 18.8h
      NRT (100/100): 23.2h
      LAS (75/100): 18.1h
    Avg layover: 21.1h | Min: 18h (LAS) | Max: 24h (NRT)
    Avg city tier: 88/100
    Avg legs/duty-day: 1.0 | Heavy days (4+ legs): 0
    Deadhead: 4/10 legs (40%) [WARNING >15%]
    Red-eye/ODAN: none
    Quality Score: 82/100

  TRIP QUALITY — Layer 2
    Trips: 4 sequences (3x2-day, 1x4-day)
    Credit efficiency: 7.94 hrs/day (pool avg: 5.60) -> ABOVE AVG
      NRT (100/100): 24.2h
      LAS (75/100): 18.8h
    Avg layover: 21.5h | Min: 19h (LAS) | Max: 24h (NRT)
    Avg city tier: 88/100
    Avg legs/duty-day: 1.0 | Heavy days (4+ legs): 0
    Deadhead: 2/10 legs (20%) [WARNING >15%]
    Red-eye/ODAN: none
    Quality Score: 87/100

  TRIP QUALITY — Layer 3
    Trips: 6 sequences (6x3-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
      SLC (70/100): 17.2h
      LAX (85/100): 14.4h
      PDX (82/100): 17.0h
      SFO (88/100): 15.0h
      LAX (85/100): 13.2h [SHORT]
      PHX (72/100): 19.9h
    Avg layover: 16.1h | Min: 13h (LAX) | Max: 20h (PHX)
    Avg city tier: 80/100
    Avg legs/duty-day: 1.3 | Heavy days (4+ legs): 0
    Deadhead: 0/23 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 73/100

  TRIP QUALITY — Layer 4
    Trips: 4 sequences (4x4-day)
    Credit efficiency: 5.61 hrs/day (pool avg: 5.60) -> ABOVE AVG
      NRT (100/100): 23.2h
      LAS (75/100): 20.1h
      RDU (68/100): 13.4h [SHORT]
      MIA (82/100): 19.4h
      SLC (70/100): 11.2h [SHORT]
      PDX (82/100): 15.4h
      CLT (58/100): 12.5h [SHORT]
      SJO (55/100): 17.0h
    Avg layover: 16.5h | Min: 11h (SLC) | Max: 23h (NRT)
    Avg city tier: 74/100
    Avg legs/duty-day: 1.2 | Heavy days (4+ legs): 0
    Deadhead: 2/19 legs (11%)
    Red-eye/ODAN: none
    Quality Score: 72/100

  TRIP QUALITY — Layer 5
    Trips: 5 sequences (5x3-day)
    Credit efficiency: 5.33 hrs/day (pool avg: 5.60) -> BELOW AVG
      SFO (88/100): 16.1h
      LAX (85/100): 17.0h
      DEN (83/100): 18.5h
      BOS (87/100): 14.0h [SHORT]
      MIA (82/100): 21.7h
    Avg layover: 17.4h | Min: 14h (BOS) | Max: 22h (MIA)
    Avg city tier: 85/100
    Avg legs/duty-day: 1.5 | Heavy days (4+ legs): 0
    Deadhead: 0/22 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 75/100

  TRIP QUALITY — Layer 6
    Trips: 9 sequences (9x2-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
    No layovers (all turns)
    Avg legs/duty-day: 1.3 | Heavy days (4+ legs): 0
    Deadhead: 0/23 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 65/100

  TRIP QUALITY — Layer 7
    Trips: 9 sequences (9x2-day)
    Credit efficiency: 5.00 hrs/day (pool avg: 5.60) -> BELOW AVG
    No layovers (all turns)
    Avg legs/duty-day: 1.3 | Heavy days (4+ legs): 0
    Deadhead: 0/24 legs (0%)
    Red-eye/ODAN: none
    Quality Score: 65/100
==============================================================================
  PART 5: CROSS-LAYER COMPARISON
==============================================================================

  Jaccard Similarity Matrix:
         L1   L2   L3   L4   L5   L6   L7
  L1    -  0.17  0.00  0.00  0.00  0.00  0.00 
  L2 0.17     -  0.00  0.00  0.00  0.00  0.00 
  L3 0.00  0.00     -  0.00  0.00  0.00  0.00 
  L4 0.00  0.00  0.00     -  0.00  0.00  0.00 
  L5 0.00  0.00  0.00  0.00     -  0.00  0.00 
  L6 0.00  0.00  0.00  0.00  0.00     -  0.06 
  L7 0.00  0.00  0.00  0.00  0.00  0.06     - 

  All layer pairs have Jaccard <= 0.5 (good diversity)

  Credit Spread:
    L1: 75.5h
    L2: 79.3h
    L3: 90.0h
    L4: 89.7h
    L5: 80.0h
    L6: 90.0h
    L7: 90.0h
    Range: 14.5h (GOOD: >8h spread)

  Strategy Fulfillment:
    L1 [MATCH] Compact front-loaded, 2+ day trips
         OK: all trips >= 2-day | OK: 2 block(s) | OK: front-loaded
    L2 [MATCH] Compact back-loaded, 2+ day trips
         OK: all trips >= 2-day | WARN: 4 blocks (expected <=2) | WARN: window mismatch (front=8, back=2)
    L3 [MATCH] Max credit, 3+ day trips
         OK: all trips >= 3-day | OK: 2 block(s) | OK: highest/near-highest credit
    L4 [MATCH] All 4-day trips, fewer commutes
         OK: all trips >= 4-day | OK: 2 block(s) | OK: 100% 4-day trips
    L5 [MATCH] Best layover cities, 3+ day trips
         OK: all trips >= 3-day | OK: 2 block(s) | INFO: city tier 85 (L1:88, L3:80)
    L6 [MATCH] Flexible fallback, 2+ day trips
         OK: all trips >= 2-day
    L7 [MATCH] Safety net, 2+ day trips
         OK: all trips >= 2-day

  Safety Net Adequacy (L7):
    Total sequences with dates: 1364
    L7 selected: 9 sequences
    L6 selected: 9 sequences
    L7 produces legal line: NO
==============================================================================
  PART 6: FINAL SCORECARD
==============================================================================

  Layer |                  Strategy |  Credit | Span |  Off | Blk | Gap |  Comm |  Qual | Legal | Strat
  ------+---------------------------+---------+------+------+-----+-----+-------+-------+-------+------
  L  1 | Dream Schedule — Compact  |  75.5h |  11d |  19d |   2 |   1 |  92/100 |  82/100 |     N |     Y
  L  2 |   Flip Window — Back Half |  79.3h |  13d |  13d |   4 |   3 |  96/100 |  87/100 |     N |     Y
  L  3 |               Maximum Pay |  90.0h |  19d |  11d |   2 |   1 |  89/100 |  73/100 |     N |     Y
  L  4 | All 4-Day Trips — Fewer C |  89.7h |  18d |  11d |   2 |   2 |  92/100 |  72/100 |     N |     Y
  L  5 | Best Layovers — Quality D |  80.0h |  16d |  10d |   2 |   1 |  86/100 |  75/100 |     N |     Y
  L  6 |      Flexible Alternative |  90.0h |  18d |  12d |   1 |   0 |  67/100 |  65/100 |     N |     Y
  L  7 | Safety Net — Maximum Flex |  90.0h |  19d |  11d |   2 |   1 |  74/100 |  65/100 |     N |     Y

------------------------------------------------------------------------------

  1. ARE ALL LAYERS LEGAL?
     NO. The following layers have legality failures:
       L1: 7-day block 38.3h > 30h at d5-11
       L2: 7-day block 38.6h > 30h at d11-17
       L3: 7-day block 34.1h > 30h at d4-10
       L4: 7-day block 34.8h > 30h at d12-18
       L5: 7-day block 34.0h > 30h at d11-17
       L6: 7-day block 33.2h > 30h at d11-17
       L7: 7-day block 31.0h > 30h at d11-17

  2. WOULD A DOMESTIC FA WANTING COMPACT 3-4 DAY TRIPS SUBMIT THIS BID?

     L1: 75.5h | 1x2d, 2x4d | compact, 11d span | cities: LAS, NRT
         Quality: 82/100 | Commutability: 92/100
     L2: 79.3h | 3x2d, 1x4d | scattered (4 blocks), 13d span | cities: LAS, NRT
         Quality: 87/100 | Commutability: 96/100
     L3: 90.0h | 6x3d | compact, wide 19d span | cities: LAX, PDX, PHX, SFO, SLC
         Quality: 73/100 | Commutability: 89/100

     GOOD:
       + L1 is compact (11d span, 2 block(s))
       + L1 has 19 days off in a row
       + Credit spread: 14.5h

     VERDICT: NO

  3. DOES THE 7-LAYER SET PROVIDE ADEQUATE FALLBACK COVERAGE?

     Layer progression:
       L1 (Dream Schedule — Compact + Quality): 75.5h, 11d span, 2 block(s)
       L2 (Flip Window — Back Half): 79.3h, 13d span, 4 block(s)
       L3 (Maximum Pay): 90.0h, 19d span, 2 block(s)
       L4 (All 4-Day Trips — Fewer Commutes): 89.7h, 18d span, 2 block(s)
       L5 (Best Layovers — Quality Destinations): 80.0h, 16d span, 2 block(s)
       L6 (Flexible Alternative): 90.0h, 18d span, 1 block(s)
       L7 (Safety Net — Maximum Flexibility): 90.0h, 19d span, 2 block(s)

     No layer has 5+ work blocks — all are flyable.
     L7 (safety net) legal: NO
     L7 prevents Layer None: NO

```
