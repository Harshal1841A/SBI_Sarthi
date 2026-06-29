import re
import hashlib
from state import SarthiState
from security.verhoeff import validate_aadhaar
from security.consent import create_consent_artifact, store_consent_artifact, get_last_consent_hash, get_consent_notice
from security.audit import create_audit_artifact
from security.encryption import hash_field

# ────────────────────────────────────────────────────────────────
# Acquisition Agent — Customer Onboarding (KYC, V-KYC, Consent)
# Handles: account_open, kyc_upload, loan_application, consent_management
# Saga steps: create_profile -> verify_kyc -> v_kyc -> fund_account
# ────────────────────────────────────────────────────────────────


async def acquisition_agent(state: SarthiState) -> dict:
    """Acquisition Agent: handle onboarding flows, KYC, consent, loan origination.
    
    State machine for onboarding:
    idle -> collect_aadhaar -> collect_pan -> e_kyc -> consent_collection -> v_kyc -> fund_account -> complete
    """
    step = state.get("onboarding_step", "idle")
    intent = state.get("current_intent", "")
    messages = state.get("messages", [])
    lang = state.get("language", "en")
    
    if not messages:
        return _welcome_onboarding(state)
    
    last_msg = messages[-1]
    user_text = last_msg.get("content", "")
    
    # Route based on current step
    if step == "idle":
        return _start_onboarding(state)
    elif step == "collect_aadhaar":
        return _process_aadhaar(state, user_text)
    elif step == "collect_pan":
        return _process_pan(state, user_text)
    elif step == "e_kyc":
        return _process_ekyc(state)
    elif step == "consent_collection":
        return _process_consent(state, user_text)
    elif step == "v_kyc":
        return _process_vkyc(state)
    elif step == "fund_account":
        return _process_funding(state, user_text)
    elif step == "loan_application":
        return _process_loan(state, user_text)
    else:
        return _default_acquisition_response(state)


