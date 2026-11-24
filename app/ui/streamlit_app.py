"""Clinic Front-Desk AI — professional chat and patient appointment dashboard."""

import asyncio
import sys

import httpx
from pathlib import Path

import streamlit as st

# Allow imports when Streamlit starts from the project directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.bedrock_mcp_agent import ask_agent

st.set_page_config(
    page_title="Clinic Front-Desk AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# This HTML/CSS is static. Never inject user questions into unsafe HTML.
st.markdown(
    """
<style>
:root {--navy:#142e3b;--teal:#137b78;--muted:#647782;--paper:#faf9f5;}
[data-testid="stAppViewContainer"] {background:var(--paper);}
[data-testid="stHeader"] {background:rgba(250,249,245,.95);}
.block-container {max-width:1240px;padding-top:2rem;padding-bottom:3rem;}
[data-testid="stSidebar"] {background:linear-gradient(160deg,#102d40,#12494c);}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] .stMarkdown {color:#f1f8f8!important;}
[data-testid="stSidebar"] hr {border-color:#44636b;}
[data-testid="stSidebar"] button {border-radius:12px!important;}
.brand {display:flex;gap:12px;align-items:center;margin:8px 0 18px;}
.brand-symbol {display:flex;align-items:center;justify-content:center;
 width:48px;height:48px;border-radius:14px;background:#d6f3ea;
 color:#106c65;font-size:26px;font-weight:800;}
.brand-name {font-size:18px;font-weight:750;color:white;line-height:1.2;}
.brand-sub {font-size:12px;color:#b6d5d4;margin-top:4px;}
.side-label {font-size:11px;font-weight:750;letter-spacing:1.5px;
 text-transform:uppercase;color:#b5d9d2;margin:10px 0 12px;}
.side-item {font-size:13px;color:#e6f1f1;line-height:2.25;}
.side-note {font-size:12px;color:#c5dddc;line-height:1.7;}
.hero {border-radius:22px;padding:32px 36px;
 background:linear-gradient(120deg,#173747,#0f6563);color:white;
 box-shadow:0 10px 28px rgba(17,55,61,.12);margin-bottom:24px;}
.hero .eyebrow {font-size:11px;font-weight:750;letter-spacing:2px;color:#ade8d9;}
.hero h1 {font-size:clamp(27px,3vw,39px)!important;line-height:1.18;
 font-weight:780;color:white!important;margin:12px 0;}
.hero p {font-size:15px;color:#e0f0ee;line-height:1.7;max-width:740px;}
.pill {display:inline-block;border:1px solid #6b9996;border-radius:30px;
 padding:6px 11px;font-size:12px;color:#eefaf6;margin:7px 7px 0 0;}
.section-title {font-size:19px;font-weight:760;color:var(--navy);margin:6px 0 3px;}
.section-sub {font-size:13px;color:var(--muted);margin-bottom:16px;}
.feature {border:1px solid #e1e9e7;border-radius:13px;background:#fff;
 padding:14px 16px;margin-bottom:10px;}
.feature strong {color:#23414a;font-size:14px;}
.feature p {color:var(--muted);font-size:12px;margin:5px 0 0;line-height:1.55;}
.notice {background:#eef6f1;border:1px solid #d9e8df;border-radius:13px;
 color:#45665b;padding:13px 15px;font-size:12px;line-height:1.65;margin-top:12px;}
[data-testid="stChatMessage"] {background:white;border:1px solid #e2eae8;
 border-radius:15px;padding:10px 13px;margin-bottom:9px;}
.stButton button {border-radius:12px;min-height:45px;font-weight:600;
 background:white;border-color:#dce8e6;color:#24414a;}
.stButton button:hover {border-color:#83c6bb;color:#106d68;background:#f0faf7;}
.footer {font-size:12px;color:#88969a;text-align:center;margin-top:35px;}
</style>
""",
    unsafe_allow_html=True,
)

EMERGENCY_TERMS = (
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
    "unconscious", "severe bleeding", "heart attack", "signs of stroke",
    "suspected stroke", "severe allergic reaction",
)
EMERGENCY_RESPONSE = (
    "If this may be a medical emergency in the UK, **call 999 immediately**. "
    "This chat cannot assess or treat emergencies."
)

TOOL_LABELS = {
    "list_clinic_doctors": "Doctor directory",
    "preview_clinic_appointment": "Appointment availability",
    "answer_clinic_policy": "Clinic policies (RAG)",
    "predict_demo_no_show_risk": "Synthetic no-show ML",
}

SUGGESTED_QUESTIONS = [
    ("👩‍⚕️ Find clinic doctors", "Which doctors are registered at the clinic?"),
    ("📋 Cancellation policy", "What is the clinic cancellation policy?"),
    ("📈 Synthetic ML demonstration", "Run a fictional synthetic no-show prediction demo."),
]


def get_answer(question: str):
    """Use the cloud-backed agent; never log messages or private data."""
    if any(term in question.casefold() for term in EMERGENCY_TERMS):
        return EMERGENCY_RESPONSE, []

    try:
        answer, tools = asyncio.run(ask_agent(question))
        if not isinstance(answer, str) or not answer.strip():
            return "I could not retrieve an answer. Please try again.", []
        return answer, tools
    except Exception as exc:
        print("Clinic assistant error type:", type(exc).__name__)
        return "The clinic assistant is temporarily unavailable. Please try again.", []



def fetch_my_appointments(session_id: str):
    """Fetch only this Cognito session's appointments via FastAPI."""
    try:
        response = httpx.get(
            "http://localhost:8000/auth/appointments",
            cookies={"clinic_demo_session": session_id},
            timeout=15.0,
            trust_env=False,
        )
        if response.status_code == 401:
            return None, "Session expired. Please sign in again."
        if response.status_code != 200:
            return None, "Clinic appointments are temporarily unavailable."

        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(
            payload.get("appointments"), list
        ):
            return None, "The appointments response was not recognised."

        return payload, None
    except (httpx.HTTPError, ValueError):
        return None, "Could not contact the clinic authentication service."


def display_date(value):
    """Format a JSON date for display without assuming data shape."""
    from datetime import date
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%a %d %b %Y")
    except (TypeError, ValueError):
        return str(value or "Date unavailable")


def display_time(value):
    text = str(value or "")
    return text[:5] if len(text) >= 5 else "Time unavailable"




def _backend_get(session_id: str, route: str):
    """Call only our local authenticated FastAPI backend."""
    try:
        response = httpx.get(
            "http://localhost:8000" + route,
            cookies={"clinic_demo_session": session_id},
            timeout=25.0,
            trust_env=False,
        )
        if response.status_code == 401:
            raise RuntimeError("Your session has expired. Please sign in again.")
        if response.status_code != 200:
            raise RuntimeError("Clinic information is temporarily unavailable.")
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Could not reach the clinic authentication service.") from exc


def _backend_post(session_id: str, route: str, body: dict | None = None):
    """State changes require the session's CSRF header and an explicit UI click."""
    csrf_data = _backend_get(session_id, "/auth/csrf")
    csrf = csrf_data.get("csrf_token")
    if not isinstance(csrf, str) or not csrf:
        raise RuntimeError("Unable to verify your session. Please sign in again.")

    try:
        response = httpx.post(
            "http://localhost:8000" + route,
            json=body if body is not None else {},
            cookies={"clinic_demo_session": session_id},
            headers={"X-CSRF-Token": csrf},
            timeout=45.0,
            trust_env=False,
        )
        if response.status_code == 401:
            raise RuntimeError("Your session has expired. Please sign in again.")
        if response.status_code == 403:
            raise RuntimeError("Request verification failed. Refresh the page.")
        if response.status_code != 200:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            if response.status_code == 409 and isinstance(detail, str):
                raise RuntimeError(detail)
            raise RuntimeError("Appointment action failed. Please try again.")
        return response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError("Could not reach the clinic booking service.") from exc


def _future_appointment(record: dict) -> bool:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        time_text = str(record.get("time", ""))[:8]
        date_text = str(record.get("date", ""))[:10]
        start = datetime.fromisoformat(f"{date_text}T{time_text}")
        local_now = datetime.now(ZoneInfo("Europe/London")).replace(tzinfo=None)
        return start > local_now and record.get("status") == "booked"
    except (ValueError, TypeError):
        return False


def _show_intent(heading: str, rows: list[tuple[str, str]]):
    with st.container(border=True):
        st.markdown("#### " + heading)
        for label, value in rows:
            st.write(f"**{label}:** {value}")
        st.caption("This request expires after 10 minutes. The slot is not held until confirmed.")


def _notify_and_refresh(message: str):
    st.session_state["appointment_flash"] = message
    for name in ("booking_intent", "cancellation_intent", "reschedule_intent"):
        st.session_state.pop(name, None)
    st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = []

# All sidebar calls must be inside this block with matching indentation.
with st.sidebar:
    st.markdown(
        """
        <div class="brand">
          <div class="brand-symbol">✚</div>
          <div><div class="brand-name">Clinic Front-Desk AI</div>
          <div class="brand-sub">Digital patient services</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("DEMONSTRATION ENVIRONMENT")
    st.divider()
    st.markdown('<div class="side-label">Available capabilities</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="side-item">◈ &nbsp; AI-powered clinic chat</div>
        <div class="side-item">◈ &nbsp; Doctor &amp; slot information</div>
        <div class="side-item">◈ &nbsp; Clinic policies &amp; FAQs</div>
        <div class="side-item">◈ &nbsp; Synthetic ML demonstration</div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown('<div class="side-label">Conversation</div>', unsafe_allow_html=True)
    if st.button("↻ Start a new conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.markdown('<div class="side-label">Account</div>', unsafe_allow_html=True)

    # Streamlit reads the opaque HttpOnly cookie from the initial browser
    # request. The access token stays only in the trusted FastAPI backend.
    session_id = st.context.cookies.get("clinic_demo_session")
    signed_in = None
    if session_id:
        try:
            response = httpx.get(
                "http://localhost:8000/auth/me",
                cookies={"clinic_demo_session": session_id},
                timeout=5.0,
                trust_env=False,
            )
            if response.status_code == 200:
                signed_in = response.json()
        except (httpx.HTTPError, ValueError):
            signed_in = None

    if signed_in and signed_in.get("authenticated"):
        st.success("Signed in with AWS Cognito")
        st.caption(f"Linked demo patient: {signed_in['patient_id']}")
        st.link_button(
            "Sign out",
            "http://localhost:8000/auth/logout",
            use_container_width=True,
        )
    else:
        st.markdown(
            '<div class="side-note">Sign in to access your linked '
            'demo patient account. Appointment management is next.</div>',
            unsafe_allow_html=True,
        )
        st.link_button(
            "Sign in with AWS Cognito",
            "http://localhost:8000/auth/start",
            use_container_width=True,
        )
        st.caption("Public chat mode: no patient records are shown.")
    st.divider()
    st.markdown(
        '<div class="side-note">Do not enter real patient details, '
        'passwords or access tokens.</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">YOUR CLINIC · DIGITAL SUPPORT</div>
      <h1>Care starts with a conversation.</h1>
      <p>Find doctors, check clinic information and get clear answers.
      Powered by your AWS-connected clinic knowledge and AI tools.</p>
      <span class="pill">Clinic information</span>
      <span class="pill">Doctor directory</span>
      <span class="pill">Appointment availability</span>
      <span class="pill">AI-assisted support</span>
    </section>
    """,
    unsafe_allow_html=True,
)

chat_tab, appointments_tab = st.tabs(
    ["💬 AI Assistant", "📅 My Appointments"]
)

with chat_tab:
    left, right = st.columns([2.1, 1], gap="large")
    selected_prompt = None

    with right:
        st.markdown(
            '<div class="section-title">How can we help?</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-sub">Start with a common request</div>',
            unsafe_allow_html=True,
        )

        for index, (label, question) in enumerate(SUGGESTED_QUESTIONS):
            if st.button(label, key=f"quick_{index}", use_container_width=True):
                selected_prompt = question

        st.markdown("#### Your assistant can help with")
        st.markdown(
            """
            <div class="feature"><strong>🩺 Clinic directory</strong>
            <p>Find doctors and check appointment slots.</p></div>
            <div class="feature"><strong>📚 Policies and FAQs</strong>
            <p>Answers grounded in the clinic's demo knowledge base.</p></div>
            <div class="feature"><strong>📊 AI demonstration</strong>
            <p>Try fictional no-show predictions using AWS Lambda.</p></div>
            <div class="notice"><strong>Important</strong><br>
            Synthetic-data demonstration only. Not medical advice.
            For a UK emergency, call 999.</div>
            """,
            unsafe_allow_html=True,
        )

    with left:
        st.markdown(
            '<div class="section-title">AI Assistant</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-sub">Ask about clinic services</div>',
            unsafe_allow_html=True,
        )

        if not st.session_state.messages:
            with st.chat_message("assistant", avatar="🏥"):
                st.markdown(
                    "**Welcome to Clinic Front-Desk AI.**\n\n"
                    "I can help with the doctor directory, clinic policies, "
                    "appointment availability and fictional ML demonstrations."
                )

        for message in st.session_state.messages:
            avatar = "🏥" if message["role"] == "assistant" else "👤"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])
                if message.get("tools"):
                    labels = [
                        TOOL_LABELS.get(name, name)
                        for name in message["tools"]
                    ]
                    st.caption("Sources & tools: " + ", ".join(labels))

        typed_prompt = st.chat_input(
            "Type your clinic question here...", max_chars=2000
        )
        prompt = typed_prompt or selected_prompt

        if prompt:
            st.session_state.messages.append({
                "role": "user", "content": prompt, "tools": []
            })
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

            with st.chat_message("assistant", avatar="🏥"):
                with st.spinner("Checking clinic information..."):
                    answer, used_tools = get_answer(prompt)
                st.markdown(answer)
                if used_tools:
                    labels = [
                        TOOL_LABELS.get(name, name)
                        for name in used_tools
                    ]
                    st.caption("Sources & tools: " + ", ".join(labels))

            st.session_state.messages.append({
                "role": "assistant", "content": answer, "tools": used_tools
            })

