# Business Rules — COBOL Source Mapping

This document maps every business rule (R01–R20) to its exact location in the original COBOL source. It answers: was this rule actually enforced in the legacy system, and where?

**Source files:**
- `src/cbl/unemplclm.cbl` — orchestrator (batch loop, input parsing, output formatting)
- `src/cbl/getclaim.cbl` — data layer (VSAM KSDS reads, writes, deletes)

---

## Rules Grounded in the COBOL Code (R01–R12)

These 12 rules were reverse-engineered from the COBOL behavior. The code enforces them — the rule numbers were assigned during the AWS modernization project.

---

### R01 — Valid operation codes only (R / I / U / D)

**What it does:** Rejects any command that isn't Read, Insert, Update, or Delete. Triggers an abend on an unrecognized code.

**UNEMPLCLM.cbl — 88-level condition names (lines 40–44):**
```cobol
05 WS-INP-CMD                    PIC X(01).
   88 C-CMD-READ                 VALUE 'R'.
   88 C-CMD-DELETE               VALUE 'D'.
   88 C-CMD-INSERT               VALUE 'I'.
   88 C-CMD-UPDATE               VALUE 'U'.
   88 C-CMD-EOF                  VALUE 'E'.
```

**UNEMPLCLM.cbl — EVALUATE enforces it (lines 856–876):**
```cobol
EVALUATE TRUE
   WHEN C-CMD-READ   PERFORM 2100-ACCEPT-READ-INPUT ...
   WHEN C-CMD-DELETE PERFORM 2200-ACCEPT-DELETE-INPUT ...
   WHEN C-CMD-INSERT OR C-CMD-UPDATE PERFORM 2300-ACCEPT-OTHER-INPUT ...
   WHEN C-CMD-EOF    DISPLAY 'REACH TO END OF FILE'
   WHEN OTHER
      DISPLAY 'WRONG COMMAND SPECIFIED'
      PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
END-EVALUATE.
```

**GETCLAIM.cbl — re-validates at the data layer (lines 60–63, 90–107):**
```cobol
88 C-COMMAND-READ    VALUE 'R'.
88 C-COMMAND-DELETE  VALUE 'D'.
88 C-COMMAND-INSERT  VALUE 'I'.
88 C-COMMAND-UPDATE  VALUE 'U'.

EVALUATE TRUE
   WHEN C-COMMAND-READ   PERFORM 2000-CLAIM-READ ...
   WHEN C-COMMAND-DELETE PERFORM 3000-CLAIM-DELETE ...
   WHEN C-COMMAND-INSERT PERFORM 4000-CLAIM-INSERT ...
   WHEN C-COMMAND-UPDATE PERFORM 5000-CLAIM-UPDATE ...
   WHEN OTHER
      DISPLAY 'WRONG COMMAND SPECIFIED'
      PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
END-EVALUATE.
```

---

### R02 — Record count must be greater than zero

**What it does:** Rejects any request specifying 0 records. Enforced in both the orchestrator (for READ commands) and the data layer (before opening the VSAM file).

**UNEMPLCLM.cbl — lines 887–919 (2100-ACCEPT-READ-INPUT):**
```cobol
IF WS-NUM-OF-RECS = 1 THEN
   SET C-OUT-DIR-REC TO TRUE
ELSE IF WS-NUM-OF-RECS > 1 THEN
   ...category validation...
ELSE
   DISPLAY 'NUMBER OF RECORDS SHOULD BE GREATER THAN ZERO : '
            WS-NUM-OF-RECS
   PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
END-IF.
```

**GETCLAIM.cbl — lines 119–133 (1000-OPEN-FILE):**
```cobol
IF LS-NUM-OF-RECS >= 1 THEN
   OPEN I-O UNEMP-CLAIM-FILE
   ...
ELSE
   PERFORM 7000-NEED-GT-ZERO THRU 7000-NEED-GT-ZERO-EXIT
END-IF.
```

**GETCLAIM.cbl — lines 350–358 (7000-NEED-GT-ZERO):**
```cobol
DISPLAY 'NUMBER OF RECORDS SHOULD BE GREATER THAN ZERO : '
LS-NUM-OF-RECS.
SET C-STATUS-WRONGNO TO TRUE.
```

---

### R03 — Single read (count = 1) uses direct record output mode

**What it does:** When a READ specifies exactly 1 record, the system fetches by exact key and formats output as a detailed single-record report (all demographic categories listed vertically).

