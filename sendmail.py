import streamlit as st
import pandas as pd
import os, pickle, base64, logging
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from db import get_db, to_object_id, now
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
from bson import ObjectId
from streamlit_option_menu import option_menu

# APScheduler Scheduler
scheduler = BackgroundScheduler()

if not scheduler.running:
    scheduler.start()

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_user_details(user_id):
    client, db = get_db()
    if db is None:
        return None
    try:
        # try ObjectId
        oid = to_object_id(user_id)
        query = {}
        if oid:
            query = {"_id": oid}
        else:
            # maybe user passed their username or string id
            query = {"$or":[{"_id":user_id},{"username":user_id},{"id":user_id}]}
        user = db.users.find_one(query)
        if user:
            return {"user_id": str(user.get("_id")), "username": user.get("username"), "is_enabled": bool(user.get("is_enabled", False))}
        return None
    except Exception as e:
        st.error(f"Error fetching user details: {e}")
        return None
    finally:
        client.close()

def authenticate_gmail_api():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def log_email_stats(user_id, to_emails, cc, bcc):
    client, db = get_db()
    if db is None:
        return
    try:
        unique_emails = list({e.strip().lower() for e in to_emails.split(',') if e.strip()}) if isinstance(to_emails, str) else []
        uniqcc = list({e.strip().lower() for e in cc.split(',') if e.strip()}) if isinstance(cc, str) else []
        uniqbcc = list({e.strip().lower() for e in bcc.split(',') if isinstance(bcc, str)}) if isinstance(bcc, str) else []
        num_sent = len(unique_emails) + len(uniqcc) + len(uniqbcc)
        # Upsert a stats doc per user (increment)
        query = {"user_id": user_id}
        update = {"$inc": {"sent": num_sent, "delivered": num_sent, "inbox": num_sent}, "$setOnInsert": {"timestamp": now()}}
        db.email_stats.update_one(query, update, upsert=True)
        st.write(f"Unique Recipients: {unique_emails}, Count: {num_sent}")
    except Exception as e:
        st.error(f"Error logging email stats: {e}")
    finally:
        client.close()