with appointments_tab:
    st.markdown("### My appointments")
    st.caption(
        "Book, cancel or reschedule appointments using your authenticated "
        "synthetic patient account. All changes are saved in AWS RDS."
    )

    if not signed_in or not signed_in.get("authenticated"):
        st.info("Sign in with AWS Cognito to manage your appointments.")
        st.link_button("Sign in with AWS Cognito", "http://localhost:8000/auth/start")
    else:
        # Pending previews belong only to the current session.
        if st.session_state.get("patient_session") != session_id:
            st.session_state["patient_session"] = session_id
            for key in ("booking_intent", "cancellation_intent", "reschedule_intent"):
                st.session_state.pop(key, None)

        header_left, header_right = st.columns([3, 1])
        with header_left:
            st.markdown("**Authenticated patient dashboard**")
            st.caption("Linked synthetic patient: " + str(signed_in["patient_id"]))
        with header_right:
            if st.button("Refresh appointments", key="refresh_patient_appointments"):
                st.rerun()

        if "appointment_flash" in st.session_state:
            st.success(st.session_state.pop("appointment_flash"))

        data, appointments_error = fetch_my_appointments(session_id)
        try:
            slots_data = _backend_get(session_id, "/auth/available-slots")
            slots_error = None
        except RuntimeError as exc:
            slots_data = {"slots": []}
            slots_error = str(exc)

        appointments = data.get("appointments", []) if data else []
        available_slots = slots_data.get("slots", [])
        future = [a for a in appointments if _future_appointment(a)]

        if appointments_error:
            st.error(appointments_error)
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Active appointments", len(appointments))
            col2.metric("Upcoming appointments", len(future))
            col3.metric("Available future slots", len(available_slots))

            if not appointments:
                st.info("You have no active appointments. Use Book to create one.")
            else:
                st.markdown("#### Your appointments")
                for item in appointments:
                    with st.container(border=True):
                        title_col, status_col = st.columns([3, 1])
                        with title_col:
                            st.markdown("**" + str(item.get("doctor_name", "Clinic doctor")) + "**")
                        with status_col:
                            st.caption("Status: " + str(item.get("status", "booked")))
                        st.write(
                            f"{display_date(item.get('date'))} · "
                            f"{display_time(item.get('time'))} · "
                            f"Reference {item.get('appointment_id', 'N/A')}"
                        )

            st.divider()
            book_tab, cancel_tab, move_tab = st.tabs(
                ["➕ Book", "✖ Cancel", "🔁 Reschedule"]
            )

            # ---------------- Book ----------------
            with book_tab:
                st.markdown("#### Book a new appointment")
                st.caption("Choose a future available slot, then review and confirm.")
                if slots_error:
                    st.warning(slots_error)
                elif not available_slots:
                    st.info("No future appointment slots are currently available.")
                else:
                    lookup = {slot["slot_id"]: slot for slot in available_slots}
                    slot_ids = list(lookup)
                    selected_slot = st.selectbox(
                        "Choose doctor and appointment time",
                        slot_ids,
                        format_func=lambda sid: (
                            f"{lookup[sid]['doctor_name']} · "
                            f"{display_date(lookup[sid]['date'])} "
                            f"{lookup[sid]['time']} · {sid}"
                        ),
                        key="book_slot_selector",
                    )
                    if st.button("Review booking", key="book_preview", use_container_width=True):
                        try:
                            st.session_state["booking_intent"] = _backend_post(
                                session_id,
                                "/auth/booking-intents",
                                {"slot_id": selected_slot},
                            )
                        except RuntimeError as exc:
                            st.error(str(exc))

                    intent = st.session_state.get("booking_intent")
                    if intent and intent.get("preview", {}).get("slot_id") == selected_slot:
                        p = intent["preview"]
                        _show_intent("Review booking", [
                            ("Doctor", str(p.get("doctor_name", ""))),
                            ("Date", str(p.get("date", ""))),
                            ("Time", str(p.get("time", ""))),
                            ("Request expires", str(intent.get("expires_at", ""))),
                        ])
                        reviewed = st.checkbox(
                            "I have reviewed this booking and want to proceed",
                            key="book_ack_" + intent["intent_id"],
                        )
                        if st.button(
                            "Confirm booking",
                            type="primary",
                            disabled=not reviewed,
                            key="book_confirm_" + intent["intent_id"],
                        ):
                            try:
                                result = _backend_post(
                                    session_id,
                                    "/auth/booking-intents/" + intent["intent_id"] + "/confirm",
                                )
                                _notify_and_refresh(
                                    "Booking confirmed. Reference: " + result["appointment_id"]
                                )
                            except RuntimeError as exc:
                                st.error(str(exc))

            # ---------------- Cancel ----------------
            with cancel_tab:
                st.markdown("#### Cancel an appointment")
                st.caption("You can only cancel your own future booked appointments.")
                if not future:
                    st.info("No upcoming appointments available for cancellation.")
                else:
                    appointment_map = {a["appointment_id"]: a for a in future}
                    selected_appointment = st.selectbox(
                        "Appointment to cancel",
                        list(appointment_map),
                        format_func=lambda aid: (
                            f"{appointment_map[aid].get('doctor_name', 'Doctor')} · "
                            f"{display_date(appointment_map[aid].get('date'))} "
                            f"{display_time(appointment_map[aid].get('time'))} · {aid}"
                        ),
                        key="cancel_appointment_selector",
                    )
                    if st.button("Review cancellation", key="cancel_preview", use_container_width=True):
                        try:
                            st.session_state["cancellation_intent"] = _backend_post(
                                session_id,
                                "/auth/cancellation-intents",
                                {"appointment_id": selected_appointment},
                            )
                        except RuntimeError as exc:
                            st.error(str(exc))

                    intent = st.session_state.get("cancellation_intent")
                    if intent and intent.get("appointment_id") == selected_appointment:
                        _show_intent("Review cancellation", [
                            ("Appointment", str(intent.get("appointment_id", ""))),
                            ("Doctor", str(intent.get("doctor_name", ""))),
                            ("Date", str(intent.get("date", ""))),
                            ("Time", str(intent.get("time", ""))),
                        ])
                        reviewed = st.checkbox(
                            "I understand this appointment will be cancelled",
                            key="cancel_ack_" + intent["intent_id"],
                        )
                        if st.button(
                            "Confirm cancellation",
                            type="primary",
                            disabled=not reviewed,
                            key="cancel_confirm_" + intent["intent_id"],
                        ):
                            try:
                                _backend_post(
                                    session_id,
                                    "/auth/cancellation-intents/" + intent["intent_id"] + "/confirm",
                                )
                                _notify_and_refresh("Appointment cancelled successfully.")
                            except RuntimeError as exc:
                                st.error(str(exc))

            # ---------------- Reschedule ----------------
            with move_tab:
                st.markdown("#### Reschedule an appointment")
                st.caption("Your current slot is released only if the new slot is booked.")
                if slots_error:
                    st.warning(slots_error)
                elif not future:
                    st.info("No upcoming appointments to reschedule.")
                elif not available_slots:
                    st.info("No alternative future slots are currently available.")
                else:
                    appointment_map = {a["appointment_id"]: a for a in future}
                    available_map = {s["slot_id"]: s for s in available_slots}
                    move_appointment = st.selectbox(
                        "Appointment to change",
                        list(appointment_map),
                        format_func=lambda aid: (
                            f"{appointment_map[aid].get('doctor_name', 'Doctor')} · "
                            f"{display_date(appointment_map[aid].get('date'))} "
                            f"{display_time(appointment_map[aid].get('time'))} · {aid}"
                        ),
                        key="move_appointment_selector",
                    )
                    move_slot = st.selectbox(
                        "New appointment time",
                        list(available_map),
                        format_func=lambda sid: (
                            f"{available_map[sid]['doctor_name']} · "
                            f"{display_date(available_map[sid]['date'])} "
                            f"{available_map[sid]['time']} · {sid}"
                        ),
                        key="move_new_slot_selector",
                    )
                    if st.button("Review rescheduling", key="move_preview", use_container_width=True):
                        try:
                            st.session_state["reschedule_intent"] = _backend_post(
                                session_id,
                                "/auth/reschedule-intents",
                                {"appointment_id": move_appointment, "new_slot_id": move_slot},
                            )
                        except RuntimeError as exc:
                            st.error(str(exc))

                    intent = st.session_state.get("reschedule_intent")
                    if (
                        intent
                        and intent.get("appointment_id") == move_appointment
                        and intent.get("new_appointment", {}).get("slot_id") == move_slot
                    ):
                        proposed = intent["new_appointment"]
                        _show_intent("Review rescheduling", [
                            ("Old appointment", str(intent.get("old_date", "")) + " " + str(intent.get("old_time", ""))),
                            ("New appointment", str(proposed.get("date", "")) + " " + str(proposed.get("time", ""))),
                            ("New doctor", str(proposed.get("doctor_name", ""))),
                        ])
                        reviewed = st.checkbox(
                            "I approve moving this appointment to the new time",
                            key="move_ack_" + intent["intent_id"],
                        )
                        if st.button(
                            "Confirm rescheduling",
                            type="primary",
                            disabled=not reviewed,
                            key="move_confirm_" + intent["intent_id"],
                        ):
                            try:
                                result = _backend_post(
                                    session_id,
                                    "/auth/reschedule-intents/" + intent["intent_id"] + "/confirm",
                                )
                                _notify_and_refresh(
                                    "Appointment rescheduled. Reference: " + result["appointment_id"]
                                )
                            except RuntimeError as exc:
                                st.error(str(exc))

            st.caption(
                "Synthetic demonstration only. Appointment changes are performed "
                "by the authenticated backend, not by the AI agent."
            )

st.markdown(
    '<div class="footer">Clinic Front-Desk AI · Demonstration environment · '
    'AWS Bedrock, MCP, RAG and synthetic ML</div>',
    unsafe_allow_html=True,
)
