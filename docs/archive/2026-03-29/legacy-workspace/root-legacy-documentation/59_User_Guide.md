# DOCUMENT 59: USER GUIDE
## Holy Grail Refinery - Documentation & Training

**Document ID:** 59  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Status:** Specification Complete

---

## GETTING STARTED

### What is Holy Grail Refinery?

Holy Grail Refinery analyzes source code across 14 programming languages and extracts universal computational intent into LogicNodes.

### Quick Start

**1. Submit a Mission**

Navigate to Mission Control UI: `http://localhost:3000`

Click "New Mission" and provide:
- **Description:** "Analyze my Python web scraper for optimization opportunities"
- **Source:** Upload files or link GitHub repository
- **Languages:** Select Python

**2. Monitor Progress**

Watch real-time progress as 35 agents analyze your code:
- PM Agent receives your request
- CEO Agent coordinates the work
- Python Specialist extracts LogicNodes
- Audit Agent verifies accuracy
- Results delivered back to you

**3. Review Results**

View your mission results including:
- Extracted LogicNodes
- Optimization recommendations
- Code quality scores
- Cross-language equivalences

---

## SUBMITTING MISSIONS

### Mission Types

**Code Analysis**
- Extract computational patterns
- Identify optimization opportunities
- Generate semantic documentation

**Cross-Language Comparison**
- Compare implementations across languages
- Find equivalent patterns
- Understand semantic differences

**Quality Audit**
- Assess code quality metrics
- Verify algorithmic correctness
- Identify potential bugs

### Specifying Requirements

Be specific in your mission description:

❌ Bad: "Analyze my code"

✅ Good: "Analyze Python data pipeline for list operations and suggest performance improvements"

### Source Options

**GitHub Repository**
```
Repository: https://github.com/user/project
Branch: main
Path: src/data_pipeline/
```

**File Upload**
- Drag and drop files
- Supports: .py, .js, .java, .cpp, and all 14 languages
- Max 100MB per upload

**Direct Paste**
- Paste code directly into editor
- Good for small snippets

---

## UNDERSTANDING RESULTS

### LogicNode Viewer

Each LogicNode shows:
- **Concept:** What operation is performed
- **Intent:** Plain English description
- **Source:** Original code location
- **Confidence:** Accuracy score (>95% = high confidence)
- **Verification:** 999/1000 tests passed

### Optimization Recommendations

Results include actionable suggestions:
```
⚡ OPTIMIZATION OPPORTUNITY

Location: scraper.py:45-52
Current: Nested loops iterating over list
Recommendation: Use list comprehension
Expected Impact: 3x faster execution
```

### Quality Scores

- **Code Quality:** 8.5/10
- **Complexity:** 6.2/10 (lower is better)
- **Maintainability:** 7.8/10

---

## BEST PRACTICES

### For Best Results

✅ **Provide context** - Explain what your code does
✅ **Be specific** - Target specific domains (list operations, async patterns)
✅ **Clean code** - Well-formatted code analyzes better
✅ **Include tests** - Helps verification

### Common Mistakes

❌ Vague descriptions
❌ Mixed concerns in one mission
❌ Extremely large codebases (>100K LOC)
❌ Obfuscated code

---

## TROUBLESHOOTING

### Mission Stuck?

Check status: Mission Control → View Logs

### Low Confidence Scores?

- Code may be unusual or highly complex
- Consider simplifying
- Review for edge cases

### Need Help?

Contact support: support@hgr.local

---

## DOCUMENT METADATA

**Document ID:** 59  
**Version:** 1.0  
**Created:** February 6, 2026

---

*End of User Guide*
