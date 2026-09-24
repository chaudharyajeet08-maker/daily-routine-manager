import os
import json
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
import routine_manager as rm

load_dotenv()

st.set_page_config(page_title="Daily Routine Manager", layout="wide", page_icon="🗓️")

# Multi-environment API Key Resolution (optional — app works fine without it, using regex parsing)
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None

client = None
PRIMARY_MODEL = "gemini-3.5-flash-lite"
if api_key:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except Exception:
        client = None

st.title("🗓️ Daily Routine & Task Reminders")
st.caption(
    "Kisi bhi email, timetable, meeting note ya to-do list ka text yahan paste karo — "
    "system usse automatically tasks mein todh kar aapka daily routine bana dega, "
    "aur is tab ko khula rakhne par browser notification bhi bhejega."
)

routine_date = st.date_input("Routine Date", value=datetime.now().date(), key="routine_date")
routine_date_str = routine_date.isoformat()

raw_input = st.text_area(
    "📋 Yahan Paste Karo (Email / Timetable / Meeting / To-Do)",
    height=180,
    placeholder="Example:\n9:30 AM - Physics revision (Rotational Motion)\n2 PM meeting with mentor\nSubmit chemistry assignment by 6pm\n...",
    key="routine_raw_input",
)

use_ai = st.checkbox(
    "🤖 AI se smartly parse karo (agar time explicit na ho to bhi sahi samjhega)",
    value=bool(client),
    disabled=not client,
    key="routine_use_ai",
)
if not client:
    st.caption("ℹ️ AI parsing ke liye `GEMINI_API_KEY` set karo (.env file ya Streamlit secrets mein). Abhi regex-based parsing use ho rahi hai.")

if st.button("➕ Parse & Add to Routine", type="primary", use_container_width=True):
    if not raw_input.strip():
        st.warning("Pehle kuch text paste karo.")
    else:
        with st.spinner("Tasks extract ho rahe hain..."):
            if use_ai and client:
                parsed = rm.parse_tasks_with_ai(raw_input, client, PRIMARY_MODEL)
            else:
                parsed = rm.parse_tasks_with_regex(raw_input)

        if not parsed:
            st.error("Koi task detect nahi hua. Please text thoda clear format mein likho.")
        else:
            rm.add_tasks(routine_date_str, parsed)
            st.success(f"{len(parsed)} tasks aapke {routine_date_str} routine mein add ho gaye!")
            st.rerun()

st.divider()
st.markdown(f"### 📅 Routine for {routine_date_str}")

day_tasks = rm.tasks_for_date(routine_date_str)

if not day_tasks:
    st.info("Is date ke liye abhi koi task nahi hai. Upar text paste karke add karo.")
else:
    priority_colors = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
    for t in day_tasks:
        c1, c2, c3, c4 = st.columns([1, 5, 2, 1])
        with c1:
            st.write(f"**{t['time']}**")
        with c2:
            label = f"~~{t['title']}~~" if t["done"] else t["title"]
            st.write(f"{priority_colors.get(t.get('priority', 'Medium'), '🟡')} {label}")
        with c3:
            new_done = st.checkbox("Done", value=t["done"], key=f"done_{t['id']}")
            if new_done != t["done"]:
                rm.toggle_done(t["id"])
                st.rerun()
        with c4:
            if st.button("🗑️", key=f"del_{t['id']}"):
                rm.delete_task(t["id"])
                st.rerun()

    pending_tasks = [t for t in day_tasks if not t["done"]]
    notif_payload = json.dumps(
        [{"time": t["time"], "title": t["title"]} for t in pending_tasks]
    )
    today_iso = routine_date_str
    components.html(
        f"""
        <div id="notif-status" style="font-family:Arial, sans-serif; font-size:13px; color:#4b5563;"></div>
        <script>
        (function() {{
            const statusEl = document.getElementById("notif-status");
            const tasks = {notif_payload};
            const dateStr = "{today_iso}";

            function scheduleNotifications() {{
                if (!("Notification" in window)) {{
                    statusEl.innerText = "Is browser mein notifications supported nahi hain.";
                    return;
                }}
                if (Notification.permission !== "granted") {{
                    statusEl.innerText = "Notifications allow karne ke liye button dabao.";
                    return;
                }}
                const now = new Date();
                let scheduled = 0;
                tasks.forEach(function(t) {{
                    const [h, m] = t.time.split(":").map(Number);
                    const target = new Date(dateStr + "T00:00:00");
                    target.setHours(h, m, 0, 0);
                    const delay = target.getTime() - now.getTime();
                    if (delay > 0 && delay < 24 * 60 * 60 * 1000) {{
                        setTimeout(function() {{
                            new Notification("⏰ Task Reminder", {{ body: t.title }});
                        }}, delay);
                        scheduled += 1;
                    }}
                }});
                statusEl.innerText = scheduled + " reminders is tab ke khule rehte hue schedule ho gaye.";
            }}

            if ("Notification" in window && Notification.permission === "default") {{
                const btn = document.createElement("button");
                btn.innerText = "🔔 Enable Browser Notifications";
                btn.style = "background:#1d4ed8;color:white;border:none;padding:8px 16px;border-radius:4px;font-weight:600;cursor:pointer;font-family:Arial,sans-serif;font-size:13px;";
                btn.onclick = function() {{
                    Notification.requestPermission().then(function() {{
                        scheduleNotifications();
                    }});
                }};
                statusEl.appendChild(btn);
            }} else {{
                scheduleNotifications();
            }}
        }})();
        </script>
        """,
        height=60,
    )
    st.caption(
        "⚠️ Note: Browser notifications tabhi aayengi jab yeh tab khula ho. Agar tumhe tab band karne "
        "ke baad bhi reminder chahiye, to email/SMS/push service integrate karna padega."
    )