def _welcome_onboarding(state: SarthiState) -> dict:
    """Welcome message for new onboarding session."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "Welcome to SBI! I am Sarthi, your digital banking assistant. To open your account, I'll need your Aadhaar and PAN. Let's start with your Aadhaar number.",
        "hi": "SBI mein aapka swagat hai! Main Sarthi hoon, aapka digital banking saathi. Khata kholne ke liye mujhe aapka Aadhaar aur PAN chahiye. Aadhaar number se shuru karte hain.",
        "mr": "SBI madhye tumche svagat! Mi Sarthi ahe, tumcha digital banking saathi. Khata ugadnyasathi tumcha Aadhaar ani PAN havet. Aadhaar number ne suru karuya."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "onboarding_step": "collect_aadhaar",
        "status": "RUNNING",
        # Resolved M-6: always spread existing metadata — never replace the whole dict
        "metadata": {**state.get("metadata", {}), "onboarding_started": True}
    }


def _start_onboarding(state: SarthiState) -> dict:
    """Start onboarding flow after intent classification."""
    return _welcome_onboarding(state)


def _process_aadhaar(state: SarthiState, user_text: str) -> dict:
    """Process Aadhaar input from user."""
    lang = state.get("language", "en")
    
    # Extract 12-digit Aadhaar from text (strip ALL whitespace, dashes)
    import re
    cleaned_text = re.sub(r'[\s\-]+', '', user_text)
    aadhaar_match = re.search(r'\b\d{12}\b', cleaned_text)
    
    if not aadhaar_match:
        # User hasn't provided Aadhaar yet — ask again
        responses = {
            "en": "Please provide your 12-digit Aadhaar number. It will be securely verified.",
            "hi": "Kripya apna 12-digit Aadhaar number bataiye. Ye surakshit tareeke se verify kiya jayega.",
            "mr": "Kripaya tumcha 12-anki Aadhaar number sanga. Te surakshit riitaya verify kela jael."
        }
        return {
            "response_text": responses.get(lang, responses["en"]),
            "onboarding_step": "collect_aadhaar",
            "status": "RUNNING"
        }
    
    aadhaar = aadhaar_match.group(0)
    validation = validate_aadhaar(aadhaar)
    
    if not validation["valid"]:
        create_audit_artifact(
            event_type="shield_flag",
            session_id=state["session_id"],
            agent_name="acquisition",
            decision={"action": "aadhaar_validation_failed", "reason": validation.get("error")},
            state_snapshot=dict(state)
        )
        
        responses = {
            "en": f"The Aadhaar number you provided is invalid: {validation.get('error')}. Please check and try again.",
            "hi": f"Aapka Aadhaar number galat hai: {validation.get('error')}. Kripya check karke dobara koshish karein.",
            "mr": f"Tumcha Aadhaar number chukicha ahe: {validation.get('error')}. Kripaya tapasaun parat prayatna kara."
        }
        return {
            "response_text": responses.get(lang, responses["en"]),
            "onboarding_step": "collect_aadhaar",
            "shield_flags": [f"aadhaar_invalid:{validation.get('error')}"],
            "status": "RUNNING"
        }
    
    # Aadhaar valid — hash it IMMEDIATELY before storing in state
    aadhaar_hash = hash_field(aadhaar)
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="acquisition",
        decision={"action": "aadhaar_validated", "last4": validation["last4"]},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": f"Aadhaar verified (ending in {validation['last4']}). Now please provide your PAN number.",
        "hi": f"Aadhaar verify ho gaya (antim 4 ank: {validation['last4']}). Ab apna PAN number dijiye.",
        "mr": f"Aadhaar verify zala (shivtche 4 ank: {validation['last4']}). Aata tumcha PAN number dya."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "aadhaar_number": aadhaar_hash,  # HASHED — never raw
        "aadhaar_last4": validation["last4"],
        "onboarding_step": "collect_pan",
        "completed_steps": ["create_profile"],
        "status": "RUNNING"
    }


def _process_pan(state: SarthiState, user_text: str) -> dict:
    """Process PAN input from user."""
    lang = state.get("language", "en")
    
    import re
    pan_match = re.search(r'\b[A-Z]{5}\d{4}[A-Z]\b', user_text.upper().replace(" ", ""))
    
    if not pan_match:
        responses = {
            "en": "Please provide your PAN number in format AAAAA9999A.",
            "hi": "Kripya apna PAN number format AAAAA9999A mein dijiye.",
            "mr": "Kripaya tumcha PAN number AAAAA9999A format madhe dya."
        }
        return {
            "response_text": responses.get(lang, responses["en"]),
            "onboarding_step": "collect_pan",
            "status": "RUNNING"
        }
    
    pan = pan_match.group(0)

    # Resolved L-7: pan already matched the full-pattern regex above;
    # the second re.match() check was redundant dead code — removed.

    # Resolved C-5: Hash PAN IMMEDIATELY — never store raw PAN in state.
    # Raw PAN in state would be dumped into every audit log snapshot,
    # violating DPDP Act 2023 / IT Act Section 43A.
    pan_hash = hash_field(pan)
    pan_display = pan[:2] + "***" + pan[-1]  # safe display: AB***Z

    # PAN valid — proceed to eKYC
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="acquisition",
        decision={"action": "pan_validated", "pan_display": pan_display},
        state_snapshot=dict(state)
    )

    responses = {
        "en": "PAN verified. Proceeding to eKYC verification. This will take a moment.",
        "hi": "PAN verify ho gaya. eKYC verification process ho raha hai. Thoda intezar karein.",
        "mr": "PAN verify zala. eKYC verification process suru ahe. Thoda pratiksha kara."
    }

    return {
        "response_text": responses.get(lang, responses["en"]),
        "pan_number": pan_hash,   # Resolved C-5: HASHED — never raw
        "onboarding_step": "e_kyc",
        "completed_steps": ["create_profile", "verify_kyc"],
        "status": "RUNNING"
    }


# Resolved C-6: verify_aadhaar() was dead code that double-hashed an already-hashed
# Aadhaar (from _process_aadhaar). This produced a corrupted hash value useless
# for any UIDAI AUA call. The function also used time.sleep(1) which blocks the
# event loop. Removed entirely — eKYC is handled in _process_ekyc() via the
# SBI middleware mock. If real UIDAI OTP flow is needed, implement it there
# using asyncio.sleep() and the hashed Aadhaar for internal lookup only.


def _process_ekyc(state: SarthiState) -> dict:
    """Process eKYC verification via SBI middleware (mock)."""
    lang = state.get("language", "en")
    
    # Mock eKYC call — in production, calls SBI middleware (NOT direct UIDAI)
    kyc_token = f"kyc_{state['session_id'][:8]}_{hashlib.sha256(state.get('aadhaar_number', '').encode('utf-8')).hexdigest()[:6]}"
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="acquisition",
        decision={"action": "e_kyc_verified", "kyc_token": kyc_token[:10] + "***"},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": "eKYC verification successful. Now I need your consent for data usage. This is required by law.",
        "hi": "eKYC verification safal raha. Ab mujhe aapka data usage ke liye consent chahiye. Ye kanooni zaroorat hai.",
        "mr": "eKYC verification yashasvi zale. Aata mala tumcha data vaparnyasathi consent havet. He kanoni garaj ahe."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "kyc_token": kyc_token,
        "onboarding_step": "consent_collection",
        "completed_steps": ["create_profile", "verify_kyc"],
        "status": "RUNNING"
    }


def _process_consent(state: SarthiState, user_text: str) -> dict:
    """Process consent collection — 4 separate requests per DPDP Act."""
    lang = state.get("language", "en")
    consent_artifacts = state.get("consent_artifacts", [])
    
    # Determine which consent we're collecting.
    # Use ALL artifacts (granted OR rejected) to avoid re-asking for rejected purposes.
    purposes_already_asked = {a["purpose_id"] for a in consent_artifacts}
    all_purposes = ["P001", "P002", "P003", "P004"]
    
    next_purpose = None
    for p in all_purposes:
        if p not in purposes_already_asked:
            next_purpose = p
            break
    
    if not next_purpose:
        # All consents collected — proceed to V-KYC
        return _proceed_to_vkyc(state)
    
    # Check if user has responded to the current consent request
    user_text_lower = user_text.lower()
    yes_indicators = ["yes", "ho", "haan", "ha", "sahi", "barobar", "agree", "sahmat", "同意", "sí"]
    no_indicators = ["no", "na", "nako", "nahi", "nahin", "reject", "refuse", "cancel"]
    
    has_yes = any(re.search(r'\b' + y + r'\b', user_text_lower) for y in yes_indicators)
    has_no = any(re.search(r'\b' + n + r'\b', user_text_lower) for n in no_indicators)
    
    if has_yes or has_no:
        # Record consent artifact
        granted = has_yes and not has_no
        artifact = create_consent_artifact(
            user_id=state.get("user_id") or state["session_id"],
            purpose_id=next_purpose,
            lang=lang,
            granted=granted,
            prev_hash=get_last_consent_hash(state.get("user_id") or state["session_id"]),
            channel=state.get("channel", "chat")
        )
        store_consent_artifact(artifact)
        
        create_audit_artifact(
            event_type="consent_grant" if granted else "consent_reject",
            session_id=state["session_id"],
            agent_name="acquisition",
            decision={"purpose_id": next_purpose, "granted": granted},
            state_snapshot=dict(state)
        )
        
        # If P001 (KYC) rejected — onboarding cannot proceed
        if next_purpose == "P001" and not granted:
            responses = {
                "en": "We cannot open an account without KYC consent. If you change your mind, please visit any SBI branch or the YONO app.",
                "hi": "KYC consent ke bina hum khata nahi khol sakte. Agar aapka man badle, toh kisi SBI branch ya YONO app par aaiye.",
                "mr": "KYC consent shivay aamhi khata ugadu shakat nahi. Jar tumhala vichar badalala tar koni SBI branch kiva YONO app var ya."
            }
            return {
                "response_text": responses.get(lang, responses["en"]),
                "consent_artifacts": [artifact],
                "onboarding_step": "idle",
                "status": "FAILED",
                "last_error": "P001_rejected"
            }
        
        # Resolved M-8: avoid double-counting consent artifacts.
        # State may already have some artifacts from previous turns.
        # Re-read them by purpose_id to build the authoritative list.
        existing_artifacts = state.get("consent_artifacts", [])
        existing_by_purpose = {a["purpose_id"]: a for a in existing_artifacts}
        existing_by_purpose[artifact["purpose_id"]] = artifact  # upsert new
        updated_artifacts = list(existing_by_purpose.values())

        # Move to next consent or V-KYC
        # Check remaining by presence (not grant status) to avoid infinite loop on rejections
        asked_purposes = {a["purpose_id"] for a in updated_artifacts}
        remaining = [p for p in all_purposes if p not in asked_purposes]
        if not remaining:
            return {
                **_proceed_to_vkyc(state),
                "consent_artifacts": updated_artifacts
            }

        # Ask for next consent
        next_purpose_obj = remaining[0]
        notice = get_consent_notice(next_purpose_obj, lang)

        return {
            "response_text": notice["text"],
            "consent_artifacts": updated_artifacts,
            "onboarding_step": "consent_collection",
            "status": "RUNNING"
        }
    
    # First time — ask for P001 consent
    notice = get_consent_notice(next_purpose, lang)
    
    return {
        "response_text": notice["text"] + "\n\nPlease say Yes or No.",
        "onboarding_step": "consent_collection",
        "status": "RUNNING"
    }


def _proceed_to_vkyc(state: SarthiState) -> dict:
    """After all consents collected, proceed to V-KYC (HITL interrupt)."""
    lang = state.get("language", "en")
    
    create_audit_artifact(
        event_type="hitl_interrupt",
        session_id=state["session_id"],
        agent_name="acquisition",
        decision={"reason": "v_kyc_mandated", "rbi_rule": "Master Direction on KYC 2023"},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": "All consents recorded. As per RBI rules, you need a 2-minute video verification with an SBI officer. I am connecting you now.",
        "hi": "Saare consents record kar liye gaye hain. RBI niyam ke anusar, aapko 2-minute ka video verification SBI adhikari se karna hoga. Main aapko jod raha hoon.",
        "mr": "Sarve consent record kelelet. RBI niyamannusar, tumhala 2-minitancha video verification SBI adhikaryashi karava lage. Mi tumhala jodat ahe."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "onboarding_step": "v_kyc",
        "interrupted": True,
        "interrupt_reason": "v_kyc_mandated",
        "requires_hitl": True,
        "status": "RUNNING"
    }


def _process_vkyc(state: SarthiState) -> dict:
    """V-KYC step — waits for HITL approval."""
    # This state is reached after HITL resume
    lang = state.get("language", "en")
    
    human_decision = state.get("human_decision")
    if not human_decision or not human_decision.get("approved"):
        # V-KYC not yet approved — remain in HITL
        return {
            "response_text": "Waiting for video verification. Please stay connected.",
            "interrupted": True,
            "interrupt_reason": "v_kyc_mandated",
            "status": "RUNNING"
        }
    
    # V-KYC approved — proceed to funding
    responses = {
        "en": "Video verification complete! Now let's fund your account with the minimum balance of Rs. 500.",
        "hi": "Video verification pura ho gaya! Ab aapke khata mein Rs. 500 ka minimum balance jama karte hain.",
        "mr": "Video verification purna zale! Aata aaplya khatavar Rs. 500 minimum balance jama karuya."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "onboarding_step": "fund_account",
        "completed_steps": ["create_profile", "verify_kyc", "v_kyc"],
        "status": "RUNNING"
    }


def _process_funding(state: SarthiState, user_text: str) -> dict:
    """Process account funding (mock)."""
    lang = state.get("language", "en")
    
    # Mock account creation
    account_id = f"SBIN{int(hashlib.sha256(state['session_id'].encode('utf-8')).hexdigest()[:8], 16):010d}"
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="acquisition",
        decision={"action": "account_funded", "account_id": account_id[:8] + "***"},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": f"Congratulations! Your savings account is now open. Account number: {account_id}. Your initial deposit of Rs. 500 has been credited. Welcome to SBI!",
        "hi": f"Badhai ho! Aapka bachat khata khul gaya hai. Khata number: {account_id}. Aapka Rs. 500 ka shuruati jama ho gaya hai. SBI mein swagat hai!",
        "mr": f"Abhinandan! Tumcha bachat khata ugadle ahe. Khata kramank: {account_id}. Tumche Rs. 500 che suruvatiche jama zalelet. SBI madhye svagat!"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "account_id": account_id,
        "onboarding_step": "complete",
        "completed_steps": ["create_profile", "verify_kyc", "v_kyc", "fund_account"],
        "status": "COMPLETE"
    }


def _process_loan(state: SarthiState, user_text: str) -> dict:
    """Process loan application within acquisition flow."""
    lang = state.get("language", "en")
    entities = state.get("extracted_entities", {})
    
    loan_amount = entities.get("amount", 50000)
    purpose = entities.get("purpose", "personal")
    
    # HITL for loans > Rs. 50,000
    if loan_amount > 50000:
        create_audit_artifact(
            event_type="hitl_interrupt",
            session_id=state["session_id"],
            agent_name="acquisition",
            decision={"reason": "high_value_loan", "amount": loan_amount},
            state_snapshot=dict(state)
        )
        
        responses = {
            "en": f"Your loan application for Rs. {loan_amount:,} is being reviewed by an SBI officer. This is required for loans above Rs. 50,000. Please wait.",
            "hi": f"Aapka Rs. {loan_amount:,} ka loan application SBI adhikari ke review mein hai. Rs. 50,000 se zyada ke loans ke liye ye zaroori hai. Kripya pratiksha karein.",
            "mr": f"Tumche Rs. {loan_amount:,} che loan application SBI adhikaryanchya review madhye ahe. Rs. 50,000 peksha jast loans sathi he garajeche ahe. Kripaya pratiksha kara."
        }
        
        return {
            "response_text": responses.get(lang, responses["en"]),
            "interrupted": True,
            "interrupt_reason": "high_value_loan",
            "requires_hitl": True,
            "status": "RUNNING"
        }
    
    # Small loan — auto-approved
    loan_id = f"LN_SBI_2026_{hashlib.sha256(state['session_id'].encode('utf-8')).hexdigest()[:6]}"
    
    responses = {
        "en": f"Loan sanctioned! Loan ID: {loan_id}. Amount: Rs. {loan_amount:,}. Interest rate: 8.5%. EMI details will be sent via SMS.",
        "hi": f"Loan manjur ho gaya! Loan ID: {loan_id}. Rakam: Rs. {loan_amount:,}. Byaj dar: 8.5%. EMI details SMS par bhej diye jayenge.",
        "mr": f"Loan manjur zale! Loan ID: {loan_id}. Rakam: Rs. {loan_amount:,}. Vyaj dar: 8.5%. EMI details SMS var pathavle jatil."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "COMPLETE"
    }


def _default_acquisition_response(state: SarthiState) -> dict:
    """Default response when in acquisition but no specific step matches."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "I'm here to help you open an account or apply for a loan. What would you like to do?",
        "hi": "Main aapka khata kholne ya loan apply karne mein madad kar sakta hoon. Aap kya karna chahenge?",
        "mr": "Mi tumhala khata ugadnyat kiva loan apply karanyat madat karu shakto. Tumhala kay karayche ahe?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "onboarding_step": state.get("onboarding_step", "idle"),
        "status": "RUNNING"
    }


def check_onboarding_status(state: SarthiState) -> str:
    """Conditional edge: check acquisition status and route next.
    Returns: "complete" | "failed" | "interrupted" | "running"
    """
    if state.get("status") == "FAILED":
        return "failed"
    elif state.get("interrupted"):
        return "interrupted"
    elif state.get("status") == "COMPLETE":
        return "complete"
    return "running"  # Loops back to acquisition for multi-step KYC