**UNEMPLCLM.cbl — lines 887–889 (2100-ACCEPT-READ-INPUT):**
```cobol
IF WS-NUM-OF-RECS = 1 THEN
   SET C-OUT-DIR-REC TO TRUE
```

**GETCLAIM.cbl — lines 141–143 (2000-CLAIM-READ):**
```cobol
IF LS-NUM-OF-RECS = 1 THEN
   PERFORM 2100-CLAIM-READ-ONE THRU 2100-CLAIM-READ-ONE-EXIT
```

**GETCLAIM.cbl — lines 153–172 (2100-CLAIM-READ-ONE):**
```cobol
MOVE LS-SEARCH-ID TO UNEMP-CLAIM-KEY.
READ UNEMP-CLAIM-FILE KEY IS UNEMP-CLAIM-KEY.
EVALUATE TRUE
   WHEN C-VSAM-OK   PERFORM 2110-CLAIM-GET-REC ...
   WHEN C-VSAM-NOTFND PERFORM 6000-NO-RECORD-FOUND ...
   WHEN OTHER       PERFORM 9999-ABEND-PARA ...
END-EVALUATE.
```

---

### R04 — Range read (count > 1) requires a valid demographic category

**What it does:** When a READ specifies more than 1 record, the category field must be one of the 5 valid values. An unrecognized category triggers an abend.

**UNEMPLCLM.cbl — 88-level category names (lines 53–57):**
```cobol
88 C-BY-AGE       VALUE 'BY AGE'.
88 C-BY-ETHNICITY VALUE 'BY ETHNICITY'.
88 C-BY-INDUSTRY  VALUE 'BY INDUSTRY'.
88 C-BY-RACE      VALUE 'BY RACE'.
88 C-BY-GENDER    VALUE 'BY GENDER'.
```

**UNEMPLCLM.cbl — lines 890–919 (2100-ACCEPT-READ-INPUT):**
```cobol
ELSE IF WS-NUM-OF-RECS > 1 THEN
   EVALUATE TRUE
       WHEN C-BY-AGE       SET C-BY-AGE-OUT-REC       TO TRUE
       WHEN C-BY-ETHNICITY SET C-BY-ETHNICITY-OUT-REC  TO TRUE
       WHEN C-BY-INDUSTRY  SET C-BY-INDUSTRY-OUT-REC   TO TRUE
       WHEN C-BY-RACE      SET C-BY-RACE-OUT-REC       TO TRUE
       WHEN C-BY-GENDER    SET C-BY-GENDER-OUT-REC     TO TRUE
       WHEN OTHER
          DISPLAY 'WRONG CATEGORY SPECIFIED'
          PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
   END-EVALUATE
```

---

### R05 — Record not found returns a status code, not an abend

**What it does:** If a READ, DELETE, or UPDATE targets a key that doesn't exist in VSAM, the system returns gracefully with status code `'04'` rather than crashing. The orchestrator can check this and continue.

**GETCLAIM.cbl — lines 340–348 (6000-NO-RECORD-FOUND):**
```cobol
DISPLAY 'NO CLAIM RECORD FOUND : ' UNEMP-CLAIM-KEY.
MOVE  ZERO            TO LS-NUM-OF-RECS.
SET   C-STATUS-NOTFND TO TRUE.
```

**GETCLAIM.cbl — return code definitions (lines 47–50):**
```cobol
88 C-STATUS-OK      VALUE '00'.
88 C-STATUS-NOTFND  VALUE '04'.
88 C-STATUS-WRONGNO VALUE '08'.
88 C-STATUS-ABEND   VALUE '12'.
```

Called from READ (line 164), DELETE (line 260), and UPDATE (line 329) paths.

---

### R06 — Duplicate record rejected on INSERT

**What it does:** VSAM returns file status `'22'` if a record with the same key already exists. This hits the ABEND path, preventing silent overwrites.

**GETCLAIM.cbl — VSAM status code definition (line 35):**
```cobol
88 C-VSAM-DUPREC VALUE '22'.
```

**GETCLAIM.cbl — lines 281–293 (4000-CLAIM-INSERT):**
```cobol
WRITE UNEMP-CLAIM-REC.
EVALUATE TRUE
   WHEN C-VSAM-OK
      DISPLAY 'RECORD IS INSERTED ' LS-SEARCH-ID
      PERFORM 2100-CLAIM-READ-ONE THRU 2100-CLAIM-READ-ONE-EXIT
   WHEN OTHER
      DISPLAY 'RECORD IS NOT INSERTED ' LS-SEARCH-ID
      PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
END-EVALUATE.
```

