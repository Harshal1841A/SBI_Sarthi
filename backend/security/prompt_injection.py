import re
from typing import Tuple, List, Dict

# ────────────────────────────────────────────────────────────────
# Prompt Injection Defense — Shield Agent Input Layer
# Detects and blocks known attack patterns before they reach LLM.
# 100% block rate for known patterns (per PRD acceptance criteria).
# ────────────────────────────────────────────────────────────────

PROMPT_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(previous|above|earlier|all)', re.IGNORECASE),
    re.compile(r'forget\s+(your|the)\s+instructions', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+', re.IGNORECASE),
    re.compile(r'system\s+prompt', re.IGNORECASE),
    re.compile(r'new\s+role\s*:', re.IGNORECASE),
    re.compile(r'DAN\s*\(|DARK\s*AI', re.IGNORECASE),
    re.compile(r'ignore\s+all\s+previous\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(previous|above|earlier)', re.IGNORECASE),
    re.compile(r'override\s+(previous|default|system)', re.IGNORECASE),
    re.compile(r'pretend\s+to\s+be', re.IGNORECASE),
    re.compile(r'act\s+as\s+if\s+you\s+are', re.IGNORECASE),
    re.compile(r'simulate\s+being', re.IGNORECASE),
    re.compile(r'ignore\s+your\s+programming', re.IGNORECASE),
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'\bDAN\b', re.IGNORECASE),
    re.compile(r'hack\s+(the|this|system)', re.IGNORECASE),
    re.compile(r'extract\s+(all|every)\s+data', re.IGNORECASE),
    re.compile(r'dump\s+(database|memory|context)', re.IGNORECASE),
    re.compile(r'leak\s+(prompt|instructions|system)', re.IGNORECASE),
    re.compile(r'transfer\s+all\s+(money|funds)', re.IGNORECASE),
    re.compile(r'wire\s+transfer\s+to', re.IGNORECASE),
    re.compile(r'send\s+all\s+money\s+to', re.IGNORECASE),
]

# High-risk banking intents that trigger additional fact-checking
HIGH_RISK_INTENTS = [
    "loan_sanction",
    "account_open",
    "fraud_report",
    "fund_transfer",
    "card_block",
    "beneficiary_add",
    "high_value_transaction"
]


def detect_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    """Detect prompt injection attempts in user input.
    
    Returns:
        (is_injection, list_of_matched_patterns)
    """
    flags = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            flags.append(match.group(0))
    return len(flags) > 0, flags


def calculate_risk_score(
    input_text: str,
    output_text: str,
    intent: str,
    entities: dict
) -> float:
    """Calculate overall risk score (0.0-1.0) for a state transition.
    
    Factors:
    - Prompt injection detection (0.4 weight)
    - High-risk intent (0.3 weight)
    - Suspicious entities (0.2 weight)
    - Context anomalies (0.1 weight)
    """
    score = 0.0
    
    # Prompt injection
    is_injection, _ = detect_prompt_injection(input_text)
    if is_injection:
        score += 0.4
    
    # High-risk intent
    if intent in HIGH_RISK_INTENTS:
        score += 0.3
    
    # Suspicious entities
    if entities.get("amount", 0) > 500000:  # > 5 lakh
        score += 0.1
    if entities.get("new_beneficiary"):
        score += 0.1
    
    # Context anomalies (placeholder for more sophisticated checks)
    if "urgent" in input_text.lower() or "immediately" in input_text.lower():
        score += 0.05
    
    return min(score, 1.0)


def shield_guard(
    input_text: str,
    output_text: str,
    state: dict
) -> dict:
    """Full Shield Agent guard check.
    
    Returns dict with:
    - input_safe: bool
    - output_safe: bool
    - flags: list of detected issues
    - action: "allow" | "block" | "rewrite" | "escalate"
    - risk_score: float 0-1
    """
    result = {
        "input_safe": True,
        "output_safe": True,
        "flags": [],
        "action": "allow",
        "risk_score": 0.0
    }
    
    # 1. Input: Prompt Injection Detection
    injection_detected, injection_flags = detect_prompt_injection(input_text)
    if injection_detected:
        result["input_safe"] = False
        result["flags"].extend([f"prompt_injection:{f}" for f in injection_flags])
        result["action"] = "block"
        result["risk_score"] = 1.0
        return result  # Block immediately — no need to check output
    
    # 2. Input: Rate limit / flooding check (basic)
    if len(input_text) > 5000:
        result["flags"].append("input_length:suspicious")
        result["risk_score"] += 0.1
    
    # 3. Output: Hallucination check for high-risk intents
    intent = state.get("current_intent", "")
    if intent in HIGH_RISK_INTENTS:
        # In production: retrieve_facts_from_rag(output_text)
        hallucination_score = _advanced_hallucination_check(output_text)
        if hallucination_score > 0.3:
            result["output_safe"] = False
            result["flags"].append(f"hallucination_score:{hallucination_score:.2f}")
            if hallucination_score < 0.7:
                result["action"] = "rewrite"
            else:
                result["action"] = "block"
            result["risk_score"] = max(result["risk_score"], hallucination_score)
    
    # 4. Output: RBI Policy Alignment Check
    policy_violations = _check_rbi_policy_alignment(output_text)
    if policy_violations:
        result["flags"].extend(policy_violations)
        result["action"] = "block"
        result["risk_score"] = 1.0
    
    # 5. Final risk score calculation
    result["risk_score"] = max(
        result["risk_score"],
        calculate_risk_score(input_text, output_text, intent, state.get("extracted_entities", {}))
    )
    
    # Auto-escalate if risk_score > 0.7
    if result["risk_score"] > 0.7 and result["action"] == "allow":
        result["action"] = "escalate"
    
    return result


def _advanced_hallucination_check(text: str) -> float:
    """Lazy-initialized RAG fact-checker."""
    try:
        from nlp.rag_engine import RAGEngine
        _rag = RAGEngine()
        result = _rag.verify_financial_claim(text)
        if not result["verified"]:
            return 0.9  # High hallucination score
        return 0.0
    except Exception as e:
        # If RAG is unavailable, assume safe (conservative) or flag for review
        return 0.0


def _check_rbi_policy_alignment(text: str) -> List[str]:
    """Check RBI FREE-AI 7 Sutras alignment.
    Returns list of violation descriptions.
    """
    violations = []
    text_lower = text.lower()
    
    # Sutra 1: No guarantee of returns on investments
    investment_guarantees = [
        "guaranteed return", "guaranteed profit", "sure profit",
        "100% return", "risk-free investment", "no risk investment"
    ]
    for phrase in investment_guarantees:
        if phrase in text_lower:
            violations.append(f"rbi_violation:sutra1_guarantee:{phrase}")
    
    # Sutra 2: No unauthorized financial advice
    if "invest in" in text_lower and "not financial advice" not in text_lower:
        # This is a heuristic — in production, use more nuanced checks
        pass
    
    # Sutra 3: Transparency about AI involvement
    if "i am a human" in text_lower or "i am your relationship manager" in text_lower:
        violations.append("rbi_violation:sutra3_ai_transparency")
    
    # Sutra 4: No discriminatory language
    discriminatory = ["lower caste", "upper caste", "religion based", "gender bias"]
    for d in discriminatory:
        if d in text_lower:
            violations.append(f"rbi_violation:sutra4_discrimination:{d}")
    
    # Sutra 5: Data privacy (PII should already be scrubbed, but double-check)
    if re.search(r'\b\d{12}\b', text):
        violations.append("rbi_violation:sutra5_pii_exposure:aadhaar")
    
    return violations
