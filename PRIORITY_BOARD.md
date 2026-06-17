# J.A.R.V.I.S. — Quick Priority Board

## 🚨 CRITICAL (Fix ASAP — Security) — ~2 ore

```
┌─────────────────────────────────────┐
│ 1. Path Traversal Upload Fix         │ ⏳ TODO     15 min
├─────────────────────────────────────┤
│ 2. Session Ownership Validation      │ ⏳ TODO    1-2 hr
├─────────────────────────────────────┤
│ 3. Block Sensitive File Types        │ ⏳ TODO      5 min
├─────────────────────────────────────┤
│ 4. Secure Redis (requirepass)        │ ⏳ TODO     10 min
├─────────────────────────────────────┤
│ 5. Replace Shell Execution           │ ⏳ TODO     30 min
└─────────────────────────────────────┘
```

---

## 🔥 HIGH PRIORITY (Next Sprint) — ~15 ore

```
┌─────────────────────────────────────┐
│ 6. Split routes.py (1146 → 7 files)  │ ⏳ TODO    2-3 hr
├─────────────────────────────────────┤
│ 7. Fix psutil Blocking (async)       │ ⏳ TODO     45 min
├─────────────────────────────────────┤
│ 8. Reduce Metrics Poll (2s → 5s)     │ ⏳ TODO     20 min
├─────────────────────────────────────┤
│ 9. Semantic Cache + TTL              │ ⏳ TODO      1 hr
├─────────────────────────────────────┤
│10. SQLite Connection Pooling         │ ⏳ TODO     45 min
├─────────────────────────────────────┤
│11. UTC Timezone Standardization      │ ⏳ TODO      1 hr
├─────────────────────────────────────┤
│12. Rate Limiting (/api/chat)         │ ⏳ TODO     30 min
├─────────────────────────────────────┤
│13. Refactor MultiAgent (God Object)  │ ⏳ TODO    3-4 hr
├─────────────────────────────────────┤
│46. Unit Tests (pytest)               │ ⏳ TODO    4-6 hr
└─────────────────────────────────────┘
```

---

## 💛 MEDIUM (Polish & UX) — ~25 ore

```
14. Upload Progress UI              ⏳ TODO     45 min
15. Max Input Validation            ⏳ TODO     10 min
16. Streaming Race Condition Fix    ⏳ TODO      1 hr
18. Remove Proxy Duplication        ⏳ TODO    1-2 hr
19. Better Error Messages           ⏳ TODO     30 min
20. Session Persistence Validation  ⏳ TODO     20 min
21. Tighten CORS Policy             ⏳ TODO     10 min
22. Threading Safe SQLite           ⏳ TODO     45 min
33. Centralized Logging             ⏳ TODO      2 hr
34. Monitoring Dashboard            ⏳ TODO    3-4 hr
37. Export PDF Feature              ⏳ TODO    1-2 hr
45. Plugin System                   ⏳ TODO    4-5 hr
47. Integration Tests               ⏳ TODO    3-4 hr
49. Security Audit (OWASP ZAP)      ⏳ TODO      1 hr
```

---

## 🔵 LOW (Optional Polish) — ~5 ore

```
23. Auto-scroll Smart              ⏳ TODO     15 min
24. Feedback Button Feedback       ⏳ TODO     15 min
25. Remove Dead Code (DOCKER_API)  ⏳ TODO      5 min
26. Extract Magic Constants        ⏳ TODO     30 min
27. Log Silent Exceptions          ⏳ TODO     10 min
28. Config-driven Upload Dir       ⏳ TODO      5 min
29. JSON Parse Error Logging       ⏳ TODO     10 min
30. Hard Break in ReAct Loop       ⏳ TODO     15 min
40. Dark Mode Toggle               ⏳ TODO     30 min
41. Keyboard Shortcuts Modal       ⏳ TODO     30 min
43. RAG Threshold UI               ⏳ TODO     45 min
54. Docker Image Optimization      ⏳ TODO     45 min
```

---

## 📊 Sprint Allocation

### **Week 1 — Security & Stability** (12 hrs)
- [ ] Items 1-5 (Critical security)
- [ ] Items 6, 17 (Refactoring)
- [ ] Items 7-8 (Performance)
- [ ] Item 12 (Rate limiting)

**Definition of Done**: No CRITICAL issues, 60% code review

---

### **Week 2 — Quality & Testing** (15 hrs)
- [ ] Items 9-11 (Optimization)
- [ ] Item 33 (Logging)
- [ ] Items 46-47 (Tests 70%+)
- [ ] Item 49 (Security audit)

**DoD**: 70% test coverage, 0 security findings

---

### **Week 3 — UX Polish** (10 hrs)
- [ ] Items 14-15 (Input/upload UX)
- [ ] Items 19-20 (Error handling)
- [ ] Items 23-24 (UI Polish)
- [ ] Item 28 (Config management)

**DoD**: Zero UX regressions, accessibility audit pass

---

### **Week 4+ — Features & Enhancements** (40+ hrs)
- [ ] Item 34 (Monitoring)
- [ ] Item 37 (PDF export)
- [ ] Item 45 (Plugin system)
- [ ] Item 41 (Shortcuts)

**DoD**: New features documented, no tech debt

---

## 🎯 Today's Focus

Pick **ONE** item from CRITICAL, then move to HIGH:

```
TODAY:
[ ] Start Item #1 (path traversal) — 15 min
[ ] Start Item #4 (Redis security) — 10 min
[ ] Code review + merge to main
```

**Suggested commit message**:
```
security: fix path traversal + redis auth + shell execution

- sanitize file uploads with basename + whitelist extensions
- add requirepass to redis + bind localhost
- replace subprocess_shell with subprocess_exec
- add rate limiting to /api/chat (10/min)

Closes: #CRITICAL-SEC-001, #CRITICAL-SEC-002
```

---

## 📞 Contact / Questions?

If stuck on any item:
1. Check IMPROVEMENTS.md for full context
2. Run tests: `pytest backend/tests/`
3. Profile: `python -m cProfile ...`
4. Debug logs: `export DEBUG=1 && python main.py`

---

**Generated**: 2026-06-17  
**Status**: Ready for Sprint Planning