Note: `C-VSAM-DUPREC ('22')` falls into `WHEN OTHER` and triggers the abend. The VSAM file itself enforces uniqueness on the key field.

---

### R07 — Record must exist before DELETE

**What it does:** The DELETE operation reads the record first. If the key is not found, it returns a not-found status rather than attempting a delete. No blind deletes.

**GETCLAIM.cbl — lines 239–268 (3000-CLAIM-DELETE):**
```cobol
MOVE LS-SEARCH-ID TO UNEMP-CLAIM-KEY.
READ UNEMP-CLAIM-FILE KEY IS UNEMP-CLAIM-KEY.

EVALUATE TRUE
   WHEN C-VSAM-OK
      DELETE UNEMP-CLAIM-FILE
      IF C-VSAM-OK THEN
         DISPLAY 'RECORD IS DELETED ' LS-SEARCH-ID
         PERFORM 2110-CLAIM-GET-REC THRU 2110-CLAIM-GET-REC-EXIT
      ELSE
         DISPLAY 'RECORD IS NOT DELETED' LS-SEARCH-ID
         PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
      END-IF
   WHEN C-VSAM-NOTFND
      PERFORM 6000-NO-RECORD-FOUND THRU 6000-NO-RECORD-FOUND-EXIT
   WHEN OTHER
      PERFORM 9999-ABEND-PARA THRU 9999-ABEND-PARA-EXIT
END-EVALUATE.
```

---

### R08 — Record must exist before UPDATE

**What it does:** The UPDATE operation reads the record first. If the key is not found, returns a not-found status rather than attempting a write. No blind updates.

**GETCLAIM.cbl — lines 298–337 (5000-CLAIM-UPDATE):**
```cobol
MOVE LS-SEARCH-ID TO UNEMP-CLAIM-KEY.
READ UNEMP-CLAIM-FILE KEY IS UNEMP-CLAIM-KEY.

EVALUATE TRUE
   WHEN C-VSAM-OK
      MOVE 0 TO WS-REC-LEN
      INSPECT FUNCTION TRIM(LS-SEARCH-REC, TRAILING)
         TALLYING WS-REC-LEN FOR CHARACTERS
      MOVE LS-SEARCH-REC(1:WS-REC-LEN) TO UNEMP-CLAIM-REC
      REWRITE UNEMP-CLAIM-REC
      IF C-VSAM-OK THEN
         DISPLAY 'RECORD IS UPDATED ' LS-SEARCH-ID
         PERFORM 2100-CLAIM-READ-ONE THRU 2100-CLAIM-READ-ONE-EXIT
      ELSE
         ...ABEND
      END-IF
   WHEN C-VSAM-NOTFND
      PERFORM 6000-NO-RECORD-FOUND THRU 6000-NO-RECORD-FOUND-EXIT
   ...
END-EVALUATE.
```

---

### R09 — Read-back confirmation after INSERT

**What it does:** After a successful INSERT, the system immediately reads the record back and returns it to the caller. Confirms the write was durable.

**GETCLAIM.cbl — lines 284–287 (4000-CLAIM-INSERT):**
```cobol
WHEN C-VSAM-OK
   DISPLAY 'RECORD IS INSERTED ' LS-SEARCH-ID
   PERFORM 2100-CLAIM-READ-ONE
      THRU 2100-CLAIM-READ-ONE-EXIT
```

---

### R10 — Read-back confirmation after UPDATE

**What it does:** After a successful UPDATE, the system immediately reads the record back and returns it to the caller. Confirms the rewrite was durable.

**GETCLAIM.cbl — lines 317–321 (5000-CLAIM-UPDATE):**
```cobol
IF C-VSAM-OK THEN
   DISPLAY 'RECORD IS UPDATED ' LS-SEARCH-ID
   PERFORM 2100-CLAIM-READ-ONE
      THRU 2100-CLAIM-READ-ONE-EXIT
```

---

### R11 — Capture-before-delete (return the deleted record's data)

**What it does:** On DELETE, the record is read into the return buffer *before* the delete executes. The caller receives the data of the record that was just deleted — useful for audit logging and confirmation output.

