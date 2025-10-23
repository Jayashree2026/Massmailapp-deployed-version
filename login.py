import streamlit as st
from hashlib import sha256
from db import get_db, to_object_id
import mainpage

# Initialize session state for login status
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False

st.set_page_config(
        page_title="Mass Mailing",
    )

def register_superuser(username, password):
    if not username or not username.strip():
        return {"status":"error","message":"Username cannot be empty."}
    if not password or len(password)<8:
        return {"status":"error","message":"Password must be at least 8 characters long."}
    client, db = get_db()
    if db is None:
        return {"status":"error","message":"DB connection failed."}
    try:
        hashed_password = sha256(password.encode()).hexdigest()
        # ensure unique username
        if db.users.find_one({"username": username.strip()}):
            return {"status":"error", "message":"Username already exists."}
        user_doc = {"username": username.strip(), "password": hashed_password, "is_superuser": True, "is_enabled": True}
        db.users.insert_one(user_doc)
        return {"status":"success", "message":"Admin registered successfully!"}
    except Exception as e:
        return {"status":"error", "message": f"Registration failed: {e}"}
    finally:
        client.close()

def login_superuser(username, password):
    client, db = get_db()
    if db is None:
        return {"status":"error","message":"DB connection failed."}
    try:
        hashed_password = sha256(password.encode()).hexdigest()
        user = db.users.find_one({"username": username, "password": hashed_password, "is_superuser": True})
        if user:
            return {"status":"success", "user": user}
        else:
            return {"status":"error", "message":"Invalid credentials or not an Admin"}
    except Exception as e:
        return {"status":"error", "message": f"Login failed: {e}"}
    finally:
        client.close()


# Function to display the login/register page for superusers
def show_login_page():
    logincss="""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Delius+Unicase:wght@400;700&family=DynaPuff:wght@400..700&family=Funnel+Sans:ital,wght@0,300..800;1,300..800&display=swap');
       body{
       font-family: 'DynaPuff', sans-serif;}         
    h1{
        font-size:40px;
        font-family: 'Delius Unicase', cursive;
        }
        label p{
        color:#1e1d1c;
        }
        [data-testid="stradio"]{
        color:#1e1d1c;
        }
        [data-testid="stBaseButton-secondary"]{
        background-color:black;}

        [data-testid="stTextInputRootElement"]{
        border:2px solid black;
        }
        button p{
        color:white;
        width:#1e1d1c;
        }
        [data-testid="stButton"]{
        backgoround-color:black;}
        </style>
        """
    st.markdown(logincss, unsafe_allow_html=True)

    col1,col2 = st.columns([1,1])
    with col1:
        st.image("./Massmailit.png")


    with col2:
        col2_style = """
        <style>
        div[data-testid="stVerticalBlock"] > div:nth-child(n) {
            font-family: 'DynaPuff', sans-serif;
        
            </style>

        """
        st.markdown(col2_style, unsafe_allow_html=True)
    

        st.title("Welcome !")
        st.subheader("Admin Authentication")

        auth_action = st.radio("Choose action", ["Register", "Login"])

        # Authentication form
        username = st.text_input("Username", key="username")
        password = st.text_input("Password", type="password", key="password")

        # Register Button
        if auth_action == "Register":
            if st.button("Register", key="register", help="Click to Register as Admin"):
                response = register_superuser(username, password)
                if response['status'] == "success":
                    st.success(response['message'])
                else:
                    st.error(response.get('message', "Registration failed"))

        # Login Button
        elif auth_action == "Login":
            if st.button("Login", key="login", help="Click to Login as Admin"):
                response = login_superuser(username, password)
                if response['status'] == "success":
                    st.session_state['user'] = response['user']
                    st.session_state.is_logged_in = True
                    st.success("Logged in successfully!")
                else:
                    st.error(response.get('message', "Login failed"))


# Main app logic
if st.session_state.is_logged_in:
    mainpage.app()
else:

    show_login_page()
