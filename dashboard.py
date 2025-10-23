# dashboard.py
import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
from streamlit_echarts import st_echarts
from db import get_db, to_object_id
from bson.son import SON



# Fetch user stats

def fetch_user_stats():
    client, db = get_db()
    if db is None:

        return {'total_sent':0,'total_delivered':0,'landed_inbox':0,'landed_spam':0}
    try:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_sent": {"$sum": {"$ifNull":["$sent",0]}},
                    "total_delivered": {"$sum": {"$ifNull":["$delivered",0]}},
                    "landed_inbox": {"$sum": {"$ifNull":["$inbox",0]}},
                    "landed_spam": {"$sum": {"$ifNull":["$spam",0]}}
                }
            }
        ]
        res = list(db.email_stats.aggregate(pipeline))
        if not res:
            return {'total_sent':0,'total_delivered':0,'landed_inbox':0,'landed_spam':0}
        row = res[0]
        return {
            'total_sent': int(row.get('total_sent',0)),
            'total_delivered': int(row.get('total_delivered',0)),
            'landed_inbox': int(row.get('landed_inbox',0)),
            'landed_spam': int(row.get('landed_spam',0))
        }
    except Exception as e:
        st.error(f"Error fetching stats: {e}")
        return {'total_sent':0,'total_delivered':0,'landed_inbox':0,'landed_spam':0}
    finally:
        client.close()

def fetch_user_performance():
    client, db = get_db()
    if db is None:
        return pd.DataFrame()
    try:
        pipeline = [
            {"$group": {"_id": "$user_id", "total_sent": {"$sum": {"$ifNull":["$sent",0]}}}},
            {"$sort": SON([("_id", 1)])}
        ]
        res = list(db.email_stats.aggregate(pipeline))
        # Normalize results: _id may be ObjectId or string
        data = [{"user_id": str(r["_id"]), "total_sent": int(r["total_sent"])} for r in res]
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching user performance: {e}")
        return pd.DataFrame()
    finally:
        client.close()

def fetch_campaign_growth():
    client, db = get_db()
    if db is None:
        return pd.DataFrame()
    try:
        pipeline = [
            {"$group": {"_id": {"$dateToString": {"format":"%Y-%m-%d", "date":"$timestamp"}}, "count": {"$sum": 1}}},
            {"$sort": SON([("_id", 1)])}
        ]
        res = list(db.email_stats.aggregate(pipeline))
        data = [{"campaign_date": r["_id"], "total_campaigns": r["count"]} for r in res]
        df = pd.DataFrame(data)
        if not df.empty:
            df["campaign_date"] = pd.to_datetime(df["campaign_date"])
        return df
    except Exception as e:
        st.error(f"Error fetching campaign growth: {e}")
        return pd.DataFrame()
    finally:
        client.close()


# Display the updated dashboard
def show_superuser_overview():
    dashcss = """<style>
    @import url('https://fonts.googleapis.com/css2?family=Delius+Unicase:wght@400;700&family=DynaPuff:wght@400..700&family=Funnel+Sans:ital,wght@0,300..800;1,300..800&display=swap');
    [data-testid="stApp"] { background-color:#ffffff; color:black; }
    [data-testid="stSidebarContent"]{
        background-color:#4f6367;}
    h1{
        font-family: 'Delius Unicase', cursive;}
    h3{
        font-family: 'DanPuff', sans-serif;}
    [data-testid="stHeader"] { background-color:black; }
    [data-testid="stSidebarUserContent"] { border-radius:5px; }
    [data-testid="stBaseButton-secondary"] { border:2px solid black; }
    [data-testid="stColumn"] { background-color:#deeded; border-radius:5px;margin-bottom:20px; border:3px Solid Black; padding:10px;
     box-shadow: 0 10px 10px rgba(0, 0, 0, 0.8); }
    canvas{ 
    background-color: white; 
    padding: 15px; 
    border-radius: 10px;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
}
    </style>"""

    st.markdown(dashcss, unsafe_allow_html=True)
    st.title("Admin Overview")
    st.markdown("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
    stats = fetch_user_stats()

    if not stats:
        st.error("No data found. Ensure the database is populated and the query is correct.")
        return

    total_sent = int(stats.get('total_sent', 0))
    total_delivered = int(stats.get('total_delivered', 0))
    landed_inbox = int(stats.get('landed_inbox', 0))
    landed_spam = int(stats.get('landed_spam', 0))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sent", total_sent)
    col2.metric("Total Delivered", total_delivered)
    col3.metric("Landed in Inbox", landed_inbox)
    col4.metric("Landed in Spam", landed_spam)

    # Deliverability Score as a Gauge
    if total_delivered > 0:
        deliverability_score = (landed_inbox / total_delivered) * 100
    else:
        deliverability_score = 0

    st.subheader("Deliverability Score")
    gauge_options = {
        "tooltip": {"formatter": "{a} <br/>{b} : {c}%"},
        "series": [
            {
                "name": "Score",
                "type": "gauge",
                "detail": {"formatter": "{value}%"},
                "data": [{"value": deliverability_score, "name": "Deliverability"}],
            }
        ],
    }
    st_echarts(options=gauge_options)

    # Bar chart for Sent, Delivered, Inbox, and Spam
    st.subheader("Email Performance Breakdown")
    bar_data = {
        "categories": ["Sent", "Delivered", "Inbox", "Spam"],
        "values": [total_sent, total_delivered, landed_inbox, landed_spam],
    }
    bar_options = {
        "xAxis": {"type": "category", "data": bar_data["categories"]},
        "yAxis": {"type": "value"},
        "series": [{"data": bar_data["values"], "type": "bar"}],
    }
    st_echarts(options=bar_options)

    st.subheader("User performance")
    # Linear chart for User Performance
    user_data = fetch_user_performance()

    if user_data.empty:
        st.warning("No data found. Ensure the database is populated with valid records.")
        return

    # Plot a bar graph
    try:
        fig, ax = plt.subplots()
        ax.bar(user_data['user_id'], user_data['total_sent'], color='skyblue')
        ax.set_title("User Participation Based on Sent Emails")
        ax.set_xlabel("User ID")
        ax.set_ylabel("Number of Emails Sent")
        plt.xticks()
        st.pyplot(fig)
    except Exception as e:
        st.error(f"Error rendering the graph: {e}")

    # Linear graph for Campaign Growth
    st.subheader("Campaign Growth Over Time")
    campaign_data = fetch_campaign_growth()
    if not campaign_data.empty:
        st.line_chart(campaign_data.set_index("campaign_date"))

# Main app
def app():
    show_superuser_overview()