**GETCLAIM.cbl — lines 246–252 (3000-CLAIM-DELETE):**
```cobol
WHEN C-VSAM-OK
   DELETE UNEMP-CLAIM-FILE
   IF C-VSAM-OK THEN
      DISPLAY 'RECORD IS DELETED ' LS-SEARCH-ID
      PERFORM 2110-CLAIM-GET-REC          ← copies record to return buffer
         THRU 2110-CLAIM-GET-REC-EXIT
```

**GETCLAIM.cbl — lines 174–180 (2110-CLAIM-GET-REC):**
```cobol
MOVE UNEMP-CLAIM-REC TO LS-RETURN-REC (1).
MOVE WS-REC-LEN      TO LS-RETURN-REC-LEN (1).
```

Note: The READ at line 243 loads the record into `UNEMP-CLAIM-REC` before the DELETE. VSAM holds the record in the buffer until the next I/O operation, so `2110-CLAIM-GET-REC` captures it intact.

---

### R12 — Batch execution capped at 200 commands

**What it does:** The orchestrator's main loop processes at most 200 input commands per execution. This is a hard limit tied to the SYSIN batch input model and the fixed-size `WS-RETURN-DATA` array.

**UNEMPLCLM.cbl — line 802 (0000-MAIN-PARA):**
```cobol
PERFORM VARYING ACCEPT-SUB FROM 1 BY 1
        UNTIL C-CMD-EOF OR C-STATUS-ABEND
        OR ACCEPT-SUB > 200
```

**UNEMPLCLM.cbl — WS-RETURN-DATA definition (lines 67–72):**
```cobol
01  WS-RETURN-DATA.
    05 FILLER OCCURS 1 TO 200
               DEPENDING ON WS-NUM-OF-RECS.
       10 WS-RETURN-REC-LEN  PIC 9(03) COMP.
       10 WS-RETURN-ID       PIC X(08).
       10 WS-RETURN-REC      PIC X(252).
```

The return data array is also bounded at 200 entries. Both constraints align.

---

## Rules Created in the Migration (R15–R20)

These rules have **no equivalent in the COBOL source**. They were identified as gaps during the modernization project and implemented for the first time in the AWS system.

| Rule | Description | Gap in COBOL |
|------|-------------|--------------|
| **R15** | Cross-category totals must balance: sum(age) = sum(race) = sum(gender) | INA fields exist in the data structure (`UCR-AGE-INA`, `UCR-RACE-INA`, etc. at `unemplclm.cbl` lines 739–784) but totals are never summed or compared across categories |
| **R16** | Period key must be valid MMDDYYYY format with day=01 | Key is `PIC X(08)` (`getclaim.cbl` line 26). Any 8-character string is accepted — no format check |
| **R17** | Claim counts must be non-negative integers | Counts stored as `PIC X(05)` strings (e.g., `UCR-AGE-LE-22 PIC X(05)` at `unemplclm.cbl` line 741). No numeric validation performed |
| **R18** | Claim counts must not exceed a realistic ceiling | No upper bound anywhere in either COBOL program |
| **R19** | INA (inapplicable) counts must be included in totals | INA fields are parsed (`UCR-AGE-INA`, `UCR-ETH-INA`, `UCR-IND-INA`, `UCR-RACE-INA`, `UCR-GEN-INA` at `unemplclm.cbl` lines 739–784) and displayed, but never validated against category subtotals |
| **R20** | Role-based write authorization | The mainframe system has no authentication layer. Any process with access to SYSIN can execute any operation |

---

## Abend vs. Graceful Error Summary

Understanding how the COBOL handles errors clarifies which rules are hard stops vs. soft returns.

| Condition | COBOL Response | Return Code |
|-----------|----------------|-------------|
| Invalid operation code | Abend (`9999-ABEND-PARA`) | `'12'` |
| Record count = 0 | Abend | `'12'` |
| Invalid demographic category | Abend | `'12'` |
| Duplicate key on INSERT | Abend (via VSAM `'22'` → WHEN OTHER) | `'12'` |
| Record not found | Graceful return | `'04'` |
| VSAM file open error | Abend | `'12'` |
| VSAM unexpected status | Abend | `'12'` |

The abend para (`getclaim.cbl` lines 373–379) sets `C-STATUS-ABEND` and displays the VSAM file status. The orchestrator loop checks `C-STATUS-ABEND` as a stop condition (line 801).
