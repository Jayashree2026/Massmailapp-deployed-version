import streamlit as st
from streamlit_option_menu import option_menu
import dashboard,sendmail,template,usermanagement




def app():
    
    
    #Main front page display
    def main():
# Custom CSS for styling
        maincss = """
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Delius+Unicase:wght@400;700&family=DynaPuff:wght@400..700&family=Funnel+Sans:ital,wght@0,300..800;1,300..800&display=swap');
                [data-testid="stHeader"]{
                background-color:black;}
                [data-testid="stApp"] {
                background-color;white
                }
                .block {
                    border: 2px solid #1e1d1c;
                    margin: 10px 0;
                    padding: 15px;
                    border-radius: 10px;
                    background-color:#deeded;
                    text-align: center;
                    box-shadow: 0 10px 10px rgba(0, 0, 0, 0.8);
                    margin-bottom: 22px;
                    font-family: 'DynaPuff', sans-serif;
                }
                .block h4 {
                font-family: 'Funnel Sans', sans-serif;
                font-size: 25px;
                }
                h1{
                font-family: 'Delius Unicase', cursive;}
                .block p {
                font-size: 18px;
                }
                [data-testid="stSidebarContent"]{
                 background-color:#4f6367;}
                
                [data-testid="stBaseButton-secondary"]{
                margin-top:20px;
                border:2px solid black;}
            </style>
        """
        st.markdown(maincss, unsafe_allow_html=True)

        # Header Section
        image, title = st.columns([1, 3])

        with image:
            st.image("./massmailit.png")

        with title:
            st.title("Ready to amplify your email campaigns?")

        st.markdown("---")

        # Function to create a styled block
        def create_block(emoji, title, description):
            st.markdown(
                f"""
                <div class="block">
                    <h4>{emoji} {title}</h4>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Content Blocks
        create_block("👥", "User Management ", "Maintain control over your email campaigns with our robust User Management system.")
        create_block("📊", "Dashboard ", "Monitor and analyze your email campaigns in real-time.")
        create_block("📝", "Compose Email ", "Craft and send personalized mass emails effortlessly. You can also schedule your mails.")
        create_block("📑", "Templates ", "Create and use customizable email templates for your campaigns.")


    # Main Function
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
                    menu_title="Main Menu",
                    options=['Home','User & Contact Management','Dashboard','Send Mail','Templates'],
                    default_index=0   
                )

            if app=='Home':
                main()
            if app=='Dashboard':
                dashboard.app()
            if app=='Send Mail':
                sendmail.app()
            if app=='User & Contact Management':
                usermanagement.app()
            if app=='Templates':
                template.app()

        run()
    if st.button("Logout"):
        st.session_state.is_logged_in = False  # Update login state

