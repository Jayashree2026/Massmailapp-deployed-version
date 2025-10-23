import streamlit as st
import pandas as pd
from db import get_db, to_object_id, now



def check_user_and_store(user_id):
    client, db = get_db()
    if db is  None:

        return False
    try:
        if not user_id:
            st.session_state['user_id'] = "superuser"
            st.success("Using default 'superuser' account.")
            return True
        # try find by _id or by id/username
        oid = to_object_id(user_id)
        query = {"$or":[{"_id": oid}] } if oid else {"$or":[{"username": user_id},{"id":user_id}]}
        user = db.users.find_one(query) if query else None
        if user and user.get("is_enabled", False):
            st.session_state['user_id'] = str(user.get("_id"))
            st.success(f"User {st.session_state['user_id']} is enabled.")
            return True
        else:
            st.warning("User is not enabled or does not exist.")
            return False
    except Exception as e:
        st.error(f"Database error: {e}")
        return False
    finally:
        client.close()

def create_template(user_id, template_name, template_content):
    client, db = get_db()
    if db is  None:
        return False
    try:
        if not user_id:
            user_id = "superuser"
        # check duplicate for this user
        existing = db.templates.find_one({"user_id": user_id, "template_name": template_name})
        if existing:
            st.warning("Template name already exists for this user.")
            return False
        doc = {"user_id": user_id, "template_name": template_name, "template_content": template_content, "superuser": user_id=="superuser", "created_at": now()}
        db.templates.insert_one(doc)
        st.success(f"Template '{template_name}' created.")
        return True
    except Exception as e:
        st.error(f"Failed to create template: {e}")
        return False
    finally:
        client.close()

def update_template(template_name, new_template_content):
    client, db = get_db()
    if db is  None:
        return False
    try:
        db.templates.update_many({"template_name": template_name}, {"$set":{"template_content": new_template_content}})
        st.success("Template updated successfully!")
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return False
    finally:
        client.close()

def delete_template(template_name):
    client, db = get_db()
    if db is  None:
        return False
    try:
        db.templates.delete_many({"template_name": template_name})
        st.success("Template deleted successfully.")
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return False
    finally:
        client.close()

def get_templates(user_id):
    client, db = get_db()
    if db is  None:
        return []
    try:
        docs = list(db.templates.find({"user_id": user_id}, {"template_name":1, "template_content":1, "_id":0}))
        return [(d.get("template_name"), d.get("template_content")) for d in docs]
    except Exception as e:
        st.error(f"Error: {e}")
        return []
    finally:
        client.close()

def get_Supertemplates():
    client, db = get_db()
    if db is  None:
        return []
    try:
        docs = list(db.templates.find({"superuser": True}, {"template_name":1,"template_content":1,"_id":0}))
        return [(d.get("template_name"), d.get("template_content")) for d in docs]
    except Exception as e:
        st.error(f"Error: {e}")
        return []
    finally:
        client.close()

#Display and manage templates
def manage_templates():
    tempcss="""<style>
    @import url('https://fonts.googleapis.com/css2?family=Delius+Unicase:wght@400;700&family=DynaPuff:wght@400..700&family=Funnel+Sans:ital,wght@0,300..800;1,300..800&display=swap');
                
    [data-testid="stApp"]{
        background-color:#ffffff;
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
        [data-testid="stSidebarUserContent"]{
        border-radius:5px;}

    [data-testid="stTable"]{
        border:2px solid black;
        background-color:#deeded;
        padding:8px;}
        [data-testid="stBaseButton-secondary"]{
        border:2px solid black;
        }
        [class="st-bt st-bu st-bv st-da st-bx st-by st-c5 st-bz st-c7"]{
        border:2px solid black;
        border-radius:5px;}
        [data-testid="stTextInputRootElement"]{
        border:2px solid black;
        background-color:white;}
        [data-testid="stTextAreaRootElement"]{
        border:2px solid black;
        border-radius:5px;
    </style>"""


    st.markdown(tempcss,unsafe_allow_html=True);
    st.title("Manage Templates")
    st.markdown("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
    # Fetch and display superuser templates
    st.subheader("Ready-made Templates")
    superuser_templates = get_Supertemplates()
    if superuser_templates:
        st.table(pd.DataFrame(superuser_templates, columns=["Template_Name", "Template_Content"]))
    else:
        st.write("No templates found for the superuser.")

    st.markdown("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
    st.header("User Authentication")
    user_id = st.text_input("Enter your User ID (Leave blank for default superuser)")
    if st.button("Check User Status and Proceed"):
        if check_user_and_store(user_id):
            st.success("User ID stored successfully. You can now manage templates or send emails.")

    # Retrieve user_id from session state
    user_id = st.session_state.get('user_id', "superuser")
    st.write(f"**Managing templates for User ID:** {user_id}")

    # Fetch and display user templates
    st.subheader("Available Templates")
    user_templates = get_templates(user_id)
    if user_templates:
        st.table(pd.DataFrame(user_templates, columns=["Template_Name", "Template_Content"]))
    else:
        st.write("No templates found for this user.")
    st.markdown("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
    # Create Template
    st.subheader("Create Template")
    template_name = st.text_input("Template Name")
    template_content = st.text_area("Template Content")
    if st.button("Create Template"):
        if template_name and template_content:
            create_template(user_id, template_name, template_content)
        else:
            st.warning("Please fill out all fields to create a template.")
    st.markdown("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
        # ---------- Update/Delete Template ----------
    st.subheader("Update/Delete Template")
    client, db = get_db()
    if db is not None:
        try:
            # fetch templates for this user or superuser
            templates = list(
                db.templates.find(
                    {"$or": [{"user_id": user_id}, {"superuser": True}]},
                    {"template_name": 1, "_id": 0},
                )
            )
            template_options = [t["template_name"] for t in templates]
            selected_template = st.selectbox("Select a Template to Update/Delete", template_options)

            if selected_template:
                new_content = st.text_area("New Template Content", "")

                if st.button("Update Template"):
                    if new_content:
                        update_template(selected_template, new_content)
                    else:
                        st.warning("Please fill out the new content to update the template.")

                if st.button("Delete Template"):
                    delete_template(selected_template)
        except Exception as e:
            st.error(f"Database error: {e}")
        finally:
            client.close()

def app():
    manage_templates()