def send_email(service, from_email, to_emails, subject, body, user_id, cc=None, bcc=None):
    if not user_id:
        st.error("Invalid user id")
        return None
    try:
        message = MIMEMultipart()
        message["From"] = from_email
        message["To"] = to_emails
        message["Subject"] = subject
        if cc:
            message["Cc"] = cc
        if bcc:
            message["Bcc"] = bcc
        message.attach(MIMEText(body, "plain"))
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        # Log statistics
        log_email_stats(user_id, to_emails, cc or "", bcc or "")
        return send_message
    except HttpError as e:
        st.error(f"An error occurred sending the email: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

def send_scheduled_email(email_id):
    client, db = get_db()
    if db is None:
        logger.error("No DB")
        return
    try:
        doc = db.scheduled_emails.find_one({"_id": to_object_id(email_id)})
        if not doc:
            logger.warning(f"No pending email found for ID: {email_id}")
            return
        if doc.get("status") != "Pending":
            logger.info("Email not pending")
            return
        user_details = fetch_user_details(doc.get("user_id"))
        if not user_details:
            logger.error("Sender details missing")
            return
        from_address = user_details.get("username")
        service = authenticate_gmail_api()
        result = send_email(service, from_address, doc.get("to_emails"), doc.get("subject"), doc.get("body"), doc.get("user_id"), doc.get("cc"), doc.get("bcc"))
        if result:
            db.scheduled_emails.update_one({"_id": doc["_id"]}, {"$set":{"status":"Sent"}})
            logger.info(f"Email ID {email_id} sent successfully.")
        else:
            logger.error(f"Failed to send email ID {email_id}.")
    except Exception as e:
        logger.error(f"Error sending scheduled email: {e}")
    finally:
        client.close()

def schedule_email_with_apscheduler(user_id, to_emails, subject, body, schedule_time, cc=None, bcc=None):
    client, db = get_db()
    if db is None:
        st.error("DB connection failed")
        return
    try:
        cc_str = ",".join(cc) if isinstance(cc, list) else (cc or "")
        bcc_str = ",".join(bcc) if isinstance(bcc, list) else (bcc or "")
        doc = {
            "user_id": user_id,
            "to_emails": to_emails,
            "subject": subject,
            "body": body,
            "cc": cc_str,
            "bcc": bcc_str,
            "schedule_time": schedule_time,
            "status": "Pending",
            "created_at": now()
        }
        res = db.scheduled_emails.insert_one(doc)
        email_id = str(res.inserted_id)
        trigger = DateTrigger(run_date=schedule_time)
        scheduler.add_job(send_scheduled_email, trigger, args=[email_id], id=f"email_{email_id}", misfire_grace_time=3600)
        st.success("Email scheduled successfully!")
    except Exception as e:
        st.error(f"Error scheduling email: {e}")
    finally:
        client.close()

def generate_scheduled_email_reports():
    schcss = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Delius+Unicase:wght@400;700&family=DynaPuff:wght@400..700&family=Funnel+Sans:ital,wght@0,300..800;1,300..800&display=swap');
                
        [data-testid="stApp"]{
        background-color:white;
        color:black;}
        h1{
        font-family: 'Delius Unicase', cursive;}
        h3{
        font-family: 'DanPuff', sans-serif;}
        [data-testid="stSidebarContent"]{
        background-color:#4f6367;}

        [data-testid="stHeader"]{
        background-color:black;
        }
        [data-testid="stBaseButton-secondary"]{
        border:2px solid black;
        }
        [data-testid="stSidebarUserContent"]{
        border-radius:5px;}

        [class="st-bt st-bu st-bv st-da st-bx st-by st-c5 st-bz st-c7"]{
        border:2px solid black;
        border-radius:5px;}
        
        [data-testid="stDataFrame"]{
        width:700px;
         border:2px solid black;
        border-radius:5px;}
        text-align:center;
        }
        [class="marks"]{
        border:2px solid black;
        border-radius:5px;}
        .st-bt st-bu st-bv st-da st-bx st-by st-c5 st-bz st-c7{
        background-color:white;
        }
        [data-testid="stTextInputRootElement"]{
        border:2px solid black;
        background-color:white;}
        [class="st-ah"]{
        border:2px solid black;
        background-color:white;}
       
        </style>
        """
    st.markdown(schcss,unsafe_allow_html=True)
    st.title("Scheduled Email Reports")
    st.markdown("Manage your scheduled emails below.")
    
    client, db = get_db()
    if db is None:
        st.error("Database connection failed.")
        return

    try:
        emails = list(db.scheduled_emails.find({}, {"_id": 1, "user_id": 1, "to_emails": 1, "subject": 1,
                                                    "schedule_time": 1, "status": 1, "created_at": 1}))
        if emails:
            df = pd.DataFrame([
                {
                    "ID": str(e["_id"]),
                    "User ID": e.get("user_id", ""),
                    "To": e.get("to_emails", ""),
                    "Subject": e.get("subject", ""),
                    "Schedule Time": e.get("schedule_time", ""),
                    "Status": e.get("status", ""),
                    "Created At": e.get("created_at", "")
                }
                for e in emails
            ])
            st.dataframe(df)
            # Bar chart by status
            if "Status" in df.columns:
                st.bar_chart(df.groupby("Status")["ID"].count())
        else:
            st.warning("No scheduled emails found.")

        # Delete scheduled email
        st.subheader("Delete Scheduled Email by ID")
        email_id_to_delete = st.text_input("Enter the Email ID to delete")
        if st.button("Delete Email"):
            if not email_id_to_delete:
                st.warning("Please enter an email ID to delete.")
            else:
                try:
                    oid = to_object_id(email_id_to_delete)
                    res = db.scheduled_emails.delete_one({"_id": oid})
                    if res.deleted_count:
                        st.success(f"Email with ID {email_id_to_delete} deleted successfully.")
                    else:
                        st.warning(f"No email found with ID {email_id_to_delete}.")
                except Exception as e:
                    st.error(f"Error deleting email: {e}")
    except Exception as e:
        st.error(f"Error fetching scheduled email reports: {e}")
    finally:
        client.close()

   


#Function to display email dashboard
def email_dashboard():
    sendcss = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Delius+Unicase:wght@400;700&family=DynaPuff:wght@400..700&family=Funnel+Sans:ital,wght@0,300..800;1,300..800&display=swap');
                
        [data-testid="stApp"]{
        background-color:white;
        color:black;}
        [data-testid="stBaseButton-secondary"]{
        border:2px solid black;
        }
        h1{
        font-family: 'Delius Unicase', cursive;}
        h3{
        font-family: 'DanPuff', sans-serif;}
        [data-testid="stSidebarContent"]{
        background-color:#4f6367;}

        [data-testid="stHeader"]{
        background-color:black;
        }
        [data-testid="stSidebarUserContent"]{
        border-radius:5px;}
        [class="st-bt st-bu st-bv st-da st-bx st-by st-c5 st-bz st-c7"]{
        border:2px solid black;
        border-radius:5px;}
        [class="st-bt st-bu st-bv st-bw st-bx st-by st-c5 st-bz st-c7"]{
        border:2px solid black;
        border-radius:5px;
        }
        [class="st-c7"]{
        border:2px solid black;
        border-radius:5px;
        }
        [data-testid="stTextAreaRootElement"]{
        border:2px solid black;
        border-radius:5px;
        } 
        [data-testid="stFileUploaderDropzone"]{
        border:2px solid black;
        border-radius:5px;
        }
        [data-testid="stDataFrame"]{
        width:700px;
         border:2px solid black;
        border-radius:5px;}
        text-align:center;
        }
        [class="marks"]{
        border:2px solid black;
        border-radius:5px;}
        .st-bt st-bu st-bv st-da st-bx st-by st-c5 st-bz st-c7{
        background-color:white;
        }
        [data-testid="stTextInputRootElement"]{
        border:2px solid black;
        background-color:white;}
       
        </style>
        """
    st.markdown(sendcss,unsafe_allow_html=True)
    st.title("Email Dashboard")

    # Use Streamlit session state to keep track of fetched user details
    if 'user_details' not in st.session_state:
        st.session_state['user_details'] = None

    # Always display Compose Email Form
    st.subheader("Compose Email")

    # Input for User ID
    user_id = st.text_input("Enter User ID to fetch details", key="userid")
    user_details = st.session_state.get('user_details')

    # Fetch and display user details when button is clicked
    if st.button("Fetch User Details"):
        if user_id:
            user_details = fetch_user_details(user_id)
            if user_details:
                if user_details.get('is_enabled') == 0:
                    st.warning("This user is not enabled for sending emails.")
                    st.session_state['user_details'] = None  # Disable further processing
                else:
                    st.session_state['user_details'] = user_details
                    st.success(f"Fetched details for user: {user_details['username']}")
                    st.write(f"**Email Address (From):** {user_details['username']}")
                    st.write(f"**User ID:** {user_details['user_id']}")  # Display the fetched user ID
            else:
                st.error("User not found.")
        else:
            st.warning("Please enter a valid User ID.")

    # Ensure user details are available in session state
    user_details = st.session_state['user_details']
    if user_details:
        from_address = user_details['username']
        user_id = user_details['user_id']

        # CSV Upload Sections for To, CC, and BCC
        st.subheader("Upload Contacts")
        
        # To Address Upload
        st.markdown("### To Address")
    
        to_addresses = st.text_input("To")

        # CC Address Upload
        st.markdown("### CC Address")

        cc_uploaded_file = st.file_uploader("Choose a CSV file for CC", type=["csv"], key="cc_upload")
        cc_addresses = []
        if cc_uploaded_file:
            try:
                cc_df = pd.read_csv(cc_uploaded_file)
                if 'username' in cc_df.columns:
                    cc_addresses = cc_df['username'].tolist()
                    st.write("CC Addresses:")
                    st.dataframe(cc_df)
                else:
                    st.error("The CSV file must contain an 'username' column.")
            except Exception as e:
                st.error(f"Error reading CC CSV file: {e}")
        else:
            cc_addresses = st.text_input("Cc")

        # BCC Address Upload
        st.markdown("### BCC Address")
        bcc_uploaded_file = st.file_uploader("Choose a CSV file for BCC", type=["csv"], key="bcc_upload")
        bcc_addresses = []
        if bcc_uploaded_file:
            try:
                bcc_df = pd.read_csv(bcc_uploaded_file)
                if 'username' in bcc_df.columns:
                    bcc_addresses = bcc_df['username'].tolist()
                    st.write("BCC Addresses:")
                    st.dataframe(bcc_df)
                else:
                    st.error("The CSV file must contain an 'username' column.")
            except Exception as e:
                st.error(f"Error reading BCC CSV file: {e}")
        else:
            bcc_addresses = st.text_input("Bcc")
        
         #Manual Inputs for Subject, Body, and Signature
        subject = st.text_input(
            "Subject", 
            value=st.session_state.get('selected_subject', '')  # Pre-load if a template is selected
        )

        # Template dropdown (Mongo)
        client, db = get_db()
        body = ""
        if db is not None:

            try:
                templates = list(
                    db.templates.find(
                        {"$or": [{"user_id": user_id}, {"superuser": True}]},
                        {"template_name": 1, "template_content": 1, "_id": 0},
                    )
                )
                if templates:
                    template_dict = {t["template_name"]: t["template_content"] for t in templates}
                    selected_template = st.selectbox("Choose Template", ["Select"] + list(template_dict.keys()))
                    if selected_template != "Select":
                        content = template_dict[selected_template]
                        st.markdown(content, unsafe_allow_html=True)
                        body = st.text_area("Body", value=content)
                    else:
                        body = st.text_area("Body", placeholder="Enter your email content here.")
                else:
                    st.warning("No templates found.")
                    body = st.text_area("Body", placeholder="Enter your email content here.")
            except Exception as e:
                st.error(f"Error loading templates: {e}")
            finally:
                client.close()
        else:
            st.error("Failed to connect to the database.")
            body = st.text_area("Body", placeholder="Enter your email content here.")
    
        signature = st.text_area(
            "Signature", 
            value=st.session_state.get('selected_signature', '') if 'selected_signature' in st.session_state else ''
        )
        

        # Send Email Button
        if st.button("Send Email"):
            if to_addresses:
                full_body = body + f"\n\n{signature}" if signature else body
                try:
                    service = authenticate_gmail_api()
                    send_email(service, from_address, to_addresses, subject, full_body, user_id, ",".join(cc_addresses), ",".join(bcc_addresses))
                    st.success("Email sent successfully!")
                except Exception as e:
                    st.error(f"Failed to send email: {e}")
            else:
                st.warning("Please upload a CSV file with valid To contacts.")


        schedule_date = st.date_input("Schedule Date")
        schedule_time = st.time_input("Schedule Time")  # Default time is the current time

        # Combine Date and Time
        schedule_datetime = datetime.combine(schedule_date, schedule_time)

        # Scheduling Section
        if schedule_datetime <= datetime.now():
            st.error("Schedule date and time must be in the future.")
        else:
            if st.button("Schedule Email"):
                from_address = user_details['username'] 
                if to_addresses:
                    full_body = body + f"\n\n{signature}" if signature else body
                    schedule_email_with_apscheduler(user_id, to_addresses, subject, full_body, schedule_datetime, cc_addresses, bcc_addresses)
                else:
                    st.warning("Please add recipients.")



def app():
    
    class MultiApp:
        def __init__(self):
            self.apps=[]
        def add_app(self,title,function):
            self.apps.append({
                "title":title,
                "function":function
            })
        def run():
            with st.sidebar:
                app=option_menu(
                    menu_title="Send Mail",
                    options=['Compose Mail','Scheduled mails'],
                    default_index=0   
                )

            if app=='Compose Mail':
                email_dashboard()
            if app=='Scheduled mails':
                generate_scheduled_email_reports()

        run()







    